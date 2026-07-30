# API Dataclean

## Rôle et positionnement

L'API Dataclean est la **source de vérité des données historiques** du projet. Elle lit les tables pré-nettoyées stockées dans Microsoft Fabric (data warehouse) et les expose via des endpoints HTTP simples.

**Ce que fait cette API :**

- exposer l'historique de consommation Enedis + météo pour chaque site (PRM),
- fournir les prévisions météo futures à l'API d'inférence,
- exporter les tables de référence (sites, prix spot).

**Ce que ne fait pas cette API :**

- elle ne nettoie pas les données brutes (ce travail est fait en amont dans Fabric),
- elle ne fait aucun calcul ML,
- elle n'écrit rien en base.

> Pour un nouveau développeur : pensez à cette API comme un simple pont entre Microsoft Fabric et le reste du système. Elle transforme une requête SQL en CSV ou JSON.

---

## Architecture interne

```
api-dataclean/
│
├── app/
│   ├── main.py                  # Point d'entrée FastAPI (CORS, démarrage)
│   ├── logging_utils.py         # Logs applicatifs structurés
│   ├── config/
│   │   └── database.py          # Connexion Fabric via pyodbc
│   ├── repository/
│   │   └── data_repository.py   # Requêtes SQL (SELECT uniquement)
│   ├── routers/
│   │   └── dataclean.py         # Définition des routes HTTP
│   └── services/
│       └── csv_export.py        # Streaming de fichiers CSV
│
├── requirements.txt
├── Dockerfile
├── .env                         # Variables de connexion DB (non versionné)
└── README.md
```

**Principes de conception :**

- `routers/` : reçoit la requête HTTP et valide les paramètres,
- `repository/` : exécute la requête SQL et retourne des données brutes,
- `services/` : formate et stream la réponse (CSV ou JSON).

---

## Prérequis

- Python 3.11
- ODBC Driver 17 for SQL Server (installé sur la machine ou dans le conteneur Docker)
- Accès réseau au warehouse Microsoft Fabric

---

## Configuration (`.env`)

Créez un fichier `.env` dans `api/api-dataclean/` :

```env
DB_SERVER=<serveur.database.fabric.microsoft.com>
DB_DATABASE=<nom_de_la_base>
DB_USER=<identifiant>
DB_PASSWORD=<mot_de_passe>
```

Sans ces variables, l'API démarre mais retourne `503 Base de données non disponible` sur toutes les routes de données.

---

## Installation et lancement local

```bash
cd api/api-dataclean

# Créer l'environnement virtuel
python -m venv env_api

# Activer (Windows)
.\env_api\Scripts\Activate.ps1
# Activer (macOS/Linux)
source env_api/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API : http://127.0.0.1:8000
- Documentation Swagger interactive : http://127.0.0.1:8000/docs

---

## Endpoints disponibles

### Vérification du statut

```
GET /health
```

Réponse :

```json
{"status": "API dataclean ok"}
```

Cet endpoint ne requiert aucune connexion DB. Il permet au load balancer ou à Docker de vérifier que le processus est vivant.

---

### Historique Enedis + météo par PRM — CSV

```
GET /dataclean/allbyprm?prm=<14_chiffres>
```

Retourne un fichier CSV en streaming avec toutes les lignes historiques du site. Chaque ligne correspond à une heure.

```bash
curl "http://127.0.0.1:8000/dataclean/allbyprm?prm=30000250086126" -o historique.csv
```

---

### Historique Enedis + météo par PRM — JSON

```
GET /dataclean/allbyprm-json?prm=<14_chiffres>
```

Retourne la même donnée au format JSON. C'est le format utilisé par `api-inference` lors de la synchronisation.

```bash
curl "http://127.0.0.1:8000/dataclean/allbyprm-json?prm=30000250086126"
```

Réponse (structure) :

```json
{
  "prm": "30000250086126",
  "count": 17520,
  "rows": [
    {"timestamp": "2023-01-01T00:00:00", "puissance": 0.42, "temperature": 5.1, ...},
    ...
  ]
}
```

---

### Prévisions météo futures — CSV

```
GET /dataclean/previsions-meteo
```

Exporte la table des prévisions météo disponibles (horizon utilisé par le modèle pour la prédiction).

---

### Table des sites — CSV

```
GET /dataclean/sites
```

Liste tous les sites (PRM) disponibles avec leurs métadonnées.

---

### Prix spot — CSV

```
GET /dataclean/prixspot
```

Exporte les prix spot de l'électricité (utilisés dans le module de calcul de coûts).

---

## Exemple Python

```python
import requests

url = "http://127.0.0.1:8000/dataclean/allbyprm-json"
params = {"prm": "30000250086126"}

response = requests.get(url, params=params, timeout=60)
response.raise_for_status()

payload = response.json()
print("PRM:", payload["prm"])
print("Nombre de lignes:", payload["count"])
```

---

## Déploiement Docker

```bash
# Construire l'image
docker build -t api-dataclean .

# Lancer le conteneur
docker run -p 8000:8000 --env-file .env api-dataclean
```

En production via `docker-compose.yml`, l'image est construite automatiquement et exposée sur le port 8000.

---

## Dépannage

| Erreur | Cause | Solution |
|---|---|---|
| `503 Base de données non disponible` | Variables DB absentes ou incorrectes | Vérifier `.env` + driver ODBC |
| `500 Erreur lors de l'export` | Table Fabric introuvable | Vérifier le schéma et les droits |
| L'API ne démarre pas | Environnement non activé | Vérifier `pip install -r requirements.txt` |
| PRM introuvable | Mauvais identifiant | Le PRM doit contenir exactement 14 chiffres |
