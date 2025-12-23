FROM python:3.13-slim

WORKDIR /app

# Installation des dépendances système (si nécessaire pour certaines libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Installation de 'uv' pour gérer les dépendances rapidement
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvbin/uv

# Copie des fichiers de dépendances
COPY pyproject.toml uv.lock ./
RUN /uvbin/uv sync --frozen --no-cache

# Copie du reste du code
COPY . .

# Commande de lancement
CMD ["/uvbin/uv", "run", "fastapi", "run", "api.main.py", "--port", "8000"]