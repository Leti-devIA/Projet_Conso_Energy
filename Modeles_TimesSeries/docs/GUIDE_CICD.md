# CI/CD — Intégration et Déploiement Continus

## Qu'est-ce que le CI/CD ?

Le **CI (Continuous Integration)** automatise les vérifications à chaque commit :

- les tests passent-ils ?
- le code respecte-t-il les conventions de style ?

Le **CD (Continuous Deployment)** automatise la construction et la mise à disposition des artefacts (images Docker) après validation.

> Pour un développeur reprenant le projet : le CI/CD est votre filet de sécurité. Si vous cassez quelque chose, GitHub vous le dit avant que ça n'arrive en production.

---

## Workflows GitHub Actions

Le projet contient 4 workflows dans `.github/workflows/` :

| Fichier | Déclencheur | Rôle |
|---|---|---|
| `ci.yml` | Chaque `git push` | Tests unitaires + linting |
| `cd-api-dataclean.yml` | Manuel ou push `main` | Build + push image `api-dataclean` |
| `cd-api-inference.yml` | Manuel ou push `main` | Build + push image `api-inference` |
| `cd-dashboard.yml` | Manuel ou push `main` | Build + push image `dashboard` |

---

## Workflow CI (`ci.yml`) — Détail

À chaque commit pushé, GitHub Actions :

1. Démarre un runner Ubuntu.
2. Checkout du code.
3. Installation de Python 3.11.
4. Installation des dépendances (`pip install -r requirements.txt`).
5. Vérification du style (`flake8` ou `ruff`).
6. Lancement des tests (`pytest --cov=src`).
7. Affichage du rapport de couverture.

**Résultat visible :** un badge ✅ ou ❌ apparaît sur chaque commit dans l'onglet GitHub Actions.

---

## Workflow CD — Détail

Quand le workflow de déploiement est déclenché :

1. Build de l'image Docker du service concerné.
2. Authentification sur Docker Hub avec les secrets GitHub.
3. Push de l'image sur Docker Hub.

L'image est ensuite disponible pour déploiement sur n'importe quel serveur avec `docker pull`.

---

## Configuration initiale (à faire une seule fois)

### 1. Configurer les secrets GitHub

Aller dans le dépôt GitHub → **Settings** → **Secrets and variables** → **Actions**.

Ajouter obligatoirement :

| Secret | Valeur |
|---|---|
| `DOCKER_USERNAME` | Votre nom d'utilisateur Docker Hub |
| `DOCKER_PASSWORD` | Votre mot de passe Docker Hub |

Sans ces secrets, les workflows CD échouent. Les secrets ne sont jamais visibles en clair dans les logs.

### 2. Créer un compte Docker Hub (si nécessaire)

[https://hub.docker.com](https://hub.docker.com) — gratuit pour les images publiques.

---

## Tester le CI en local avant de pusher

```bash
# Script qui exécute localement les mêmes vérifications que le workflow CI
bash scripts/run_ci_tests.sh
```

Si ce script passe ✅ en local, le pipeline GitHub Actions passera aussi.

---

## Scripts utilitaires

| Script | Rôle |
|---|---|
| `scripts/run_ci_tests.sh` | Teste en local (tests + linting) |
| `scripts/build_and_push.sh` | Build et push les images Docker manuellement |
| `scripts/deploy.sh` | Déploie tout le projet en local |

---

## Flux recommandé

```
1. Développer sur une branche feature/fix
       │
       ▼
2. git push origin ma-branche
  → GitHub Actions CI démarre automatiquement
       │
       ▼
3. Tests passent ✅ → ouvrir Pull Request
  Tests échouent ❌ → corriger et re-pusher
       │
       ▼
4. Merge sur main
  → Workflows CD déclenchés
  → Images Docker buildées et pushées sur Docker Hub
       │
       ▼
5. Déploiement serveur : docker pull + docker compose up
```

---

## Fichier `docker-compose.ci.yml`

Ce fichier est utilisé uniquement pendant la CI. Il démarre les services sans les données réelles ni les connexions Fabric, pour permettre aux tests de tourner dans un environnement contrôlé.

```bash
# Lancer la suite de tests via Docker Compose CI
docker compose -f docker-compose.ci.yml up --abort-on-container-exit
```

---

## Dépannage CI/CD

| Problème | Solution |
|---|---|
| Tests échouent sur GitHub mais passent en local | Vérifier les versions de dépendances (utiliser `pip freeze`) |
| Build Docker échoue | Vérifier `DOCKER_USERNAME` et `DOCKER_PASSWORD` dans les secrets |
| Workflow ne se déclenche pas | Vérifier le `on:` du fichier YAML (branche correcte ?) |
| Coverage trop basse | Écrire des tests pour les modules non couverts |
