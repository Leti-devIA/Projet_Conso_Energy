
# API Dataclean

L'API Dataclean sert à **récupérer et exposer des données déjà pré-nettoyées** stockées dans Microsoft Fabric.

Son rôle principal est de fournir ces données de manière simple pour :

- l'API d'inférence (`api-inference`),
- le dashboard,
- ou des scripts data (analyse, exploration, export).

> Cette API **ne fait pas le nettoyage initial** des données : elle lit des tables déjà préparées en amont.

---

## 1) Objectif pédagogique

Si tu es étudiant en data/IA, retiens ceci :

- `api-dataclean` = **source de vérité des historiques** (Enedis + météo + autres tables utiles),
- elle évite de manipuler directement la base dans chaque script,
- elle standardise l'accès via des endpoints HTTP clairs.

---

## 2) Fonctionnalités

- Export CSV des données d'un site (par PRM)
- Export JSON des données d'un site (pratique pour consommation API → API)
- Export CSV des prévisions météo
- Export CSV de la table des sites
- Export CSV des prix spot
- Endpoint de santé (`/health`)

---

## 3) Structure du projet

```
api-dataclean/
│
├── app/
│   ├── main.py                  # Entrée FastAPI, CORS, startup/shutdown
│   ├── logging_utils.py         # Logs applicatifs
│   ├── config/
│   │   └── database.py          # Connexion DB/Fabric via pyodbc
│   ├── repository/
│   │   └── data_repository.py   # Requêtes SQL
│   ├── routers/
│   │   └── dataclean.py         # Endpoints HTTP
│   └── services/
│       └── csv_export.py        # Streaming CSV
│
├── requirements.txt
├── Dockerfile
├── .env
└── README.md
```

---

## 4) Prérequis

- Python 3.11 recommandé
- `pip`
- ODBC Driver 17 for SQL Server
- Accès réseau à la base Fabric/Warehouse

---

## 5) Configuration (`.env`)

Variables minimales à définir :

```env
DB_SERVER=...
DB_DATABASE=...
DB_USER=...
DB_PASSWORD=...
```

Sans ces variables, l'API démarre mais renverra `503 Base de données non disponible` sur les routes data.

---

## 6) Installation et lancement local

```bash
cd api/api-dataclean
python -m venv env_api
```

- Windows PowerShell :
```powershell
.\env_api\Scripts\Activate.ps1
```

- macOS/Linux :
```bash
source env_api/bin/activate
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Lancer l'API :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

URLs utiles :

- API : http://127.0.0.1:8000
- Swagger : http://127.0.0.1:8000/docs

---

## 7) Endpoints disponibles

### Vue d'ensemble

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/dataclean/allbyprm` | Exporte l'historique d'un PRM au format CSV (`?prm=<PRM_14_chiffres>`). Idéal pour un téléchargement direct et une ouverture dans Excel/BI. |
| GET | `/dataclean/allbyprm-json` | Retourne l'historique d'un PRM au format JSON (`?prm=<PRM_14_chiffres>`), avec `prm`, `count` et `rows`. Endpoint privilégié pour l'intégration applicative (API → API). |
| GET | `/dataclean/allbyprm-json-batch` | Retourne l'historique de plusieurs PRM en un seul appel JSON (`?prms=<PRM1>&prms=<PRM2>...`). Réduit le nombre d'appels réseau côté dashboard ou batch de prédiction. |
| GET | `/dataclean/previsions-meteo` | Exporte les prévisions météo futures au format CSV, utilisées comme variables exogènes pour la prédiction. |
| GET | `/dataclean/sites` | Exporte la table de référence des sites (dont les PRM associés) au format CSV, utile pour le mapping site ↔ point de livraison. |
| GET | `/dataclean/prixspot` | Exporte les prix spot de l'électricité au format CSV, utilisés pour les analyses économiques et la projection de coûts. |
| GET | `/health` | Endpoint de santé de l'API. Permet de vérifier rapidement que le service est opérationnel. |

### Santé
- `GET /health`

Réponse :
```json
{"status": "API dataclean ok"}
```

### Historique Enedis + météo par PRM (CSV)
- `GET /dataclean/allbyprm?prm=<PRM_14_chiffres>`

Exemple :
```bash
curl "http://127.0.0.1:8000/dataclean/allbyprm?prm=30000250086126" -o dataclean_prm.csv
```

### Historique Enedis + météo par PRM (JSON)
- `GET /dataclean/allbyprm-json?prm=<PRM_14_chiffres>`

Exemple :
```bash
curl "http://127.0.0.1:8000/dataclean/allbyprm-json?prm=30000250086126"
```

### Historique Enedis + météo multi-PRM (JSON batch)
- `GET /dataclean/allbyprm-json-batch?prms=<PRM_1>&prms=<PRM_2>`

Exemple :
```bash
curl "http://127.0.0.1:8000/dataclean/allbyprm-json-batch?prms=30000250086126&prms=30000250086127"
```

### Prévisions météo (CSV)
- `GET /dataclean/previsions-meteo`

### Sites (CSV)
- `GET /dataclean/sites`

### Prix spot (CSV)
- `GET /dataclean/prixspot`

---

## 8) Exemple Python (appel JSON)

```python
import requests

url = "http://127.0.0.1:8000/dataclean/allbyprm-json"
params = {"prm": "30000250086126"}

response = requests.get(url, params=params, timeout=60)
response.raise_for_status()

payload = response.json()
print("PRM:", payload["prm"])
print("Nombre de lignes:", payload["count"])
print("Première ligne:", payload["rows"][0] if payload["rows"] else "Aucune")
```

---

## 9) Intégration avec `api-inference`

`api-inference` utilise en particulier :

- `GET /dataclean/allbyprm-json` pour récupérer l'historique,
- puis lancer la prédiction côté modèle.

En Docker Compose, l'URL interne est généralement :

`DATACLEAN_BASE_URL=http://api-dataclean:8000`

---

## 10) Déploiement Docker

Construire l'image :

```bash
docker build -t api-dataclean .
```

Lancer le conteneur :

```bash
docker run -p 8000:8000 --env-file .env api-dataclean
```

---

## 11) Dépannage rapide

### `503 Base de données non disponible`
- Vérifier `DB_SERVER`, `DB_DATABASE`, `DB_USER`, `DB_PASSWORD`
- Vérifier le driver ODBC installé
- Vérifier la connectivité réseau

### `500 Erreur lors de l'export`
- Vérifier le schéma/table côté Fabric
- Vérifier que le PRM demandé existe

### L'API ne démarre pas
- Vérifier l'environnement virtuel actif
- Vérifier l'installation des dépendances (`pip install -r requirements.txt`)

---

## 12) Résumé

`api-dataclean` est l'API de lecture des données pré-nettoyées :

- fiable pour l'usage pipeline,
- simple à appeler,
- pensée pour alimenter l'inférence et le dashboard.
