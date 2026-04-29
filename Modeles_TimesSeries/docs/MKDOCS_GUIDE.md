# MkDocs — Documentation technique

## Qu'est-ce que MkDocs ?

**MkDocs** est un générateur de sites statiques conçu pour la documentation de projets. Il convertit des fichiers Markdown en un site web navigable et lisible.

Ce projet utilise un **thème personnalisé** (répertoire `docs/theme/`) pour correspondre à l'identité visuelle du projet.

---

## Structure de la documentation

```
Modeles_TimesSeries/
│
├── mkdocs.yml              # Configuration principale (navigation, thème, extensions)
├── docs/
│   ├── index.md            # Page d'accueil
│   ├── API Dataclean.md
│   ├── API Inference.md
│   ├── DOCKER_NGROK.md
│   ├── PIPELINE_ENTRAINEMENT.md
│   ├── AMELIORATIONS_PROPHET.md
│   ├── GRID_SEARCH_GUIDE.md
│   ├── MLFLOW_GUIDE.md
│   ├── DASHBOARD_GUIDE.md
│   ├── TESTING.md
│   ├── GUIDE_CICD.md
│   ├── FORMULE_COUT_HORAIRE.md
│   ├── MKDOCS_GUIDE.md     # Ce fichier
│   └── theme/              # Thème HTML/CSS personnalisé
```

---

## Installation

```bash
pip install mkdocs
# (déjà inclus dans requirements.txt)
```

---

## Servir la documentation en local

```bash
# Depuis Modeles_TimesSeries/
mkdocs serve
```

Ouvrir : **http://127.0.0.1:8000**

La documentation se recharge automatiquement à chaque modification d'un fichier Markdown.

---

## Générer le site statique

```bash
mkdocs build
```

Les fichiers HTML sont générés dans le répertoire `site/`. Ce répertoire peut être déployé sur n'importe quel hébergeur statique (GitHub Pages, Netlify, S3…).

---

## Configuration (`mkdocs.yml`)

```yaml
site_name: Projet Modèles Time Series
site_description: Documentation technique du projet de prévision énergétique

theme:
  name: null
  custom_dir: docs/theme   # Thème personnalisé

docs_dir: docs

markdown_extensions:
  - admonition             # Blocs d'avertissement (Note, Warning…)
  - tables                 # Tableaux Markdown
  - toc:
      permalink: true      # Liens permanents dans les titres

nav:
  - Accueil: index.md
  - APIs:
      - API Dataclean: API Dataclean.md
      - API Inference: API Inference.md
  - Infrastructure:
      - Docker & Ngrok: DOCKER_NGROK.md
      - CI/CD: GUIDE_CICD.md
  - Machine Learning:
      - Pipeline d'entraînement: PIPELINE_ENTRAINEMENT.md
      - Modèle Prophet: AMELIORATIONS_PROPHET.md
      - Grid Search: GRID_SEARCH_GUIDE.md
      - MLflow: MLFLOW_GUIDE.md
  - Application:
      - Dashboard: DASHBOARD_GUIDE.md
      - Formule coût horaire: FORMULE_COUT_HORAIRE.md
  - Tests: TESTING.md
  - MkDocs: MKDOCS_GUIDE.md
```

---

## Ajouter une nouvelle page

1. Créer un fichier `.md` dans `docs/`.
2. L'ajouter dans la section `nav:` de `mkdocs.yml`.
3. Lancer `mkdocs serve` pour prévisualiser.

### Exemple

```yaml
nav:
  - Accueil: index.md
  - Ma nouvelle page: MA_PAGE.md
```

---

## Syntaxe Markdown utile

### Bloc d'avertissement (Admonition)

```markdown
!!! note "Titre de la note"
    Contenu de la note. Utile pour mettre en évidence une information importante.

!!! warning "Attention"
    Ce bloc avertit d'un risque ou d'un comportement inattendu.
```

### Bloc de code avec langue

````markdown
```python
def hello():
    print("Hello")
```
````

### Table

```markdown
| Colonne 1 | Colonne 2 | Colonne 3 |
|---|---|---|
| valeur A | valeur B | valeur C |
```

---

## Déploiement sur GitHub Pages (optionnel)

```bash
mkdocs gh-deploy
```

Cette commande génère le site statique et le pousse sur la branche `gh-pages` du dépôt GitHub. La documentation sera accessible à l'adresse `https://<username>.github.io/<repo>/`.

Prérequis : avoir configuré GitHub Pages sur le dépôt (Settings → Pages → Source : branche `gh-pages`).
