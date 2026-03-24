# On part d'une image Python légère
FROM python:3.11-slim

# Dossier de travail dans le conteneur
WORKDIR /app

# Dépendances système (pyodbc, curl pour healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Build context = Modeles_TimesSeries/ ──────────────────
# Dépendances Python
COPY api/api-inference/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'API inference
COPY api/api-inference/app/ ./app/

# Modèles entraînés (écrasés par le volume en prod)
COPY models/saved/ ./models/saved/

# Config YAML
COPY config/ ./config/

# Module src (Prophet, features engineering, etc.)
COPY src/ ./src/

# Dossier exports (outbox Fabric — monté en volume en prod)
RUN mkdir -p /app/exports

# Port exposé
EXPOSE 8001

# Commande de démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]