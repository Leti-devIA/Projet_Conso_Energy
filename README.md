# Projet Conso Energ

Prévision de consommation énergétique horaire à partir de données Enedis et météo, avec :
- un modèle LSTM (TensorFlow)
- une API FastAPI pour exposer / exporter les données nettoyées.

---

## 1. Architecture du projet

Arborescence logique du dossier `Projet Conso Energ` :

- `Modeles_TimesSeries/`
  - `modele_lstm.ipynb` : notebook principal de modélisation (feature engineering, entraînement, évaluation, sauvegarde).
  - Fichiers de données d’entrée (ex. `dataFE_prm_30000250086126.csv`).
  - Artéfacts de modèle générés par le notebook :
    - `modele_lstm_production.h5` : modèle LSTM entraîné.
    - `scalers_production.pkl` : scalers `StandardScaler` pour X et y.
    - `config_production.json` : configuration modèle (features, hyperparamètres, performance).
    - `sample_prediction.json` : exemple d’entrée/sortie pour tests.
- `enedis-meteo-api/`
  - `.env` : variables d’environnement (connexion BDD, etc.).
  - `requirements.txt` : dépendances Python de l’API.
  - `app/`
    - `main.py` : point d’entrée FastAPI, configuration CORS, montage des routers.
    - `config/database.py` : connexion à la base (Fabric / SQL Server via `pyodbc`).
    - `repository/data_repository.py` : accès aux données (requêtes SQL).
    - `routers/dataclean.py` : endpoints métier (export de données nettoyées, prévisions météo…).
    - `services/csv_export.py` : génération / streaming CSV.
  - `env_api/` : environnement virtuel Python dédié à l’API.
  - `exports/` : CSV produits par l’API (ex. `export_*.csv`).
- Autres fichiers (à la racine ou par dossier) :
  - `.gitignore`, `README.md` (ce fichier)
  - éventuels notebooks ou scripts complémentaires.

---

## 2. Modélisation LSTM (dossier `Modeles_TimesSeries`)

### 2.1. Objectif

Prédire la puissance moyenne horaire (`puissance_moy_heure`) à partir :
- de variables météo (température, humidité, vent, couverture nuageuse…)
- de variables temporelles (heure, jour de semaine, fériés, encodage cyclique)
- de lags et statistiques glissantes de consommation (lags 1, 2, 3, 24, 48, moyennes / std / min / max roulants)
- d’interactions (ex. `temp_x_heure_sin`, `temp_x_heure_cos`).

### 2.2. Contenu du notebook `modele_lstm.ipynb`

Principales étapes :

1. **Chargement & diagnostic des données**
   - Lecture du CSV (données horaires).
   - Conversion en kW, analyse de la plage de valeurs, diagnostics temporels.

2. **Feature engineering**
   - Lags, moyennes glissantes, écarts-types, min/max roulants.
   - Encodage cyclique des heures / jours de semaine.
   - Interactions température × cycles temporels.

3. **Préparation des données**
   - Normalisation avec `StandardScaler` (X et y).
   - Création de séquences temporelles (fenêtre glissante) avec `WINDOW = 48` heures.
   - Split Train / Validation / Test (70 % / 15 % / 15 %).

4. **Définition du modèle**
   - Modèle `Sequential` avec :
     - 1 couche `Bidirectional(LSTM)` + 2 couches LSTM empilées.
     - `Dropout`, régularisation L2.
     - Dense intermédiaire + couche de sortie.
   - Perte Huber (`loss="huber"`) + métrique `mae`.
   - Callbacks : `EarlyStopping`, `ReduceLROnPlateau`, TensorBoard + HParams.

5. **Entraînement & évaluation**
   - Entraînement sur Train/Val.
   - Prédiction sur Test, inverse transform avec `scaler_y`.
   - Clipping à 0 des valeurs négatives.
   - Métriques : MAE, RMSE, MAPE, R².
   - Visualisations :
     - réel vs prédit
     - courbes de loss
     - distributions, scatter, distribution des erreurs.

6. **Importance des features**
   - Permutation Feature Importance sur le set de validation.
   - Visualisation globale + Top 10.

7. **Sauvegarde pour production**
   - Modèle : `modele_lstm_production.h5`
   - Scalers : `scalers_production.pkl`
   - Config : `config_production.json`
   - Sample : `sample_prediction.json`

