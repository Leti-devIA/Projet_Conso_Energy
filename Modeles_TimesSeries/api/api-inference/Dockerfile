# On part d'une image Python légère
FROM python:3.11-slim

# Dossier de travail dans le conteneur
WORKDIR /app

# Dépendances système (pyodbc, curl pour healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    gcc \
    g++ \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Ajouter clé + repo Microsoft puis installer le driver SQL Server
RUN mkdir -p /etc/apt/keyrings \
    && curl https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg

RUN echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    > /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
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