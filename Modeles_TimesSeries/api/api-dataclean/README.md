# 📊 Projet Consommation Energetique - API

API REST FastAPI pour l'export de données de consommation énergétique, météo et prix spot depuis Microsoft Fabric Warehouse.

## 🚀 Fonctionnalités

- Export CSV par PRM, prévisions météo, sites et prix spot
- Streaming en temps réel sans saturation mémoire
- Authentification Azure AD sécurisée
- Traitement optimisé pour gros volumes

## 🏗️ Architecture

```
📁 enedis-meteo-api/
├── 📁 app/
│   ├── 📁 config/
│   │   └── 📄 database.py          # Gestion connexion Microsoft Fabric (pyodbc + async)
│   ├── 📁 routers/
│   │   └── 📄 dataclean.py         # Endpoints API pour données nettoyées
│   ├── 📁 services/
│   │   └── 📄 csv_export.py        # Service d'export CSV avec streaming
│   ├── 📁 repository/
│   │   └── 📄 data_repository.py   # Requêtes SQL vers dbo.ENEDIS_METEO_CLEAN
│   └── 📄 main.py                  # Application FastAPI
├── 📁 env_api/                      # Environnement virtuel Python
├── 📄 .env                          # Variables d'environnement
└── 📄 requirements.txt              # Dépendances Python
```

## 🛠️ Stack Technique

FastAPI 0.104+ · Uvicorn · Microsoft Fabric Warehouse · pyodbc · Azure AD · asyncio

## 🔧 Installation

