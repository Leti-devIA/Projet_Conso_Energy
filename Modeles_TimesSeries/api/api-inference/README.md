# 📈 API Inference - Projet Conso Energ

API REST FastAPI qui sert de pont entre :
- l'API de données nettoyées (`api-dataclean`),
- les modèles Prophet entraînés (`models/saved`),
- le dashboard (consommation des prédictions).

## 🚀 Fonctionnalités

- Synchronisation des historiques par PRM depuis `GET /dataclean/allbyprm?prm=...`
- Sauvegarde automatique des historiques dans `data/raw/sites`
- Lancement d'une prédiction Prophet pour un PRM (historique récupéré directement via API dataclean en JSON)
- Retour JSON direct pour le dashboard (sans CSV de sortie)
- Exposition du dernier résultat depuis un cache mémoire API
- Documentation OpenAPI native (`/docs`)

## 🏗️ Architecture (flux simplifié)

1. Dashboard → `POST /predict/prm/{prm}`
2. API Inference → `api-dataclean/dataclean/allbyprm-json?prm=...`
3. API Inference → génération météo + modèle Prophet (en mémoire)
4. API Inference → réponse JSON immédiate de la prédiction
5. (Optionnel) Dashboard → `GET /predictions/prm/{prm}/latest` pour relire le dernier résultat en mémoire

> `POST /sync/prm/{prm}` reste disponible si tu veux conserver une copie locale CSV pour debug/audit.

## 🔐 Authentification

Toutes les routes métier sont protégées par une clé API via header HTTP :

- Header : `X-API-Key`
- Variable d'environnement : `INFERENCE_API_KEY`

Route non protégée : `GET /health`

Exemple `.env` :

```env
INFERENCE_API_KEY=dev-inference-key
DATACLEAN_BASE_URL=http://127.0.0.1:8000
CORS_ORIGINS=http://127.0.0.1:8501
```

## 🛠️ Lancement

Depuis `Modeles_TimesSeries/api/api-inference` :

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Documentation Swagger : `http://127.0.0.1:8001/docs`

---

## 📚 Spécification des endpoints

### **GET** `/health`

Vérifie que l'API est démarrée.

#### Réponse (200)

```json
{
  "status": "ok"
}
```

---

### **POST** `/sync/prm/{prm}`

Synchronise l'historique d'un PRM depuis `api-dataclean` et le sauvegarde localement.

#### Paramètres

| Paramètre | Type   | Obligatoire | Description |
|-----------|--------|-------------|-------------|
| `prm`     | string | ✅ Oui      | Identifiant PRM (14 chiffres) |

#### Headers

| Header      | Obligatoire | Description |
|-------------|-------------|-------------|
| `X-API-Key` | ✅ Oui      | Clé API d'accès |

#### Exemple

```bash
curl -X POST "http://127.0.0.1:8001/sync/prm/30000250086126" \
  -H "X-API-Key: dev-inference-key"
```

#### Réponse (200)

```json
{
  "message": "Synchronisation réussie",
  "prm": "30000250086126",
  "file_path": ".../data/raw/sites/dataclean_prm_30000250086126.csv",
  "rows": 26304
}
```

#### Codes de retour

- `200` : synchronisation OK
- `401` : clé API absente/invalide
- `422` : format PRM invalide
- `502` : API dataclean inaccessible ou en erreur

---

### **POST** `/predict/prm/{prm}`

Lance une prédiction pour un PRM à partir de :
1) l'historique récupéré en direct depuis `api-dataclean` (`/dataclean/allbyprm-json`),
2) la génération météo future,
3) le modèle Prophet du PRM.

Le endpoint retourne directement la série de prédiction en JSON (aucune écriture CSV côté API inference).

#### Paramètres

| Paramètre | Type   | Obligatoire | Description |
|-----------|--------|-------------|-------------|
| `prm`     | string | ✅ Oui      | Identifiant PRM (14 chiffres) |

#### Headers

| Header      | Obligatoire | Description |
|-------------|-------------|-------------|
| `X-API-Key` | ✅ Oui      | Clé API d'accès |

#### Exemple

```bash
curl -X POST "http://127.0.0.1:8001/predict/prm/30000250086126" \
  -H "X-API-Key: dev-inference-key"
```

#### Réponse (200)

```json
{
  "message": "Prédiction générée",
  "prm": "30000250086126",
  "rows": 26280,
  "start": "2026-03-23 00:00:00",
  "end": "2029-03-22 23:00:00",
  "series": [
    {
      "datetime": "2026-03-23 00:00:00",
      "puissance_moy_heure_pred": 731.5,
      "puissance_moy_heure_pred_lower": 690.2,
      "puissance_moy_heure_pred_upper": 778.4,
      "jours_depuis_debut": 1095.0,
      "annee": 2026
    }
  ]
}
```

#### Codes de retour

- `200` : prédiction générée
- `401` : clé API absente/invalide
- `404` : historique dataclean vide ou modèle introuvable
- `422` : format PRM invalide
- `500` : erreur interne pipeline
- `502` : API dataclean inaccessible / en erreur

