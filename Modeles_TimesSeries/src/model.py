"""
Définition de l'architecture du modèle LSTM optimisé.
"""
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Bidirectional
from tensorflow.keras.regularizers import l2
import yaml


def load_config(config_path="config/config.yaml"):
    """Charge la configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def build_lstm_model(input_shape, config_path="config/config.yaml"):
    """
    Construit le modèle LSTM optimisé avec 3 couches.
    
    Architecture :
    - Bidirectional LSTM (96 unités)
    - LSTM (48 unités)
    - LSTM (24 unités)
    - Dense (16 unités)
    - Dense (1 unité) - sortie
    
    Args:
        input_shape: Tuple (window_size, n_features)
        config_path: Chemin vers la configuration
        
    Returns:
        Modèle Keras compilé
    """
    # Charger les hyperparamètres
    config = load_config(config_path)
    model_config = config['model']
    training_config = config['training']
    
    lstm1_units = model_config['lstm1_units']
    lstm2_units = model_config['lstm2_units']
    lstm3_units = model_config['lstm3_units']
    dropout_rate = model_config['dropout_rate']
    l2_reg = model_config['l2_reg']
    learning_rate = training_config['learning_rate']
    
    # Construction du modèle
    model = Sequential([
        # Couche 1 : Bidirectional LSTM
        Bidirectional(
            LSTM(
                lstm1_units,
                return_sequences=True,
                kernel_regularizer=l2(l2_reg),
                recurrent_regularizer=l2(l2_reg)
            ),
            input_shape=input_shape
        ),
        Dropout(dropout_rate),
        
        # Couche 2 : LSTM
        LSTM(
            lstm2_units,
            return_sequences=True,
            kernel_regularizer=l2(l2_reg),
            recurrent_regularizer=l2(l2_reg)
        ),
        Dropout(dropout_rate),
        
        # Couche 3 : LSTM
        LSTM(
            lstm3_units,
            kernel_regularizer=l2(l2_reg),
            recurrent_regularizer=l2(l2_reg)
        ),
        Dropout(dropout_rate),
        
        # Couches denses
        Dense(16, activation='relu', kernel_regularizer=l2(l2_reg)),
        Dense(1)
    ])
    
    # Compilation avec loss Huber (robuste aux outliers)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss=tf.keras.losses.Huber(),
        metrics=['mae']
    )
    
    print("=" * 60)
    print("MODÈLE LSTM CONSTRUIT")
    print("=" * 60)
    print(f"Architecture :")
    print(f"  - Bidirectional LSTM : {lstm1_units} unités")
    print(f"  - LSTM              : {lstm2_units} unités")
    print(f"  - LSTM              : {lstm3_units} unités")
    print(f"  - Dropout           : {dropout_rate}")
    print(f"  - L2 Regularization : {l2_reg}")
    print(f"  - Learning Rate     : {learning_rate}")
    print(f"  - Loss              : Huber")
    print("=" * 60)
    
    return model


def get_model_summary(model):
    """
    Affiche et retourne le résumé du modèle.
    
    Args:
        model: Modèle Keras
        
    Returns:
        String contenant le résumé
    """
    from io import StringIO
    import sys
    
    # Capturer le résumé
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    model.summary()
    sys.stdout = old_stdout
    
    summary = mystdout.getvalue()
    print(summary)
    return summary


if __name__ == "__main__":
    # Test de construction du modèle
    config = load_config("config/config.yaml")
    window = config['model']['window']
    
    # Utiliser les features optimisées (14 features)
    n_features = len(config['features_optimized'])
    
    print(f"📊 Input shape : ({window}, {n_features})")
    
    # Construire le modèle
    model = build_lstm_model(input_shape=(window, n_features))
    
    # Afficher le résumé
    get_model_summary(model)
    
    # Afficher le nombre de paramètres
    total_params = model.count_params()
    print(f"\n🔢 Nombre total de paramètres : {total_params:,}")
