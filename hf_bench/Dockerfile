# Dockerfile (GPU, long-lived server with SSE)
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    TRANSFORMERS_CACHE=/models \
    TORCH_HOME=/models \
    MODEL_STORE_DIR=/models_store

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3-pip git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3.11 -m pip install --upgrade pip

# PyTorch CUDA (cu124)
RUN python3.11 -m pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cu124 \
    torch torchvision torchaudio

# App deps
RUN python3.11 -m pip install --no-cache-dir \
    fastapi==0.115.6 \
    "uvicorn[standard]==0.32.1" \
    psutil==6.1.0 \
    transformers==4.46.3 \
    accelerate==1.12.0 \
    safetensors==0.4.5 \
    huggingface_hub==0.26.5

# Copy the clean-arch code (expects hf_bench/app/** in your repo)
COPY hf_bench/app /app/app

EXPOSE 8000

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
