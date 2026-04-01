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

# Dépendances Python API uniquement (build plus rapide)
COPY api/api-inference/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'API inference
COPY api/api-inference/app/ ./app/

# Module src (Prophet, features engineering, etc.)
COPY src/ ./src/

# Config YAML
COPY config/ ./config/

# Modèles entraînés (uniquement fichiers _latest.pkl)
COPY models/saved/*_latest.pkl ./models/saved/

# Données (pour seed, historique, etc.)
COPY data/ ./data/

# Dossiers de travail
RUN mkdir -p /app/exports /app/logs /app/mlruns /app/mlruns_temp

# Port exposé
EXPOSE 8001

# Commande de démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]