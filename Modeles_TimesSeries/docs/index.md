# Documentation du projet

Cette documentation centralise le fonctionnement du projet **Modeles_TimesSeries** : architecture, entraînement, tests, CI/CD et exploitation.

## Parcours recommandé

1. Lire [DATA_ARCHITECTURE](DATA_ARCHITECTURE.md) pour comprendre les flux de données.
2. Lire [WORKFLOW_MULTI_SITES](WORKFLOW_MULTI_SITES.md) pour l’enchaînement métier.
3. Lire [MLFLOW_GUIDE](MLFLOW_GUIDE.md) pour le suivi d’expériences.
4. Lire [TESTING](TESTING.md) et [GUIDE_CICD](GUIDE_CICD.md) pour la qualité logicielle.

## Convention de rédaction

- 1 fichier = 1 sujet fonctionnel clair.
- Utiliser des titres explicites (`#`, `##`, `###`) avec une hiérarchie régulière.
- Commencer chaque document par : objectif, prérequis, étapes, vérification.
- Ajouter des exemples de commandes testables quand c’est possible.
- Préférer les noms de fichiers en MAJUSCULES avec underscore, comme déjà présent dans ce dossier.

## Commandes locales

Depuis la racine `Modeles_TimesSeries` :

```bash
mkdocs serve
```

Puis ouvrir :

```text
http://127.0.0.1:8000
```

Build statique :

```bash
mkdocs build
```

Le site généré est disponible dans le dossier `site/`.