8. **Fonction de prédiction itérative**
   - `predict_future(...)` :
     - charge modèle + scalers + config,
     - utilise les 48 dernières heures d’historique + météo future,
     - met à jour itérativement les lags/rolling features avec les prédictions,
     - renvoie un `DataFrame` avec `datetime` et `puissance_kw_pred`.

---

## 3. API FastAPI (dossier `enedis-meteo-api`)

### 3.1. Objectif

- Exposer une API permettant :
  - de récupérer / exporter les données nettoyées (Enedis + météo) sous forme de CSV,
  - de préparer les données nécessaires à la modélisation,
  - d’intégrer le projet à d’autres systèmes (BI, scripts batch, etc.).

### 3.2. Endpoints principaux (router `dataclean`)

Selon l’implémentation de `app/routers/dataclean.py`, on trouve typiquement :

- `GET /`
  → route de test / healthcheck (définie dans `main.py`).

- `GET /dataclean/allbyprm`
  → export CSV des lignes pour un PRM donné (table de données nettoyées).

- `GET /dataclean/previsions-meteo`
  → export CSV des prévisions météo.

La réponse peut être un `StreamingResponse` CSV s’appuyant sur `services/csv_export.py`.
Les fichiers exportés sont généralement enregistrés dans `enedis-meteo-api/exports/`.

### 3.3. Connexion base de données

- Gérée dans `app/config/database.py` avec `pyodbc` / `aioodbc`.
- Paramètres de connexion dans `.env` (serveur, database, user, password…).

---

## 4. Mise en place & exécution

### 4.1. Pré-requis

- Python 3.11 recommandé.
- (Optionnel) Microsoft Fabric / SQL Server pour la source de données de l’API.
- `pip` pour l’installation des dépendances.

### 4.2. Lancer l’API FastAPI

Depuis le dossier `enedis-meteo-api` :

1. (Option 1) Activer l’environnement virtuel existant :

   - PowerShell :
     ```powershell
     .\env_api\Scripts\Activate.ps1
     ```
   - CMD :
     ```bat
     env_api\Scripts\activate.bat
     ```

2. Installer les dépendances (si besoin) :

   ```bash
   pip install -r requirements.txt
   ```

3. Lancer le serveur :

   ```bash
   uvicorn app.main:app --reload
   ```

4. Consulter la doc interactive :
   - Swagger UI : `http://localhost:8000/docs`
   - ReDoc : `http://localhost:8000/redoc`

### 4.3. Relancer l’entraînement du modèle

Depuis le dossier `Modeles_TimesSeries` :

1. Créer / activer un environnement Python (si besoin).
2. Installer les dépendances nécessaires (TensorFlow, scikit-learn, matplotlib, pandas…).
3. Lancer Jupyter :

   ```bash
   jupyter notebook
   ```

4. Ouvrir `modele_lstm.ipynb` et exécuter les cellules dans l’ordre.
5. Les fichiers `*.h5`, `*.pkl`, `*.json` sont régénérés à la fin.

---

## 5. Chaîne de bout en bout (vision globale)

1. **Collecte & nettoyage**
   - L’API interroge la base (Enedis + météo), applique le nettoyage, et peut exporter des CSV.
2. **Préparation & entraînement**
   - Les CSV sont chargés dans `modele_lstm.ipynb`.
   - Feature engineering, entraînement LSTM, évaluation.
3. **Industrialisation**
   - Sauvegarde du modèle + scalers + config.
   - Utilisation de `predict_future()` pour produire des prévisions horaires sur un horizon donné (ex. 24h, 15 jours).
4. **Exposition / consommation**
   - Intégration possible :
     - scripts batch qui consomment `predict_future()` et publient les résultats,
     - extension de l’API pour exposer directement des prédictions (à partir du modèle sauvegardé).

---

## 6. Améliorations possibles

- Déplacer `predict_future()` dans un module Python dédié (ex. `Modeles_TimesSeries/prediction_service.py`).
- Créer un endpoint FastAPI de prédiction en temps réel utilisant `modele_lstm_production.h5`.
- Ajout de tests unitaires / tests d’intégration pour :
  - le feature engineering,
  - la fonction de prédiction,
  - les endpoints critiques de l’API.
- Intégration CI/CD (tests + déploiement automatique de l’API / modèle).