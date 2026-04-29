# Dashboard Streamlit

## Rôle

Le dashboard est l'interface de **visualisation métier** du projet. Il permet à un responsable énergétique ou à un data analyst d'explorer les prédictions, de consulter les métriques et d'estimer les coûts sans écrire une ligne de code.

---

## Lancement

```bash
# Depuis Modeles_TimesSeries/
streamlit run dashboard_app.py
```

Le dashboard s'ouvre automatiquement dans le navigateur à l'adresse `http://localhost:8501`.

Prérequis : l'API Inference doit être accessible (locale ou Docker).

---

## Architecture

```
dashboard_app.py
│
├── Connexion à API Inference (http://localhost:8001)
│   ├── GET /models/list           → liste des PRM disponibles
│   ├── GET /predictions/prm/latest → récupère les prédictions
│   └── POST /predict/prm/{prm}   → déclenche une nouvelle prédiction
│
├── Sections du dashboard
│   ├── Sélection du site (PRM)
│   ├── Courbe de prédiction vs historique
│   ├── Métriques de performance (MAE, RMSE, MAPE, R²)
│   ├── Décomposition des composantes Prophet
│   └── Estimateur de coût horaire
```

---

## Fonctionnalités

### 1. Sélection du site

Sélectionnez un PRM dans la liste déroulante. La liste est peuplée dynamiquement depuis `GET /models/list` de l'API Inference.

### 2. Courbe de prédiction

Affiche la série historique de consommation superposée aux prédictions Prophet, avec les **intervalles de confiance** (bande `yhat_lower` / `yhat_upper`).

Les intervalles de confiance représentent la plage dans laquelle la vraie valeur a X% de chances de se trouver. Plus la bande est large, plus le modèle est incertain.

### 3. Métriques de performance

| Métrique | Interprétation |
|---|---|
| MAE | Erreur moyenne en kW — facile à interpréter |
| RMSE | Pénalise les grandes erreurs — sensible aux pics |
| MAPE | Erreur relative en % — attention aux valeurs proches de zéro |
| R² | Coefficient de détermination — 1 = prédiction parfaite |

### 4. Décomposition Prophet

Visualise les composantes extraites par Prophet :

- **Tendance** : évolution long terme
- **Saisonnalité journalière** : profil type d'une journée
- **Saisonnalité hebdomadaire** : différences jour ouvrable / week-end
- **Saisonnalité annuelle** : variations saisonnières
- **Effet jours fériés** : impact des fériés

### 5. Estimateur de coût horaire

Permet d'estimer le coût de l'énergie heure par heure en combinant :

- les prédictions de consommation,
- les prix spot importés,
- les volumes contractuels achetés.

Voir la [Formule coût horaire](FORMULE_COUT_HORAIRE.md) pour le détail du calcul.

---

## Déclencher une prédiction depuis le dashboard

Si aucune prédiction n'est encore disponible pour un PRM, ou si vous souhaitez en générer une nouvelle :

1. Sélectionner le PRM dans la liste.
2. Cliquer sur **"Lancer une prédiction"**.
3. Le dashboard appelle `POST /predict/prm/{prm}` et affiche les résultats après quelques secondes.

---

## Bonnes pratiques d'utilisation

- Filtrer par PRM avant de comparer des profils de consommation.
- Vérifier la cohérence entre l'horizon de prédiction affiché et la période souhaitée.
- Contrôler le R² avant toute décision métier : un R² < 0.85 signifie que le modèle doit être réentraîné ou que les données ont changé.
- Si les métriques se dégradent dans le temps, vérifier si un réentraînement est nécessaire (les patterns de consommation évoluent).

---

## Variables à configurer

Dans `api/api-inference/.env` :

```env
CORS_ORIGINS=http://localhost:8501
```

Cela autorise le dashboard à appeler l'API Inference depuis le navigateur.
