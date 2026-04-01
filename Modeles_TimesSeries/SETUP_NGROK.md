# 🚀 Setup ngrok + API local pour Fabric

## 5 min pour tout mettre en place

### 1️⃣ Installer ngrok

```powershell
# via Chocolatey (recommandé)
choco install ngrok

# Ou télécharger : https://ngrok.com/download
```

### 2️⃣ Configurer ngrok token

1. Va sur [ngrok.com](https://ngrok.com) → crée un compte gratuit
2. Dashboard → copy ton **Auth Token**
3. Dans PowerShell :

```powershell
ngrok config add-authtoken <COLLE_TON_TOKEN>
```

### 3️⃣ Démarrer l'infrastructure locale (100% docker)

```powershell
cd "C:\Users\36MONNIE-L\Documents\Projet Conso Energ\Modeles_TimesSeries"

# Démarre API + ngrok + sync automatique URL ngrok -> config/fabric_runtime.json
docker compose --profile local up -d

# Vérifier
docker ps
docker compose logs -f ngrok
docker compose logs ngrok-config-sync
```

### 4️⃣ Tester en local

```powershell
# Récupère l'URL ngrok
ngrok api edges list

# Ou visite : http://localhost:4040 (dashboard ngrok)

# Teste l'API
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/models/list
```

### 5️⃣ Execute sur Fabric

1. Upload `fabric_load_models.ipynb` dans Fabric Workspace
2. Attache ton Lakehouse
3. **Exécute d'un coup** (ou cellule par cellule)

L'API démarre automatiquement, ngrok crée le tunnel, les modèles se chargent.

### 6️⃣ Ce qui est automatisé

Le service Docker `ngrok-config-sync` exécute automatiquement `scripts/sync_ngrok_to_fabric_config.py` et :
- lit l'URL HTTPS active via `http://127.0.0.1:4040/api/tunnels`
- écrit `config/fabric_runtime.json`
- écrit `config/fabric_runtime.env`

Tu peux vérifier :

```powershell
Get-Content .\config\fabric_runtime.json
```

Relancer uniquement la synchro si besoin :

```powershell
docker compose --profile local run --rm ngrok-config-sync
```

Ensuite, copie `config/fabric_runtime.json` dans ton Lakehouse Fabric à cet emplacement :

- `/Files/config/fabric_runtime.json`

Le notebook lit automatiquement ce fichier (variable `FABRIC_RUNTIME_CONFIG_PATH`) et utilise `api_base_url`.

---

## 🐛 Troubleshooting

| Problème | Solution |
|----------|----------|
| **Docker not found** | Installe Docker Desktop |
| **ngrok not found** | `choco install ngrok` |
| **Connexion API timeout** | Vérifie : `docker compose ps` |
| **URL ngrok déjà utilisée** | Compte ngrok gratuit = 1 tunnel max, reset ou upgrade |
| **Credentials Fabric invalides** | Vérifie `.env` / Warehouse details |

---

## 📋 Fichiers clés

- `docker-compose.yml` : API + ngrok
- `.env` : secrets (API_KEY, DB_CREDENTIALS)
- `api/api-inference/.env` : config API (CORS, DATACLEAN_BASE_URL)
- `fabric_load_models.ipynb` : **Ce que tu lances dans Fabric**

---

## 🔄 Workflow

```
Ton PC
  ├─ Docker (API)
  └─ ngrok (tunnel public)
       ↓
       ↓ (URL publique)
       ↓
Fabric Notebook (cloud)
  ├─ Get /models/list
  ├─ Get /models/prm/{prm}
  └─ MERGE → ia_modeles
```
