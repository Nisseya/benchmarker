# worker_hf.py
from __future__ import annotations

import os
import time
import threading
from typing import Optional, Dict, Any, Literal

import psutil
from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel, Field

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    AutoModelForSeq2SeqLM,
    GenerationConfig,
)

app = FastAPI(title="hf-llm-worker", version="1.0.0")


# ----------------------------
# Config
# ----------------------------
HF_CACHE_DIR = os.getenv("HF_HOME", os.getenv("TRANSFORMERS_CACHE", "./.hf_cache"))
DEFAULT_MODEL = os.getenv("HF_DEFAULT_MODEL", "").strip() or None
DEFAULT_TASK: Literal["causal-lm", "seq2seq"] = os.getenv("HF_DEFAULT_TASK", "causal-lm")  # best-effort
DEFAULT_DEVICE = os.getenv("HF_DEVICE", "auto")  # "auto" | "cpu" | "cuda"
DEFAULT_DTYPE = os.getenv("HF_DTYPE", "auto")  # "auto" | "float16" | "bfloat16" | "float32"

# Optional: avoid exposing arbitrary model loading in prod
ALLOW_DYNAMIC_MODEL_LOAD = os.getenv("ALLOW_DYNAMIC_MODEL_LOAD", "1") == "1"
ALLOWED_MODELS = set(
    m.strip() for m in os.getenv("HF_ALLOWED_MODELS", "").split(",") if m.strip()
)  # if provided, only these are allowed


# ----------------------------
# Model state (single loaded model per worker)
# ----------------------------
_lock = threading.Lock()
_state: Dict[str, Any] = {
    "model_id": None,
    "task": None,
    "tokenizer": None,
    "model": None,
    "device": None,
    "dtype": None,
    "loaded_at": None,
}


def _pick_device(device: str) -> str:
    if device == "cpu":
        return "cpu"
    if device == "cuda":
        if not torch.cuda.is_available():
            return "cpu"
        return "cuda"
    # auto
    return "cuda" if torch.cuda.is_available() else "cpu"


def _pick_dtype(dtype: str, device: str):
    if dtype == "float16":
        return torch.float16
    if dtype == "bfloat16":
        return torch.bfloat16
    if dtype == "float32":
        return torch.float32
    # auto
    if device == "cuda":
        # bfloat16 if supported, else float16
        if torch.cuda.is_available():
            major, _minor = torch.cuda.get_device_capability()
            # Ampere+ supports bf16 reasonably; keep it simple
            return torch.bfloat16 if major >= 8 else torch.float16
    return torch.float32


def _ensure_allowed(model_id: str):
    if not ALLOW_DYNAMIC_MODEL_LOAD and (_state["model_id"] is None):
        raise HTTPException(status_code=403, detail="Dynamic model loading is disabled.")
    if ALLOWED_MODELS and model_id not in ALLOWED_MODELS:
        raise HTTPException(status_code=403, detail="Model not in allowlist.")


def load_model(model_id: str, task: Literal["causal-lm", "seq2seq"], device: str, dtype: str):
    _ensure_allowed(model_id)

    dev = _pick_device(device)
    dt = _pick_dtype(dtype, dev)

    tokenizer = AutoTokenizer.from_pretrained(model_id, cache_dir=HF_CACHE_DIR, use_fast=True)

    if task == "seq2seq":
        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_id,
            cache_dir=HF_CACHE_DIR,
            torch_dtype=dt if dev == "cuda" else None,
            device_map=None,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            cache_dir=HF_CACHE_DIR,
            torch_dtype=dt if dev == "cuda" else None,
            device_map=None,
        )

    model.eval()
    model.to(dev)

    _state.update(
        {
            "model_id": model_id,
            "task": task,
            "tokenizer": tokenizer,
            "model": model,
            "device": dev,
            "dtype": str(dt).replace("torch.", ""),
            "loaded_at": time.time(),
        }
    )


def _require_loaded():
    if _state["model"] is None or _state["tokenizer"] is None:
        raise HTTPException(status_code=409, detail="No model loaded. Call POST /load first (or set HF_DEFAULT_MODEL).")


# ----------------------------
# Prompting for Text-to-SQL style (schema + question)
# ----------------------------
def build_prompt(schema: str, question: str) -> str:
    # “Safe-ish” default: ask for SQL only. Adapt as needed for your benchmark.
    return (
        "You are a senior data engineer. Convert the user question into a single SQL query.\n"
        "Rules:\n"
        "- Output ONLY the SQL query, no markdown, no explanations.\n"
        "- Use only the tables/columns present in the schema.\n"
        "- If something is ambiguous, make the most reasonable assumption.\n\n"
        "DATABASE SCHEMA:\n"
        f"{schema}\n\n"
        "QUESTION:\n"
        f"{question}\n\n"
        "SQL:"
    )


