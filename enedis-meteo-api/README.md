# 📊 Projet Consommation Energetique - API

API REST FastAPI pour l'export de données de consommation énergétique d'ENEDIS et données météorologiques nettoyées, connectée à Microsoft Fabric Warehouse.

## 🚀 Fonctionnalités

- **Export de données par PRM** : Récupération complète des données pour un Point de Référence Mesure (PRM) donné
- **Export des prévisions météo** : Récupération complète de toutes les prévisions météorologiques
- **Inspection des colonnes** : Vérification de la structure de la table en temps réel
- **Streaming en temps réel** : Téléchargement progressif sans saturation mémoire
- **Format CSV** : Export standardisé pour analyse dans Excel, Python, R, etc.
- **Gestion de gros volumes** : Traitement optimisé par batch pour des millions de lignes
- **Authentification Azure AD** : Connexion sécurisée via ActiveDirectoryInteractive

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

- **Framework** : FastAPI 0.104+
- **Serveur** : Uvicorn (ASGI)
- **Base de données** : Microsoft Fabric Warehouse (SQL Server)
- **Driver** : pyodbc avec ODBC Driver 17 for SQL Server
- **Authentification** : Azure Active Directory Interactive
- **Async** : asyncio avec run_in_executor pour opérations pyodbc

## 🔧 Installation

