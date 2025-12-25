# server.py
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

import psutil
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from huggingface_hub import HfApi, snapshot_download
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer

# ----------------------------
# Config (env)
# ----------------------------
HF_CACHE_DIR = os.getenv("HF_HOME", "/models")
MODEL_STORE_DIR = os.getenv("MODEL_STORE_DIR", "/models_store")  # NVMe mount recommended
REQUIRE_REVISION = os.getenv("REQUIRE_REVISION", "1") == "1"
TRUST_REMOTE_CODE = False  # NEVER enable if users can submit arbitrary HF links
ALLOW_SAFETENSORS_ONLY = os.getenv("ALLOW_SAFETENSORS_ONLY", "1") == "1"

# Hard limits to prevent abuse
MAX_REPO_SIZE_GB = float(os.getenv("MAX_REPO_SIZE_GB", "30"))  # reject above this
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "512"))
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "20000"))
QUEUE_MAXSIZE = int(os.getenv("QUEUE_MAXSIZE", "100"))

# Inference settings
DEVICE = os.getenv("HF_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
DTYPE = os.getenv("HF_DTYPE", "float16")  # float16|bfloat16|float32
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.0"))
DEFAULT_TOP_P = float(os.getenv("DEFAULT_TOP_P", "1.0"))
DEFAULT_DO_SAMPLE = os.getenv("DEFAULT_DO_SAMPLE", "0") == "1"


# ----------------------------
# Helpers
# ----------------------------
def _torch_dtype(dtype: str) -> torch.dtype:
    d = dtype.lower()
    if d == "float16":
        return torch.float16
    if d == "bfloat16":
        return torch.bfloat16
    if d == "float32":
        return torch.float32
    raise ValueError(f"Unsupported dtype: {dtype}")


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


HF_URL_RE = re.compile(r"^https?://huggingface\.co/([^/\s]+/[^/\s]+)(?:/.*)?$")


def parse_hf_input(model: str, revision: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    Accept either:
      - "org/model"
      - "https://huggingface.co/org/model"
      - "https://huggingface.co/org/model/tree/<rev>"
    revision is strongly recommended/required.
    """
    model = model.strip()

    m = HF_URL_RE.match(model)
    if m:
        model_id = m.group(1)
        # Try to infer revision from URL if present: /tree/<rev> or /resolve/<rev>/
        # Best-effort only. Prefer explicit revision field.
        inferred = None
        tree = re.search(r"/tree/([^/\s]+)", model)
        if tree:
            inferred = tree.group(1)
        res = re.search(r"/resolve/([^/\s]+)/", model)
        if res:
            inferred = res.group(1)
        if revision is None:
            revision = inferred
        return model_id, revision

    # raw repo id
    if "/" in model and " " not in model:
        return model, revision

    raise HTTPException(status_code=400, detail="Invalid HF model input. Provide 'org/model' or a huggingface.co URL.")


def build_prompt(schema: str, question: str) -> str:
    # Strict Text-to-SQL prompt (reduces “notes”/explanations)
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
    # Hard stop after first semicolon if present
    if ";" in t:
        return t.split(";", 1)[0].strip() + ";"
    return t


def repo_size_gb(repo_info) -> float:
    total = 0
    siblings = getattr(repo_info, "siblings", None) or []
    for s in siblings:
        size = getattr(s, "size", None)
        if isinstance(size, int):
            total += size
    return total / (1024 ** 3)


def has_safetensors(repo_info) -> bool:
    siblings = getattr(repo_info, "siblings", None) or []
    for s in siblings:
        rfilename = getattr(s, "rfilename", "") or ""
        if rfilename.endswith(".safetensors"):
            return True
    return False


# ----------------------------
# Job model
# ----------------------------
@dataclass
class BenchJob:
    job_id: str
    model_id: str
    revision: str
    schema: str
    question: str
    max_new_tokens: int
    temperature: float
    top_p: float
    do_sample: bool
    dtype: str
    created_at: float = field(default_factory=time.time)
    events: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=200))


# ----------------------------
# App
# ----------------------------
app = FastAPI(title="hf-benchmark-server-sse", version="1.0.0")
api = HfApi()

job_queue: "asyncio.Queue[BenchJob]" = asyncio.Queue(maxsize=QUEUE_MAXSIZE)

# Model in-process cache (optional). We keep only one loaded model at a time.
_loaded: Dict[str, Any] = {
    "key": None,  # (model_id, revision, dtype)
    "tokenizer": None,
    "model": None,
}


class BenchRequest(BaseModel):
    model: str = Field(..., description="HF repo id 'org/model' or https://huggingface.co/org/model")
    revision: Optional[str] = Field(None, description="HF revision (commit SHA strongly recommended). Required if REQUIRE_REVISION=1")
    schema: str
    question: str

    max_new_tokens: int = 256
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    do_sample: bool = DEFAULT_DO_SAMPLE
    dtype: str = DTYPE  # float16|bfloat16|float32


@app.get("/health")
async def health():
    process = psutil.Process(os.getpid())
    rss_mb = process.memory_info().rss / (1024 * 1024)

    gpu = None
    if torch.cuda.is_available():
        gpu = {
            "device": torch.cuda.get_device_name(0),
            "allocated_mb": torch.cuda.memory_allocated(0) / (1024 * 1024),
            "reserved_mb": torch.cuda.memory_reserved(0) / (1024 * 1024),
        }

    return {
        "status": "ok",
        "device": DEVICE,
        "dtype_default": DTYPE,
        "rss_mb": rss_mb,
        "gpu": gpu,
        "queue_size": job_queue.qsize(),
        "model_store_dir": MODEL_STORE_DIR,
        "hf_cache_dir": HF_CACHE_DIR,
        "limits": {
            "max_repo_size_gb": MAX_REPO_SIZE_GB,
            "max_new_tokens": MAX_NEW_TOKENS,
            "max_prompt_chars": MAX_PROMPT_CHARS,
            "require_revision": REQUIRE_REVISION,
            "allow_safetensors_only": ALLOW_SAFETENSORS_ONLY,
            "trust_remote_code": TRUST_REMOTE_CODE,
        },
    }


async def push(job: BenchJob, event: str, payload: Dict[str, Any]) -> None:
    await job.events.put(_sse(event, payload))


def local_snapshot_dir(model_id: str, revision: str) -> str:
    safe_model = model_id.replace("/", "__")
    return os.path.join(MODEL_STORE_DIR, safe_model, revision)


async def ensure_model_on_nvme(job: BenchJob) -> str:
    # Pre-check repo metadata to enforce size / safetensors policy
    t0 = time.perf_counter()
    await push(job, "status", {"phase": "repo_info", "model_id": job.model_id, "revision": job.revision})

    repo = api.repo_info(repo_id=job.model_id, revision=job.revision, repo_type="model")
    size_gb = repo_size_gb(repo)

    if size_gb > MAX_REPO_SIZE_GB:
        raise HTTPException(
            status_code=413,
            detail=f"Model repo too large ({size_gb:.2f} GB) > limit {MAX_REPO_SIZE_GB:.2f} GB",
        )

    if ALLOW_SAFETENSORS_ONLY and not has_safetensors(repo):
        raise HTTPException(
            status_code=415,
            detail="Model repo has no .safetensors weights (policy ALLOW_SAFETENSORS_ONLY=1).",
        )

    dst = local_snapshot_dir(job.model_id, job.revision)
    os.makedirs(dst, exist_ok=True)

    # If already present (best-effort), skip download
    marker = os.path.join(dst, ".READY")
    if os.path.exists(marker):
        await push(job, "status", {"phase": "cached_on_nvme", "path": dst, "repo_size_gb": round(size_gb, 3)})
        return dst

    await push(job, "status", {"phase": "downloading_to_nvme", "path": dst, "repo_size_gb": round(size_gb, 3)})

    # Download snapshot into NVMe dir. We still keep HF cache dir for underlying caching.
    # Limit patterns to common files; allow tokenizer/config; include safetensors shards.
    allow_patterns = [
        "*.safetensors",
        "*.json",
        "tokenizer.*",
        "vocab.*",
        "merges.txt",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "generation_config.json",
        "config.json",
        "added_tokens.json",
        "spiece.model",
        "*.model",
    ]
    # If you want to allow pytorch_model.bin, set ALLOW_SAFETENSORS_ONLY=0
    if not ALLOW_SAFETENSORS_ONLY:
        allow_patterns.append("*.bin")

    snapshot_download(
        repo_id=job.model_id,
        revision=job.revision,
        repo_type="model",
        local_dir=dst,
        local_dir_use_symlinks=False,
        cache_dir=HF_CACHE_DIR,
        allow_patterns=allow_patterns,
        ignore_patterns=["*.msgpack", "*.h5", "*.ot", "*.ckpt"],
    )

    # Mark ready
    with open(marker, "w", encoding="utf-8") as f:
        f.write(f"ok {time.time()}\n")

    dt_ms = (time.perf_counter() - t0) * 1000
    await push(job, "status", {"phase": "download_complete", "ms": round(dt_ms, 2), "path": dst})
    return dst


async def load_model_into_gpu(job: BenchJob, path: str) -> None:
    key = (job.model_id, job.revision, job.dtype)
    if _loaded["key"] == key and _loaded["model"] is not None and _loaded["tokenizer"] is not None:
        await push(job, "status", {"phase": "model_already_loaded", "key": list(key)})
        return

    # Clear previous model to free VRAM
    await push(job, "status", {"phase": "unloading_previous_model"})
    _loaded["key"] = None
    _loaded["tokenizer"] = None
    _loaded["model"] = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    await push(job, "status", {"phase": "loading_model_to_gpu", "path": path, "dtype": job.dtype})
    t0 = time.perf_counter()

    dtype = _torch_dtype(job.dtype)
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=TRUST_REMOTE_CODE, use_fast=True)

    model = AutoModelForCausalLM.from_pretrained(
        path,
        trust_remote_code=TRUST_REMOTE_CODE,
        torch_dtype=dtype if DEVICE.startswith("cuda") else None,
        device_map=None,
    )
    model.eval()
    model.to(DEVICE)

    dt_ms = (time.perf_counter() - t0) * 1000
    _loaded["key"] = key
    _loaded["tokenizer"] = tokenizer
    _loaded["model"] = model

    gpu_stats = None
    if torch.cuda.is_available():
        gpu_stats = {
            "allocated_mb": torch.cuda.memory_allocated(0) / (1024 * 1024),
            "reserved_mb": torch.cuda.memory_reserved(0) / (1024 * 1024),
        }
    await push(job, "status", {"phase": "model_loaded", "ms": round(dt_ms, 2), "gpu": gpu_stats})


async def run_generation(job: BenchJob) -> Dict[str, Any]:
    tokenizer = _loaded["tokenizer"]
    model = _loaded["model"]
    if tokenizer is None or model is None:
        raise HTTPException(status_code=409, detail="Model not loaded.")

    schema = job.schema
    question = job.question

    prompt = build_prompt(schema, question)
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS]

    # Clamp generation bounds
    max_new = min(max(job.max_new_tokens, 1), MAX_NEW_TOKENS)

    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss / (1024 * 1024)
    start = time.perf_counter()

    await push(job, "status", {"phase": "tokenizing"})
    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    # Warmup (not measured) – optional but usually stabilizes
    await push(job, "status", {"phase": "warmup"})
    with torch.no_grad():
        _ = model.generate(
            **inputs,
            max_new_tokens=min(16, max_new),
            temperature=job.temperature,
            top_p=job.top_p,
            do_sample=job.do_sample,
        )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    await push(job, "status", {"phase": "generating"})
    gen_start = time.perf_counter()

    with torch.no_grad():
        out_ids = model.generate(
            **inputs,
            max_new_tokens=max_new,
            temperature=job.temperature,
            top_p=job.top_p,
            do_sample=job.do_sample,
        )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    gen_end = time.perf_counter()
    end = time.perf_counter()
    end_mem = process.memory_info().rss / (1024 * 1024)

    decoded = tokenizer.decode(out_ids[0], skip_special_tokens=True)
    completion = decoded[len(prompt):].strip() if decoded.startswith(prompt) else decoded.strip()
    sql = extract_sql(completion)

    # Token metrics (rough)
    num_new_tokens = int(out_ids.shape[-1] - inputs["input_ids"].shape[-1])
    gen_s = max(gen_end - gen_start, 1e-9)
    tps = num_new_tokens / gen_s

    gpu = None
    if torch.cuda.is_available():
        gpu = {
            "allocated_mb": torch.cuda.memory_allocated(0) / (1024 * 1024),
            "reserved_mb": torch.cuda.memory_reserved(0) / (1024 * 1024),
        }

    return {
        "status": "success",
        "model_id": job.model_id,
        "revision": job.revision,
        "device": DEVICE,
        "dtype": job.dtype,
        "prompt": prompt,
        "raw_answer": completion,
        "sql": sql,
        "metrics": {
            "exec_time_ms": (end - start) * 1000,
            "gen_time_ms": (gen_end - gen_start) * 1000,
            "new_tokens": num_new_tokens,
            "tokens_per_s": tps,
            "ram_delta_mb": end_mem - start_mem,
            "cpu_percent": psutil.cpu_percent(),
            "gpu": gpu,
        },
    }


async def job_worker_loop():
    while True:
        job = await job_queue.get()
        try:
            await push(job, "status", {"phase": "started", "job_id": job.job_id})

            # Ensure model present on NVMe (download time is not your benchmark, but we still stream it)
            path = await ensure_model_on_nvme(job)

            # Load into GPU (this is a key metric for model switching)
            await load_model_into_gpu(job, path)

            # Run inference
            result = await run_generation(job)

            await push(job, "result", result)
            await push(job, "done", {"job_id": job.job_id})

        except HTTPException as he:
            await push(job, "error", {"job_id": job.job_id, "detail": he.detail, "status_code": he.status_code})
            await push(job, "done", {"job_id": job.job_id})
        except Exception as e:
            await push(job, "error", {"job_id": job.job_id, "detail": repr(e)})
            await push(job, "done", {"job_id": job.job_id})
        finally:
            job_queue.task_done()


@app.on_event("startup")
async def startup():
    os.makedirs(HF_CACHE_DIR, exist_ok=True)
    os.makedirs(MODEL_STORE_DIR, exist_ok=True)
    asyncio.create_task(job_worker_loop())


@app.post("/bench/stream")
async def bench_stream(req: BenchRequest, request: Request):
    model_id, revision = parse_hf_input(req.model, req.revision)

    if REQUIRE_REVISION and not revision:
        raise HTTPException(status_code=400, detail="revision is required (set REQUIRE_REVISION=0 to allow default).")

    # If revision missing and allowed, default to main (not recommended for benchmark fairness)
    revision = revision or "main"

    job = BenchJob(
        job_id=str(uuid.uuid4()),
        model_id=model_id,
        revision=revision,
        schema=req.schema,
        question=req.question,
        max_new_tokens=req.max_new_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
        do_sample=req.do_sample,
        dtype=req.dtype,
    )

    # Enqueue
    try:
        job_queue.put_nowait(job)
    except asyncio.QueueFull:
        raise HTTPException(status_code=429, detail="Server queue is full. Try again later.")

    async def event_stream() -> AsyncGenerator[bytes, None]:
        # Initial queued event (position is approximate)
        yield _sse("status", {"phase": "queued", "job_id": job.job_id, "queue_size": job_queue.qsize()}).encode("utf-8")

        try:
            while True:
                # If client disconnected, stop pushing (best-effort)
                if await request.is_disconnected():
                    break

                msg = await job.events.get()
                yield msg.encode("utf-8")

                # end stream on done
                if msg.startswith("event: done"):
                    break
        except asyncio.CancelledError:
            # Client cancelled connection
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # useful behind nginx
        },
    )