# ----------------------------
# API models
# ----------------------------
class LoadRequest(BaseModel):
    model_id: str = Field(..., description="HuggingFace model id, e.g. 'Qwen/Qwen2.5-0.5B-Instruct'")
    task: Literal["causal-lm", "seq2seq"] = Field("causal-lm")
    device: str = Field(DEFAULT_DEVICE, description="auto|cpu|cuda")
    dtype: str = Field(DEFAULT_DTYPE, description="auto|float16|bfloat16|float32")


class GenerateRequest(BaseModel):
    schema: str
    question: str

    # generation params
    max_new_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    do_sample: bool = False

    # Optional: override model for this call (if enabled / allowlisted)
    model_id: Optional[str] = None
    task: Optional[Literal["causal-lm", "seq2seq"]] = None
    device: Optional[str] = None
    dtype: Optional[str] = None


# ----------------------------
# Endpoints
# ----------------------------
@app.get("/")
async def root():
    return {"status": "ok", "service": "hf-llm-worker"}


@app.get("/health")
async def health():
    process = psutil.Process(os.getpid())
    rss_mb = process.memory_info().rss / (1024 * 1024)

    gpu = None
    if torch.cuda.is_available():
        try:
            gpu = {
                "device": torch.cuda.get_device_name(0),
                "allocated_mb": torch.cuda.memory_allocated(0) / (1024 * 1024),
                "reserved_mb": torch.cuda.memory_reserved(0) / (1024 * 1024),
            }
        except Exception:
            gpu = {"device": "cuda", "allocated_mb": None, "reserved_mb": None}

    return {
        "status": "ok",
        "model_loaded": _state["model_id"] is not None,
        "model_id": _state["model_id"],
        "task": _state["task"],
        "device": _state["device"],
        "dtype": _state["dtype"],
        "rss_mb": rss_mb,
        "gpu": gpu,
    }


@app.post("/load")
async def load(req: LoadRequest):
    with _lock:
        t0 = time.perf_counter()
        load_model(req.model_id, req.task, req.device, req.dtype)
        dt_ms = (time.perf_counter() - t0) * 1000

    return {
        "status": "loaded",
        "model_id": _state["model_id"],
        "task": _state["task"],
        "device": _state["device"],
        "dtype": _state["dtype"],
        "load_time_ms": dt_ms,
        "cache_dir": HF_CACHE_DIR,
    }


@app.post("/generate")
async def generate(req: GenerateRequest = Body(...)):
    # Optional per-call override (useful for your benchmark runner)
    if req.model_id:
        with _lock:
            task = req.task or DEFAULT_TASK
            device = req.device or DEFAULT_DEVICE
            dtype = req.dtype or DEFAULT_DTYPE
            load_model(req.model_id, task, device, dtype)

    _require_loaded()

    prompt = build_prompt(req.schema, req.question)

    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss / (1024 * 1024)
    start_time = time.perf_counter()

    tokenizer = _state["tokenizer"]
    model = _state["model"]
    device = _state["device"]

    try:
        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}

        gen_cfg = GenerationConfig(
            max_new_tokens=req.max_new_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
            do_sample=req.do_sample,
        )

        with torch.no_grad():
            if _state["task"] == "seq2seq":
                out_ids = model.generate(**inputs, generation_config=gen_cfg)
                text = tokenizer.decode(out_ids[0], skip_special_tokens=True)
                # For seq2seq, decoded includes only target by default; keep it as-is.
                completion = text.strip()
            else:
                out_ids = model.generate(**inputs, generation_config=gen_cfg)
                full = tokenizer.decode(out_ids[0], skip_special_tokens=True)
                # Strip the prompt prefix if it appears (best-effort)
                completion = full[len(prompt) :].strip() if full.startswith(prompt) else full.strip()

        end_time = time.perf_counter()
        end_mem = process.memory_info().rss / (1024 * 1024)

        return {
            "status": "success",
            "model_id": _state["model_id"],
            "task": _state["task"],
            "device": _state["device"],
            "dtype": _state["dtype"],
            "exec_time_ms": (end_time - start_time) * 1000,
            "ram_delta_mb": end_mem - start_mem,
            "cpu_percent": psutil.cpu_percent(),
            "prompt": prompt,
            "answer": completion,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"inference_error: {repr(e)}")


# Auto-load a default model if provided
@app.on_event("startup")
def _startup():
    if DEFAULT_MODEL:
        with _lock:
            if _state["model_id"] is None:
                load_model(DEFAULT_MODEL, DEFAULT_TASK, DEFAULT_DEVICE, DEFAULT_DTYPE)