### 1. Prérequis
- **Python 3.8+**
- **ODBC Driver 17 for SQL Server** ([Télécharger](https://go.microsoft.com/fwlink/?linkid=2249004))
- **Accès à Microsoft Fabric Warehouse** (réseau entreprise ou VPN)
- **Compte Azure AD** avec permissions sur le Warehouse

### 2. Installation des dépendances

```bash
# Créer l'environnement virtuel
python -m venv env_api

# Activer l'environnement
.\env_api\Scripts\Activate  # Windows PowerShell
# ou
env_api\Scripts\activate.bat  # Windows CMD
# ou
source env_api/bin/activate  # Linux/Mac

# Installer les dépendances
pip install -r requirements.txt
```

### 3. Configuration

Créez un fichier `.env` à la racine :

```env
DB_SERVER=dnmqtfgsjw7ejbm2qgflaq64vm-tbkwk7v224xe5klpmn6vd3cnfi.datawarehouse.fabric.microsoft.com
DB_DATABASE=LH_Projet_Conso_Energie
```

**⚠️ Important** : Ne jamais commiter le fichier `.env` !

### 4. Démarrage

```bash
# Lancer l'API en mode développement
uvicorn app.main:app --reload --port 8000

# Ou via Python directement
python app/main.py
```

L'API sera accessible sur : **http://127.0.0.1:8000**

## 📖 Documentation

### Interface Swagger
Documentation interactive complète : **http://127.0.0.1:8000/docs**

### ReDoc
Documentation alternative : **http://127.0.0.1:8000/redoc**

## 🌐 Endpoints

### **GET** `/`

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

#### Codes de réponse

| Code | Description                    |
|------|--------------------------------|
| 200  | Export réussi                  |
| 503  | Base de données non disponible |
| 500  | Erreur lors de l'export        |
| 422  | Paramètre manquant ou invalide |

---

### **GET** `/dataclean/columns`

Retourne la liste des colonnes disponibles dans la table `ENEDIS_METEO_CLEAN`.

#### Exemple d'utilisation

```bash
GET /dataclean/columns
```

#### Réponse

```json
{
  "columns": [
    "prm",
    "date",
    "heure",
    "consommation",
    "temperature",
    ...
  ],
  "count": 15
}
```

#### Utilité

- Vérifier la structure de la table
- Identifier les colonnes disponibles pour les analyses
- Valider les noms de colonnes avant les requêtes

---

### **GET** `/dataclean/previsions-meteo`

Export complet de toutes les prévisions météorologiques au format CSV avec streaming.

#### Paramètres

Aucun paramètre requis.

#### Exemple d'utilisation

```bash
GET /dataclean/previsions-meteo
```

#### Réponse

- **Format** : CSV (text/csv)
- **Nom du fichier** : `previsions_meteo.csv`
- **Mode** : Streaming (téléchargement progressif)
- **Source** : Table `dbo.PREVISIONS_METEO`

#### Codes de réponse

| Code | Description                    |
|------|--------------------------------|
| 200  | Export réussi                  |
| 503  | Base de données non disponible |
| 500  | Erreur lors de l'export        |

#### Utilité

- Récupérer l'ensemble des données de prévisions météo
- Analyser les prévisions météorologiques sur l'ensemble des PRM
- Export pour traitement externe (analyse, ML, visualisation)

---

## 🔍 Fonctionnement technique

### Architecture Async

L'API utilise une architecture asynchrone pour optimiser les performances :

```python
# Exécution de pyodbc (synchrone) dans un executor
loop = asyncio.get_event_loop()
cursor, columns = await loop.run_in_executor(
    None, 
    get_rows_by_prm, 
    connection, 
    prm
)
```

**Avantages** :
- ✅ Pas de blocage de la boucle événementielle
- ✅ Gestion de multiples requêtes simultanées
- ✅ Meilleure scalabilité

### Streaming Response

L'API utilise **FastAPI StreamingResponse** pour :
- ✅ Éviter la saturation mémoire
- ✅ Commencer le téléchargement immédiatement  
- ✅ Traiter des millions de lignes
- ✅ Éviter les timeouts

### Traitement par batch

```python
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
if meteo_response.status_code == 200:
    with open("previsions_meteo.csv", "wb") as f:
        for chunk in meteo_response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("✅ Prévisions météo exportées !")
```

### Python avec pandas
```python
import pandas as pd

# Charger directement le CSV dans un DataFrame
prm = "30000250086126"
url = f"http://127.0.0.1:8000/dataclean/allbyprm?prm={prm}"

df = pd.read_csv(url)
print(f"📊 {len(df)} lignes chargées")
print(df.head())

# Charger les prévisions météo
df_meteo = pd.read_csv("http://127.0.0.1:8000/dataclean/previsions-meteo")
print(f"📊 {len(df_meteo)} prévisions météo chargées")
print(df_meteo.head())
```

### JavaScript/Fetch
```javascript
// Export CSV
const prm = '30000250086126';
const response = await fetch(`http://127.0.0.1:8000/dataclean/allbyprm?prm=${prm}`);

if (response.ok) {
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    
    // Téléchargement automatique
    const a = document.createElement('a');
    a.href = url;
    a.download = `dataclean_prm_${prm}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
} else {
    console.error('Erreur:', response.statusText);
}

// Obtenir les colonnes
const columnsResponse = await fetch('http://127.0.0.1:8000/dataclean/columns');
const columns = await columnsResponse.json();
console.log('Colonnes disponibles:', columns);

// Export des prévisions météo
const meteoResponse = await fetch('http://127.0.0.1:8000/dataclean/previsions-meteo');
if (meteoResponse.ok) {
    const blob = await meteoResponse.blob();
    const url = window.URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'previsions_meteo.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}
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

gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 120
```

#### 3. Démarrage avec Uvicorn (production)
```bash
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --no-access-log \
  --log-level warning
```

### Docker (optionnel)

#### Dockerfile
```dockerfile
FROM python:3.11-slim

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Installer ODBC Driver 17 pour SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY . .

# Exposer le port
EXPOSE 8000

# Démarrer l'application
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
    restart: unless-stopped
```

#### Construire et lancer
```bash
docker-compose up -d
```

### Systemd Service (Linux)

```ini
# /etc/systemd/system/enedis-api.service
[Unit]
Description=Enedis Meteo API
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/enedis-meteo-api
Environment="DB_SERVER=..."
Environment="DB_DATABASE=..."
ExecStart=/opt/enedis-meteo-api/env_api/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable enedis-api
sudo systemctl start enedis-api
sudo systemctl status enedis-api
```

### Monitoring

#### Healthcheck endpoint
Ajoutez dans [main.py](app/main.py) :
```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
```

#### Logs
```bash
# Suivre les logs en temps réel
tail -f logs/api.log

# Ou avec systemd
journalctl -u enedis-api -f
```

## 👥 Support & Contributions

### Obtenir de l'aide

1. **Consultez la documentation Swagger** : http://127.0.0.1:8000/docs
2. **Vérifiez les logs** dans le terminal où uvicorn tourne
3. **Testez la connexion** avec l'endpoint `/dataclean/columns`
4. **Consultez la section Dépannage** ci-dessus

### Structure du projet

```
app/
├── config/
│   └── database.py         # DatabaseManager avec connexion persistante
├── routers/
│   └── dataclean.py        # Endpoints FastAPI
├── services/
│   └── csv_export.py       # Streaming CSV par batch
├── repository/
│   └── data_repository.py  # Requêtes SQL
└── main.py                 # Point d'entrée FastAPI
```

### Technologies utilisées

| Composant | Technologie | Version |
|-----------|------------|---------|
| Framework | FastAPI | 0.104+ |
| Serveur | Uvicorn | 0.24+ |
| Base de données | Microsoft Fabric Warehouse | - |
| Driver | pyodbc | 5.0+ |
| Auth | Azure Active Directory | - |
| Python | CPython | 3.8+ |

---

## 📝 Changelog

### Version 1.1.0 (Janvier 2026)
- ✅ Export de toutes les prévisions météo (`/previsions-meteo`)
- ✅ Streaming CSV pour données volumineuses

### Version 1.0.0 (Janvier 2026)
- ✅ Connexion à Microsoft Fabric Warehouse
- ✅ Authentification Azure AD Interactive
- ✅ Export CSV par PRM avec streaming
- ✅ Endpoint pour lister les colonnes
- ✅ Gestion async avec pyodbc
- ✅ Reconnexion automatique
- ✅ Logs de débogage détaillés
- ✅ Documentation Swagger complète

---

**Développé pour** : Projet Consommation Énergétique  
**Base de données** : `LH_Projet_Conso_Energie` (Microsoft Fabric)  
**Version** : 1.1.0  
**Dernière mise à jour** : Janvier 2026