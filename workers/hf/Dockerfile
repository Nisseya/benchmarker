# CUDA runtime + cuDNN (compatible PyTorch)
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    TRANSFORMERS_CACHE=/models \
    TORCH_HOME=/models

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3.11 -m pip install --upgrade pip

# Python deps
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cu124 \
    torch torchvision torchaudio \
    && python3.11 -m pip install --no-cache-dir -r requirements.txt


# App
COPY worker_hf.py .

EXPOSE 8000
CMD ["python3.11", "-m", "uvicorn", "worker_hf:app", "--host", "0.0.0.0", "--port", "8000"]
