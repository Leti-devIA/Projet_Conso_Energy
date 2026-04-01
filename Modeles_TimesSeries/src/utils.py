"""
Fonctions utilitaires communes du projet.

Contenu :
- helpers de configuration et détection des sites,
- fonctions de métriques,
- quelques utilitaires historiques (issus d'anciennes expérimentations).
"""
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import yaml
from pathlib import Path

# ===================== Configuration =====================
def load_config(config_path="config/config.yaml"):
    """Charge le fichier YAML de configuration et le retourne sous forme de dict."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Le fichier de config {config_path} est introuvable")

    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ============================================================
# DÉTECTION AUTOMATIQUE DES PRMs
# ============================================================
def detect_prms(raw_data_dir):
    """Retourne un dict {prm: Path} pour tous les fichiers bruts trouvés."""
    prm_files = {}
    for path in sorted(Path(raw_data_dir).glob("dataclean_prm_*.csv")):
        match = re.search(r'dataclean_prm_(\d+)\.csv$', path.name)
        if match:
            prm_files[match.group(1)] = path
    return prm_files

# ============================================================
# JOURS FÉRIÉS FRANCE
# ============================================================
def build_jour_ferie_index(years):
    """Retourne un set de dates (date uniquement) correspondant aux jours fériés."""
    import holidays
    fr_holidays = holidays.France(years=years)
    return set(fr_holidays.keys())


# ===================== Utilitaire historique (séquences) =====================
def create_sequences(X, y, window):
    """
    Crée des séquences temporelles pour le LSTM.

    Args:
        X: Array des features (n_samples, n_features)
        y: Array de la cible (n_samples, 1)
        window: Taille de la fenêtre temporelle

    Returns:
        Tuple (X_seq, y_seq)
        - X_seq: (n_sequences, window, n_features)
        - y_seq: (n_sequences, 1)
    """
    Xs, ys = [], []
    for i in range(len(X) - window):
        Xs.append(X[i:i+window])
        ys.append(y[i+window])
    return np.array(Xs), np.array(ys)


def calculate_mape(y_true, y_pred):
    """
    Calcule le Mean Absolute Percentage Error.

    Args:
        y_true: Valeurs réelles
        y_pred: Valeurs prédites

    Returns:
        MAPE en pourcentage
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    # Éviter division par zéro
    mask = y_true != 0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100


def evaluate_model(model, X_test, y_test, scaler_y):
    """
    Évalue le modèle sur le test set.

    Args:
        model: Modèle Keras entraîné
        X_test: Features de test
        y_test: Cible de test
        scaler_y: Scaler de la cible

    Returns:
        Dict avec les métriques
    """
    # Prédictions
    y_pred_scaled = model.predict(X_test, verbose=0)

    # Inverse transform
    y_pred = scaler_y.inverse_transform(y_pred_scaled)
    y_true = scaler_y.inverse_transform(y_test)

    # Clipper les valeurs négatives
    y_pred_clipped = np.clip(y_pred, 0, None)

    # Calculer les métriques
    mae = mean_absolute_error(y_true, y_pred_clipped)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred_clipped))
    r2 = r2_score(y_true, y_pred_clipped)
    mape = calculate_mape(y_true, y_pred_clipped)

    # Nombre de prédictions négatives
    nb_negative = (y_pred < 0).sum()

    # Afficher les résultats
    print(f"📊 MAE  : {mae:.2f} kW")
    print(f"📊 RMSE : {rmse:.2f} kW")
    print(f"📊 R²   : {r2:.4f}")
    print(f"📊 MAPE : {mape:.2f}%")
    print(f"📊 Prédictions négatives : {nb_negative} (clippées à 0)")

    metrics = {
        'mae': float(mae),
        'rmse': float(rmse),
        'r2': float(r2),
        'mape': float(mape),
        'negative_predictions': int(nb_negative)
    }

    return metrics