---

### **GET** `/predictions/prm/{prm}/latest`

Retourne la dernière prédiction calculée et gardée en mémoire par l'API (après un appel POST `/predict/prm/{prm}`).

#### Paramètres

| Paramètre | Type   | Obligatoire | Description |
|-----------|--------|-------------|-------------|
| `prm`     | string | ✅ Oui      | Identifiant PRM (14 chiffres) |

#### Headers

| Header      | Obligatoire | Description |
|-------------|-------------|-------------|
| `X-API-Key` | ✅ Oui      | Clé API d'accès |

#### Exemple

```bash
curl "http://127.0.0.1:8001/predictions/prm/30000250086126/latest" \
  -H "X-API-Key: dev-inference-key"
```

#### Réponse (200)

```json
{
  "message": "Prédiction générée",
  "prm": "30000250086126",
  "rows": 26280,
  "start": "2026-03-23 00:00:00",
  "end": "2029-03-22 23:00:00",
  "series": [
    {
      "datetime": "2026-03-23 00:00:00",
      "puissance_moy_heure_pred": 731.5,
      "puissance_moy_heure_pred_lower": 690.2,
      "puissance_moy_heure_pred_upper": 778.4,
      "jours_depuis_debut": 1095.0,
      "annee": 2026
    }
  ]
}
```

#### Codes de retour

- `200` : lecture OK
- `401` : clé API absente/invalide
- `404` : aucune prédiction en mémoire (il faut lancer POST `/predict/prm/{prm}`)
- `422` : format PRM invalide

---

## 🧪 Tests

```bash
pytest -q
```

Couverture actuelle :
- santé API,
- authentification,
- validation PRM,
- lecture de la dernière prédiction.

## ✅ Alignement C9 (certification)

- API REST exposant des fonctions du modèle IA
- Authentification d'accès (API key)
- Endpoints documentés + OpenAPI (`/docs`)
- Tests automatisés des endpoints principaux

## ⚠️ Limites (version volontairement simple)

- Authentification basique (pas de JWT/OAuth2)
- Pas de rate limiting avancé
- Les prédictions "latest" sont en mémoire uniquement (perdues au redémarrage)

Ce choix est assumé pour garder une solution lisible, pédagogique et présentable en soutenance.

---

## 🔁 Automatisation Fabric (local → OneLake → Notebook)

Quand le SQL endpoint Lakehouse refuse le DML (`24559`), l'API écrit dans `exports/fabric_outbox.jsonl`.

Vous pouvez activer le pipeline 100% automatisé :

1. Upload de l'outbox locale vers OneLake (`Files/exports/fabric_outbox.jsonl`)
2. Déclenchement d'un Notebook Fabric qui ingère l'outbox dans les tables Delta

### Variables `.env`

```env
FABRIC_AUTOMATION_ENABLED=true
FABRIC_TENANT_ID=<tenant-guid>
FABRIC_CLIENT_ID=<app-client-id>
FABRIC_CLIENT_SECRET=<app-secret>

ONELAKE_WORKSPACE_NAME=DATA_PLATEFORME_INGESTION_LXE
ONELAKE_LAKEHOUSE_NAME=LH_Projet_Conso_Energie
ONELAKE_OUTBOX_REMOTE_PATH=Files/exports/fabric_outbox.jsonl

FABRIC_WORKSPACE_ID=<fabric-workspace-id>
FABRIC_NOTEBOOK_ITEM_ID=<fabric-notebook-item-id>
FABRIC_NOTEBOOK_TRIGGER_PAYLOAD_JSON={"executionData":{"parameters":{}}}
```

### Droits requis (service principal)

- Accès `Storage` sur le Lakehouse/OneLake pour écrire dans `Files/...`
- Accès `Run` sur le Notebook Fabric ciblé
- Consentement admin pour les scopes token utilisés par l'API :
  - `https://storage.azure.com/.default`
  - `https://api.fabric.microsoft.com/.default`

### Comportement API

- `POST /models/prm/{prm}/push` :
  - si DML disponible : écrit directement dans Fabric SQL endpoint
  - si erreur `24559` : écrit dans outbox locale, upload OneLake, puis trigger Notebook

- `POST /models/push-all` : même logique pour chaque modèle

---

## 🌐 Mode Pull Fabric (recommandé)

En alternative au trigger depuis l'API locale, Fabric peut venir lire les données directement :

- `GET /fabric-exports/pending?limit=500`
  - retourne les événements outbox non acquittés
  - nécessite header `X-API-Key`

- `POST /fabric-exports/ack`
  - body JSON : `{"event_ids": ["..."]}`
  - supprime les événements traités de l'outbox locale
  - nécessite header `X-API-Key`

Notebook prêt à l'emploi (Fabric pull) :
- `Modeles_TimesSeries/docs annexes/fabric_pull_from_inference_api.ipynb`

Pré-requis réseau :
- l'URL de `api-inference` doit être accessible depuis Fabric (tunnel, endpoint public, ou réseau autorisé)
