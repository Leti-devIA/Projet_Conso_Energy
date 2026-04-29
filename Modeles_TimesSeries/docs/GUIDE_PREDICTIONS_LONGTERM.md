# Guide prédictions long terme

## Objectif
Documenter le processus de génération de prédictions long terme par PRM.

## Commande type
```bash
python main.py predict-longterm --prm <PRM_14_CHIFFRES> --years 3 --add-trend
```

## Vérifications
- Vérifier la présence de l’historique dans `data/processed/`.
- Vérifier la présence du modèle dans `models/saved/`.
- Vérifier les sorties dans `data/predictions/`.

## Liens utiles
- [Workflow multi-sites](WORKFLOW_MULTI_SITES.md)
- [Guide tests](TESTING.md)
