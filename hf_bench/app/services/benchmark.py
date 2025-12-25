from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import psutil
import torch

from app.core.config import Settings


def build_prompt(schema: str, question: str) -> str:
    return (
        "You are a SQL generation engine.\n\n"
        "You MUST output a single valid SQL query.\n"
        "Do NOT output explanations, comments, notes, or markdown.\n"
        "Do NOT repeat the question.\n"
        "Do NOT add any text before or after the SQL.\n\n"
        "Rules:\n"
        "- Use ONLY the tables and columns present in the schema.\n"
        "- If aggregation per group is requested, you MUST use GROUP BY.\n"
        "- If the question asks \"par X\", you MUST include X in SELECT and GROUP BY.\n"
        "- The output must be executable as-is.\n\n"
        "DATABASE SCHEMA:\n"
        f"{schema}\n\n"
        "QUESTION:\n"
        f"{question}\n\n"
        "SQL QUERY:\n"
    )


def extract_sql(text: str) -> str:
    t = text.strip()
    if ";" in t:
        return t.split(";", 1)[0].strip() + ";"
    return t


@dataclass
class BenchRunner:
    settings: Settings

    def warmup(
        self,
        *,
        tokenizer: Any,
        model: Any,
        schema: str,
        question: str,
    ) -> None:
        prompt = build_prompt(schema, question)
        if len(prompt) > self.settings.max_prompt_chars:
            prompt = prompt[: self.settings.max_prompt_chars]

        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(self.settings.device) for k, v in inputs.items()}

        with torch.no_grad():
            _ = model.generate(**inputs, max_new_tokens=16, do_sample=False)
        if torch.cuda.is_available():
            torch.cuda.synchronize()

    def run_once(
        self,
        *,
        question_id: int,
        tokenizer: Any,
        model: Any,
        schema: str,
        question: str,
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        do_sample: bool,
        gpu_stats_fn,
    ) -> Dict[str, Any]:
        prompt = build_prompt(schema, question)
        if len(prompt) > self.settings.max_prompt_chars:
            prompt = prompt[: self.settings.max_prompt_chars]

        max_new = max(1, min(max_new_tokens, self.settings.max_new_tokens))

        proc = psutil.Process()
        start_mem = proc.memory_info().rss / (1024 * 1024)
        start = time.perf_counter()

        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(self.settings.device) for k, v in inputs.items()}

        if torch.cuda.is_available():
            torch.cuda.synchronize()
        gen_start = time.perf_counter()

        with torch.no_grad():
            out_ids = model.generate(
                **inputs,
                max_new_tokens=max_new,
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
            )

        if torch.cuda.is_available():
            torch.cuda.synchronize()
        gen_end = time.perf_counter()

        end = time.perf_counter()
        end_mem = proc.memory_info().rss / (1024 * 1024)

        decoded = tokenizer.decode(out_ids[0], skip_special_tokens=True)
        completion = decoded[len(prompt):].strip() if decoded.startswith(prompt) else decoded.strip()
        sql = extract_sql(completion)

        num_new_tokens = int(out_ids.shape[-1] - inputs["input_ids"].shape[-1])
        gen_s = max(gen_end - gen_start, 1e-9)
        tps = num_new_tokens / gen_s

        return {
            "question_id": question_id,
            "raw_answer": completion,
            "sql": sql,
            "metrics": {
                "gen_time_ms": (gen_end - gen_start) * 1000,
                "exec_time_ms": (end - start) * 1000,
                "new_tokens": num_new_tokens,
                "tokens_per_s": tps,
                "ram_delta_mb": end_mem - start_mem,
                "cpu_percent": psutil.cpu_percent(interval=None),
                "gpu": gpu_stats_fn(),
            },
        }
