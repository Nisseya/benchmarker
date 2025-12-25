FROM python:3.9-slim

WORKDIR /app
RUN pip install fastapi uvicorn psutil

COPY worker_api.py .

# On lance le serveur sur le port 8000
CMD ["uvicorn", "workers.server.worker_api:app", "--host", "0.0.0.0", "--port", "8000"]