### 1. Prérequis
- **Python 3.8+**
- **ODBC Driver 17 for SQL Server** ([Télécharger](https://go.microsoft.com/fwlink/?linkid=2249004))
- **Accès à Micros & Démarrage

```bash
# Créer et activer l'environnement virtuel
python -m venv env_api
.\env_api\Scripts\Activate.ps1  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer .env
DB_SERVER=votre-serveur.datawarehouse.fabric.microsoft.com
DB_DATABASE=LH_Projet_Conso_Energie

# Lancer l'API
uvicorn app.main:app --reload --port 8000
```

**Documentation Swagger** : http://127.0.0.1:8000/docs
Point d'entrée de l'API.

#### Réponse
```json
{
  "status": "Bienvenue à l'API de data Enedis-Météo"
}
```

---

### **GET** `/dataclean/allbyprm`

Export complet des données pour un PRM donné au format CSV avec streaming.

#### Paramètres

| Paramètre | Type   | Obligatoire | Description                    |
|-----------|--------|-------------|--------------------------------|
| `prm`     | string | ✅ Oui      | Point de Référence Mesure     |

#### Exemple d'utilisation

```bash
GET /dataclean/allbyprm?prm=30000250086126
```

#### Réponse

- **Format** : CSV (text/csv)
- **Nom du fichier** : `dataclean_prm_{prm}.csv`
- **Mode** : Streaming (téléchargement progressif)
- **Source** : Table `dbo.ENEDIS_METEO_CLEAN`

#### Codes de dataclean/allbyprm`
Export CSV des données pour un PRM spécifique avec streaming.

```bash
curl "http://127.0.0.1:8000/dataclean/allbyprm?prm=30000250086126" -o export.csv
```

**Paramètres** : `prm` (string, obligatoire)
**Fichier** : `dataclean_prm_{prm}.csv`

---

### **GET** `/dataclean/allbyprm-json`

Version JSON de l'endpoint historique par PRM, conçue pour les appels serveur-à-serveur (ex: API d'inférence).

```bash
curl "http://127.0.0.1:8000/dataclean/allbyprm-json?prm=30000250086126"
```

**Paramètres** : `prm` (string, obligatoire)

#### Réponse

```json
{
    "prm": "30000250086126",
    "count": 26304,
    "rows": [
        {
            "datetime": "2025-01-01T00:00:00",
            "puissance_moy_heure": 731.5,
            "temperature": 8.2
        }
    ]
}
```

---

### **GET** `/dataclean/previsions-meteo`
Export CSV de toutes les prévisions météo.

```bash
curl "http://127.0.0.1:8000/dataclean/previsions-meteo" -o previsions_meteo.csv
```

**Fichier** : `previsions_meteo.csv`

---

### **GET** `/dataclean/sites`
Export CSV de tous les sites de l'entreprise.

```bash
curl "http://127.0.0.1:8000/dataclean/sites" -o table_sites.csv
```

**Fichier** : `table_sites.csv`

---

### **GET** `/dataclean/prixspot`
Export CSV des prix spot de l'électricité.

```bash
curl "http://127.0.0.1:8000/dataclean/prixspot" -o prix_spot.csv
```

**Fichier** : `prix_spot.csv`
# Traitement par paquets de 10 000 lignes
batch_size = 10_000
for row in cursor:
    batch.append(row)
    if len(batch) >= batch_size:
        # Envoi du paquet au client
        yield csv_data
```

### Gestion des connexions

```python
class DatabaseManager:
    # Connexion unique réutilisée
    self._connection: Optional[pyodbc.Connection] = None

    # Lock async pour thread-safety
    self._lock = asyncio.Lock()
```

**Caractéristiques** :
- Connexion persistante réutilisée
- Reconnexion automatique en cas d'expiration
- Thread-safe avec asyncio.Lock
- Authentification Azure AD Interactive

### Gestion des erreurs

| Code | Description                    | Cause                              |
|------|--------------------------------|------------------------------------|
| 503  | Base de données non disponible | Connexion Fabric échouée          |
| 500  | Erreur lors de l'export        | Requête SQL invalide, timeout     |
| 422  | Paramètre PRM manquant         | Query parameter non fourni        |

## 📊 Exemples d'utilisation

### cURL
```bash
# Export CSV d'un PRM
curl -X GET "http://127.0.0.1:8000/dataclean/allbyprm?prm=30000250086126" \
     -H "accept: text/csv" \
     --output "dataclean_prm_30000250086126.csv"

# Obtenir les colonnes disponibles
curl -X GET "http://127.0.0.1:8000/dataclean/columns"

# Export de toutes les prévisions météo
curl -X GET "http://127.0.0.1:8000/dataclean/previsions-meteo" \
     -H "accept: text/csv" \
     --output "previsions_meteo.csv"
```

### Python
```python
import requests

# Export CSV avec streaming
url = "http://127.0.0.1:8000/dataclean/allbyprm"
params = {"prm": "30000250086126"}

response = requests.get(url, params=params, stream=True)

if response.status_code == 200:
    with open("dataclean_export.csv", "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("✅ Export terminé !")
else:
    print(f"❌ Erreur {response.status_code}: {response.text}")

# Obtenir les colonnes
columns_response = requests.get("http://127.0.0.1:8000/dataclean/columns")
print(columns_response.json())

# Export des prévisions météo
meteo_response = requests.get("http://127.0.0.1:8000/dataclean/previsions-meteo", stream=True)
if ⚡ Architecture

- **Async** : pyodbc synchrone exécuté dans un executor asyncio
- **Streaming** : StreamingResponse avec traitement par batch (10k lignes)
- **Connexion** : Pool persistant avec reconnexion automatique et Azure AD
- **Performance** : Mémoire constante ~50MB, traitement illimité
```

## 🔒 Sécurité

### Authentification base de données
L'API utilise **Azure Active Directory Interactive** pour se connecter à Microsoft Fabric :
- ✅ Authentification sécurisée via navigateur (première fois)
- ✅ Tokens temporaires réutilisés automatiquement
- ✅ Reconnexion automatique en cas d'expiration
- ✅ Pas de mot de passe stocké en clair

### Connexion réseau
**⚠️ Important** : L'API ne fonctionne que depuis le **réseau d'entreprise** ou via **VPN** :
- Le port 1433 (SQL Server) est bloqué hors réseau interne
- Microsoft Fabric Warehouse est protégé par pare-feu Azure
- Configuration normale pour des données sensibles

### Variables d'environnement
Les informations sensibles sont stockées dans `.env` :
```env
# ⚠️ Ne JAMAIS commiter ce fichier !
DB_SERVER=...
DB_DATABASE=...
```

Ajoutez `.env` à votre `.gitignore` :
```bash
echo ".env" >> .gitignore
```

### CORS
L'API accepte toutes les origines (`allow_origins=["*"]`) :
- ✅ OK pour développement local
- ⚠️ À restreindre en production

### Recommandations production
- [ ] Configurer CORS avec origines spécifiques
- [ ] Ajouter authentification API (JWT, OAuth2)
- [ ] Implémenter rate limiting
- [ ] Logger les accès (audit trail)
- [ ] Utiliser HTTPS (TLS/SSL)

## 📈 Performance

### Optimisations
- **Streaming** : Pas de limitation mémoire
- **Batch processing** : 10 000 lignes par paquet
- **Connexion réutilisée** : Évite les reconnexions multiples
- **Logs optimisés** : Progression toutes les 50 000 lignes

### Métriques typiques
- **100k lignes** : ~30 secondes
- **1M lignes** : ~5 minutes
- **10M lignes** : ~45 minutes
- **Mémoire serveur** : ~50MB constant

## 🐛 Dépannage

### Erreur : "Unable to create process using..."
**Cause** : L'environnement virtuel pointe vers un ancien chemin Python

**Solution** :
```bash
# Désactiver et supprimer l'ancien environnement
deactivate
Remove-Item -Recurse -Force env_api

# Recréer l'environnement
python -m venv env_api
.\env_api\Scripts\Activate
pip install -r requirements.txt
```

### Erreur : "Connection failed: Named Pipes Provider"
**Cause** : Problème de connexion au serveur Microsoft Fabric

**Solutions** :
1. Vérifier que vous êtes sur le **réseau d'entreprise** ou **VPN**
2. Tester la connectivité :
```powershell
Test-NetConnection -ComputerName <votre-serveur>.datawarehouse.fabric.microsoft.com -Port 1433
```
3. Vérifier les variables d'environnement :
```bash
Get-Content .env
```

### Erreur : "Invalid column name 'date_complete'"
**Cause** : La colonne n'existe pas dans la table

**Solution** :
1. Vérifier les colonnes disponibles :
```bash
curl http://127.0.0.1:8000/dataclean/columns
```
2. Utiliser le bon nom de colonne dans vos requêtes

### Vérifier les pilotes ODBC
```bash
# PowerShell
Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}

# Python
python -c "import pyodbc; print(pyodbc.drivers())"

# Doit afficher: ODBC Driver 17 for SQL Server
```

### Test de connexion manuel
```python
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

connection_string = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_DATABASE')};"
    f"Authentication=ActiveDirectoryInteractive;"
    f"Encrypt=yes;"
    f"TrustServerCertificate=no;"
    f"Connection Timeout=60;"
    f"MultiSubnetFailover=True;"
)

