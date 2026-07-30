# Ngrok

---

## 1. C'est quoi, ngrok ?

**ngrok** est un reverse proxy tunnelé : il expose publiquement, via une URL HTTPS, un service qui tourne sur une machine non routable depuis Internet (localhost, derrière un NAT/routeur, sans IP publique).

Concrètement : ton API écoute sur `http://127.0.0.1:8001`. Cette adresse n'est valide que dans l'espace réseau local de la machine — aucune requête externe ne peut l'atteindre, port forwarding ou non, tant qu'aucun tunnel n'est établi.

L'agent ngrok, lancé en local, ouvre une connexion **sortante** persistante vers l'infrastructure ngrok (edge servers). C'est cette connexion sortante — donc jamais bloquée par le NAT/firewall — qui permet ensuite à ngrok de router du trafic entrant vers la machine locale, sans ouverture de port entrant ni IP fixe. En échange, ngrok attribue une URL publique (`https://a1b2c3d4.ngrok-free.app`) qui forward tout le trafic HTTP(S) reçu vers le service local, avec terminaison TLS gérée côté ngrok.

---

## 2. Pourquoi on utilise ngrok dans ce projet

Le notebook `fabric_load_models.ipynb` tourne **dans le cloud**, sur l'infrastructure Microsoft Fabric. Pour charger les modèles de séries temporelles, ce notebook a besoin d'appeler notre API (`/models/list`, `/models/prm/{prm}`, etc.).

Le problème : cette API tourne en local, sur un poste de développement, dans Docker. Fabric ne peut pas résoudre `127.0.0.1:8001` — c'est une adresse loopback, valide uniquement dans le namespace réseau de la machine qui l'exécute. Aucune route réseau, cloud ou non, ne permet d'atteindre cette adresse depuis l'extérieur.

Deux alternatives standards ont été écartées à ce stade du projet :
- **déploiement de l'API sur une infrastructure cloud** (App Service, container cloud, etc.) : overhead de mise en place et de maintenance non justifié à ce stade (CI/CD, gestion des secrets en environnement cloud, coûts d'hébergement),
- **port forwarding manuel sur le routeur / IP fixe** : dépend du réseau (souvent impossible en entreprise), non portable d'un poste à l'autre, expose directement l'IP publique du poste.

ngrok permet de contourner ces contraintes : le tunnel est établi en quelques secondes, à chaque démarrage, sans aucune modification de la configuration réseau du poste ou du routeur. C'est une solution adaptée au **développement et aux tests**, tant que l'API n'est pas hébergée ailleurs qu'en local.

> ⚠️ **Point important** : ngrok est une solution adaptée pour du développement / des démonstrations, pas pour de la production. L'URL change à chaque redémarrage (sauf abonnement payant), et la disponibilité de l'API dépend du PC qui doit rester allumé et connecté.

---

## 3. Comment ça fonctionne, techniquement

```
┌─────────────────────────┐
│         Ton PC           │
│                          │
│  ┌────────────────────┐  │
│  │   API (Docker)     │  │
│  │  127.0.0.1:8001    │  │
│  └─────────┬──────────┘  │
│            │              │
│  ┌─────────▼──────────┐  │
│  │   Agent ngrok       │  │──── Tunnel sécurisé (HTTPS) ────┐
│  │  (tourne en local)  │  │                                  │
│  └──────────────────────┘  │                                  │
└─────────────────────────┘                                  │
                                                               ▼
                                          ┌─────────────────────────────┐
                                          │   Serveurs ngrok (cloud)     │
                                          │  Génèrent une URL publique   │
                                          │  https://xxxx.ngrok-free.app │
                                          └───────────────┬─────────────┘
                                                           │
                                                           ▼
                                          ┌─────────────────────────────┐
                                          │  Fabric Notebook (cloud)     │
                                          │  Appelle l'URL publique      │
                                          │  → redirigé vers ton API     │
                                          └─────────────────────────────┘
```

Étapes du flux :

1. **L'agent ngrok** tourne sur ton PC (ici, dans un conteneur Docker) et ouvre une connexion sortante vers les serveurs de ngrok. C'est important : c'est une connexion **sortante**, donc pas besoin d'ouvrir de port sur ton routeur.
2. Les **serveurs ngrok** (dans le cloud) attribuent une URL publique HTTPS unique.
3. Quand quelqu'un (ici, le notebook Fabric) appelle cette URL publique, la requête voyage jusqu'aux serveurs ngrok, qui la font redescendre par le tunnel jusqu'à l'agent ngrok sur ton PC.
4. L'agent ngrok transmet la requête à l'API locale (`127.0.0.1:8001`), récupère la réponse, et la renvoie par le même chemin.

Tout ça se passe en quelques millisecondes et c'est transparent pour l'API : elle reçoit une requête HTTP normale, sans savoir qu'elle passe par un tunnel.

