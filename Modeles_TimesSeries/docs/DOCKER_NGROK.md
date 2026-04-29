# Docker & Ngrok

## Pourquoi Docker ?

Docker permet de lancer l'ensemble du projet (API Dataclean + API Inference + ngrok) en une seule commande, sans configurer manuellement chaque environnement Python. C'est également le mode d'exécution utilisé en CI/CD et en production.

---

## Docker Compose — Structure

Le projet dispose de deux fichiers `docker-compose` :

| Fichier | Usage |
|---|---|
| `docker-compose.yml` | Orchestration locale complète (APIs + ngrok optionnel) |
| `docker-compose.ci.yml` | Orchestration CI (tests uniquement, sans données réelles) |

### Services définis dans `docker-compose.yml`

```yaml
services:
  api-dataclean:          # API Dataclean sur port 8000
  api-inference:          # API Inference sur port 8001 (dépend de api-dataclean)
  ngrok:                  # Tunnel ngrok (profil "local" uniquement)
  ngrok-config-sync:      # Synchronise l'URL ngrok → fabric_runtime.json
```

---

## Démarrage standard

```bash
# Depuis Modeles_TimesSeries/
docker compose up -d

# Vérifier que tout tourne
docker compose ps

# Voir les logs en temps réel
docker compose logs -f

# Logs d'un seul service
docker compose logs -f api-inference
```

Pour arrêter :

```bash
docker compose down
```

Pour reconstruire les images après modification du code :

```bash
docker compose up --build -d
```

---

## Démarrage avec ngrok (profil "local")

Le profil `local` active deux services supplémentaires : `ngrok` et `ngrok-config-sync`.

```bash
docker compose --profile local up -d
```

Ce profil est utile quand Microsoft Fabric doit appeler l'API Inference depuis le cloud, sans que vous ayez un serveur public déployé.

---

## Variables d'environnement Docker

Chaque service lit son propre fichier `.env` :

- `api/api-dataclean/.env` → service `api-dataclean`
- `api/api-inference/.env` → service `api-inference`

En Docker Compose, la communication inter-services se fait par **nom de service** (réseau interne Docker) :

```env
# Dans api/api-inference/.env pour Docker
DATACLEAN_BASE_URL=http://api-dataclean:8000
```

---

## Architecture réseau Docker

```
Réseau Docker interne (bridge)
│
├── api-dataclean   ← accessible sur http://api-dataclean:8000 depuis api-inference
│                    ← accessible sur http://localhost:8000 depuis l'hôte
│
├── api-inference   ← accessible sur http://api-inference:8001 depuis les autres services
│                    ← accessible sur http://localhost:8001 depuis l'hôte
│
└── ngrok           ← crée un tunnel public vers api-inference:8001
```

---

## Qu'est-ce que ngrok ?

**ngrok** crée un **tunnel HTTPS public** vers un port local. Concrètement :

- Votre PC fait tourner `api-inference` sur le port 8001.
- ngrok génère une URL publique du type `https://abc123.ngrok.io`.
- Fabric (dans le cloud Microsoft) peut appeler cette URL comme si c'était une vraie API déployée.

C'est une solution de développement/démonstration. Elle évite de déployer sur un serveur cloud juste pour tester l'intégration Fabric.

### Schéma de fonctionnement

```
[Microsoft Fabric (cloud)]
        │  HTTPS
        ▼
[https://abc123.ngrok.io]   ← URL publique ngrok
        │
[ngrok agent (Docker)]
        │
[api-inference:8001 (local)]
```

---

## Configuration ngrok

### 1. Obtenir un token

1. Créer un compte sur [ngrok.com](https://ngrok.com) (gratuit).
2. Aller dans le Dashboard → **Your Authtoken**.
3. Copier le token.

### 2. Configurer le token

```powershell
ngrok config add-authtoken <votre_token>
```

Ou définir la variable d'environnement `NGROK_AUTHTOKEN` dans `docker-compose.yml`.

### 3. Démarrer l'infrastructure

```powershell
cd "C:\Users\36MONNIE-L\Documents\Projet Conso Energ\Modeles_TimesSeries"
docker compose --profile local up -d

# Vérifier les logs ngrok
docker compose logs -f ngrok
docker compose logs ngrok-config-sync
```

### 4. Récupérer l'URL publique

```powershell
# Via le tableau de bord local ngrok
# http://localhost:4040

# Via l'API ngrok
curl http://localhost:4040/api/tunnels
```

---

## Synchronisation automatique de l'URL ngrok

Le service `ngrok-config-sync` exécute le script `scripts/sync_ngrok_to_fabric_config.py` qui :

1. lit l'URL HTTPS active via `http://localhost:4040/api/tunnels`,
2. écrit `config/fabric_runtime.json`,
3. écrit `config/fabric_runtime.env`.

Ces fichiers sont ensuite copiés dans votre Lakehouse Fabric à l'emplacement `/Files/config/fabric_runtime.json` pour que les notebooks Fabric connaissent l'URL de l'API.

```powershell
# Vérifier le contenu généré
Get-Content .\config\fabric_runtime.json

# Relancer la synchro manuellement si besoin
docker compose --profile local run --rm ngrok-config-sync
```

---

## Intégration avec Microsoft Fabric

1. Démarrer l'infrastructure locale avec ngrok.
2. Copier `config/fabric_runtime.json` dans le Lakehouse Fabric sous `/Files/config/`.
3. Ouvrir le notebook Fabric (`fabric_load_models.ipynb`).
4. Le notebook lit `fabric_runtime.json` → récupère `api_base_url` → appelle l'API Inference.

---

## Limites du compte ngrok gratuit

| Limite | Valeur |
|---|---|
| Nombre de tunnels simultanés | 1 |
| Bande passante | Non limitée |
| Durée par session | Illimitée |
| URL fixe | Non (change à chaque redémarrage) |

Pour une URL fixe, utilisez un compte ngrok payant ou déployez l'API sur un serveur public.

---

## Dépannage Docker & ngrok

| Problème | Solution |
|---|---|
| `docker: command not found` | Installer Docker Desktop |
| `Port 8000 already in use` | `docker compose down` puis relancer |
| URL ngrok change à chaque redémarrage | Normal sur compte gratuit, re-copier `fabric_runtime.json` |
| `ngrok: authentication failed` | Vérifier `NGROK_AUTHTOKEN` dans l'environnement |
| API Inference ne voit pas API Dataclean | Vérifier `DATACLEAN_BASE_URL=http://api-dataclean:8000` (nom Docker, pas localhost) |