try:
    conn = pyodbc.connect(connection_string)
    print("✅ Connexion réussie!")
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 1 * FROM dbo.ENEDIS_METEO_CLEAN")
    print(f"✅ Table accessible!")
    conn.close()
except Exception as e:
    print(f"❌ Erreur: {e}")
```

### Logs de débogage
L'API affiche des logs détaillés dans le terminal :
```
📥 Requête reçue pour PRM: 30000250086126
✅ Connexion établie, exécution de la requête SQL...
📊 Colonnes trouvées: ['prm', 'date', 'heure', ...]
✅ Génération du CSV...
```

En cas d'erreur, la stacktrace complète est affichée.

### Problèmes courants

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| API démarre mais ne se connecte pas | Hors réseau entreprise | Connecter VPN |
| 503 Service Unavailable | Connexion DB échouée | Vérifier .env et réseau |
| 500 Internal Server Error | Colonne inexistante | Vérifier avec `/columns` |
| Import pyodbc failed | Driver ODBC manquant | Installer ODBC Driver 17 |

## 🚀 Déploiement

### Environnement de production

#### 1. Configuration
```bash
# Variables d'environnement
export DB_SERVER="votre-serveur-prod.datawarehouse.fabric.microsoft.com"
export DB_DATABASE="votre-base-prod"
```

#### 2. Démarrage avec Gunicorn (Linux)
```bash
pip install gunicorn

- **Auth** : Azure AD Interactive (tokens temporaires, reconnexion auto)
- **Réseau** : Nécessite réseau entreprise ou VPN
- **Config** : Variables sensibles dans `.env` (ne pas commiter)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### docker-compose.yml
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_SERVER=${DB_SERVER}
      - DB_DATABASE=${DB_DATABASE}
    Problèmes courants

| Erreur | Solution |
|--------|----------|
| Connection failed | Vérifier VPN/réseau entreprise |
| 503 Unavailable | Vérifier `.env` et connexion Azure |
| Unable to create process | Recréer l'environnement : `python -m venv env_api` |
| ODBC Driver missing | [Télécharger ODBC Driver 17](https://go.microsoft.com/fwlink/?linkid=2249004) |

### Test de connexion
```python
import pyodbc, os
from dotenv import load_dotenv

load_dotenv()
conn = pyodbc.connect(
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_DATABASE')};"
    f"Authentication=ActiveDirectoryInteractive;"
)
print("✅ Connexion OK")
```

---

## 📝 Changelog

### Version 1.2.0 (Février 2026)
- ✅ Export des prix spot (`/prixspot`)
- ✅ Export des sites (`/sites`)

### Version 1.1.0 (Janvier 2026)
- ✅ Export prévisions météo (`/previsions-meteo`)
- ✅ Streaming CSV optimisé

### Version 1.0.0 (Janvier 2026)
- ✅ Export CSV par PRM
- ✅ Connexion Microsoft Fabric + Azure AD

---

**Base de données** : `LH_Projet_Conso_Energie` (Microsoft Fabric)
**Version** : 1.2.0
**Dernière mise à jour** : Févr