**Le problème dans notre cas** : l'URL publique change à chaque fois qu'on relance ngrok (avec un compte gratuit). Le notebook Fabric a donc besoin de connaître cette URL à jour à chaque exécution. C'est pour ça qu'on a ajouté un service `ngrok-config-sync` : il va chercher automatiquement l'URL active du tunnel et l'écrit dans un fichier de config que le notebook lit. Voir section 6.

---

## 4. Installer ngrok

```powershell
# via Chocolatey (recommandé)
choco install ngrok

# Ou télécharger directement : https://ngrok.com/download
```

## 5. Configurer ton token ngrok

1. Va sur [ngrok.com](https://ngrok.com) → crée un compte gratuit
2. Dashboard → copie ton **Auth Token**
3. Dans PowerShell :

```powershell
ngrok config add-authtoken <COLLE_TON_TOKEN>
```

Ce token identifie ton compte ngrok — sans lui, l'agent ngrok refuse de démarrer.

---

## 6. Démarrer l'infrastructure locale (100% Docker)

```powershell
cd "C:\Users\36MONNIE-L\Documents\Projet Conso Energ\Modeles_TimesSeries"

# Démarre API + ngrok + sync automatique URL ngrok -> config/fabric_runtime.json
docker compose --profile local up -d

# Vérifier que tout tourne
docker ps
docker compose logs -f ngrok
docker compose logs ngrok-config-sync
```

Le service `ngrok-config-sync` exécute automatiquement `scripts/sync_ngrok_to_fabric_config.py`, qui :
- interroge l'API locale de ngrok (`http://127.0.0.1:4040/api/tunnels`) pour récupérer l'URL HTTPS active,
- écrit cette URL dans `config/fabric_runtime.json`,
- écrit aussi `config/fabric_runtime.env`.

Tu peux vérifier le contenu à tout moment :

```powershell
Get-Content .\config\fabric_runtime.json
```

Pour relancer uniquement la synchro (par exemple si l'URL a changé) :

```powershell
docker compose --profile local run --rm ngrok-config-sync
```

**Ensuite**, copie `config/fabric_runtime.json` dans le Lakehouse Fabric, à cet emplacement précis :

```
/Files/config/fabric_runtime.json
```

Le notebook lit automatiquement ce fichier (variable `FABRIC_RUNTIME_CONFIG_PATH`) et récupère `api_base_url` pour savoir où appeler l'API.

---

## 7. Tester en local avant d'aller sur Fabric

```powershell
# Récupère l'URL ngrok active
ngrok api edges list

# Ou visite le dashboard local : http://localhost:4040

# Teste l'API directement
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/models/list
```

## 8. Exécuter sur Fabric

1. Upload `fabric_load_models.ipynb` dans le Fabric Workspace
2. Attache ton Lakehouse
3. Exécute le notebook (d'un coup, ou cellule par cellule)

L'API doit déjà tourner en local et le fichier `fabric_runtime.json` doit déjà être copié dans le Lakehouse — sinon le notebook ne saura pas quelle URL appeler.

---

## 9. Troubleshooting

| Problème | Cause probable | Solution |
|----------|----------------|----------|
| **Docker not found** | Docker Desktop non installé | Installer Docker Desktop |
| **ngrok not found** | ngrok non installé | `choco install ngrok` |
| **Connexion API timeout** | Conteneurs pas démarrés | Vérifier `docker compose ps` |
| **URL ngrok déjà utilisée / refusée** | Compte gratuit = 1 tunnel actif max | Fermer l'ancien tunnel, ou passer sur un compte payant |
| **Le notebook n'arrive pas à joindre l'API** | `fabric_runtime.json` pas à jour ou pas copié dans le Lakehouse | Relancer `ngrok-config-sync`, recopier le fichier dans `/Files/config/` |
| **Credentials Fabric invalides** | `.env` mal configuré | Vérifier `.env` / détails du Warehouse |

---

## 10. Limites à connaître (compte gratuit)

- **1 seul tunnel actif à la fois** — si tu relances ngrok ailleurs, l'ancien tunnel tombe.
- **L'URL change à chaque redémarrage** de l'agent ngrok — c'est pour ça que la synchro automatique vers `fabric_runtime.json` est indispensable.
- **Le PC doit rester allumé et connecté** pendant toute la durée où Fabric doit pouvoir appeler l'API — dès que le PC s'éteint ou que Docker s'arrête, le tunnel meurt et l'API devient injoignable.
- Cette solution est pensée pour du **développement/test**, pas pour un usage en production continue.

---

## 11. Fichiers clés du projet

- `docker-compose.yml` : orchestration API + ngrok + sync
- `.env` : secrets (API_KEY, DB_CREDENTIALS)
- `api/api-inference/.env` : config API (CORS, DATACLEAN_BASE_URL)
- `scripts/sync_ngrok_to_fabric_config.py` : récupère l'URL ngrok active et met à jour la config
- `config/fabric_runtime.json` / `config/fabric_runtime.env` : config générée automatiquement, à copier dans le Lakehouse
- `fabric_load_models.ipynb` : notebook à exécuter dans Fabric