def plot_predictions(y_true, y_pred, title="Prédictions vs Réalité", save_path=None):
    """
    Visualise les prédictions vs valeurs réelles.

    Args:
        y_true: Valeurs réelles
        y_pred: Valeurs prédites
        title: Titre du graphique
        save_path: Chemin pour sauvegarder (optionnel)
    """
    fig, axes = plt.subplots(2, 1, figsize=(15, 10))

    # Graphique 1 : Série temporelle
    axes[0].plot(y_true, label='Réel', alpha=0.7, linewidth=1)
    axes[0].plot(y_pred, label='Prédit', alpha=0.7, linewidth=1)
    axes[0].set_xlabel('Temps (heures)')
    axes[0].set_ylabel('Puissance (kW)')
    axes[0].set_title(f'{title} - Série temporelle')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Graphique 2 : Scatter plot
    axes[1].scatter(y_true, y_pred, alpha=0.5, s=10)
    axes[1].plot([y_true.min(), y_true.max()],
                 [y_true.min(), y_true.max()],
                 'r--', linewidth=2, label='Ligne idéale')
    axes[1].set_xlabel('Valeurs réelles (kW)')
    axes[1].set_ylabel('Valeurs prédites (kW)')
    axes[1].set_title(f'{title} - Corrélation')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✅ Graphique sauvegardé : {save_path}")

    plt.show()


def plot_training_history(history, save_path=None):
    """
    Visualise l'historique d'entraînement.

    Args:
        history: Objet History de Keras
        save_path: Chemin pour sauvegarder (optionnel)
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    # Loss
    axes[0].plot(history.history['loss'], label='Train')
    axes[0].plot(history.history['val_loss'], label='Validation')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Loss')
    axes[0].set_title('Évolution de la Loss')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # MAE
    axes[1].plot(history.history['mae'], label='Train')
    axes[1].plot(history.history['val_mae'], label='Validation')
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('MAE')
    axes[1].set_title('Évolution de la MAE')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✅ Graphique sauvegardé : {save_path}")

    plt.show()


def plot_feature_importance(feature_importance, top_n=15, save_path=None):
    """
    Visualise l'importance des features.

    Args:
        feature_importance: Dict {feature_name: importance_value}
        top_n: Nombre de features à afficher
        save_path: Chemin pour sauvegarder (optionnel)
    """
    # Trier par importance
    sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
    top_features = sorted_features[:top_n]

    names = [f[0] for f in top_features]
    values = [f[1] for f in top_features]

    # Créer le graphique
    fig, ax = plt.subplots(figsize=(12, 8))

    colors = ['#d62728' if v > 20 else '#ff7f0e' if v > 10 else '#2ca02c'
              for v in values]

    bars = ax.barh(names, values, color=colors)
    ax.set_xlabel('Augmentation de MAE quand la feature est permutée (kW)')
    ax.set_title(f'Top {top_n} Features les plus importantes')
    ax.grid(True, axis='x', alpha=0.3)

    # Ajouter les valeurs
    for bar, val in zip(bars, values):
        ax.text(val + 0.5, bar.get_y() + bar.get_height()/2,
                f'{val:.2f}', va='center', fontsize=9)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✅ Graphique sauvegardé : {save_path}")

    plt.show()


def summary_statistics(df, column):
    """
    Affiche les statistiques descriptives d'une colonne.

    Args:
        df: DataFrame
        column: Nom de la colonne
    """
    print(f"\n📊 Statistiques pour '{column}':")
    print(f"   Min      : {df[column].min():.2f}")
    print(f"   Max      : {df[column].max():.2f}")
    print(f"   Moyenne  : {df[column].mean():.2f}")
    print(f"   Médiane  : {df[column].median():.2f}")
    print(f"   Écart-type: {df[column].std():.2f}")
    print(f"   Q1       : {df[column].quantile(0.25):.2f}")
    print(f"   Q3       : {df[column].quantile(0.75):.2f}")


if __name__ == "__main__":
    print("Module utils.py chargé avec succès !")
    print("\nFonctions disponibles :")
    print("  - create_sequences()")
    print("  - calculate_mape()")
    print("  - evaluate_model()")
    print("  - plot_predictions()")
    print("  - plot_training_history()")
    print("  - plot_feature_importance()")
    print("  - summary_statistics()")
