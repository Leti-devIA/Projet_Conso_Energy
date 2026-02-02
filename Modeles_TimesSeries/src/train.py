"""
Script d'entraînement du modèle LSTM.
"""
import pandas as pd
import numpy as np
import yaml
import pickle
import json
from pathlib import Path
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.callbacks import EarlyStopping, TensorBoard, ReduceLROnPlateau

from model import build_lstm_model
from feature_engineering import get_feature_list
from utils import create_sequences, evaluate_model


def load_config(config_path="config/config.yaml"):
    """Charge la configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def prepare_data(df, config):
    """
    Prépare les données pour l'entraînement.
    
    Args:
        df: DataFrame avec features
        config: Configuration
        
    Returns:
        Tuple (X_train, y_train, X_val, y_val, X_test, y_test, scaler_X, scaler_y)
    """
    print("=" * 60)
    print("PRÉPARATION DES DONNÉES")
    print("=" * 60)
    
    # Récupérer les features optimisées
    features = config['features_optimized']
    target = config['target']
    
    # Vérifier que toutes les features sont présentes
    missing_features = [f for f in features if f not in df.columns]
    if missing_features:
        raise ValueError(f"Features manquantes : {missing_features}")
    
    # Extraire X et y
    df = df.sort_values('datetime').reset_index(drop=True)
    X = df[features].values
    y = df[target].values.reshape(-1, 1)
    
    print(f"✅ Features sélectionnées : {len(features)}")
    print(f"✅ Target : {target}")
    
    # Normalisation avec StandardScaler
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    
    X_scaled = scaler_X.fit_transform(X)
    y_scaled = scaler_y.fit_transform(y)
    
    print(f"✅ Normalisation effectuée (StandardScaler)")
    
    # Créer les séquences
    window = config['model']['window']
    X_seq, y_seq = create_sequences(X_scaled, y_scaled, window)
    
    print(f"✅ Séquences créées (window={window})")
    
    # Split train/val/test
    train_split = config['training']['train_split']
    val_split = config['training']['val_split']
    
    train_size = int(train_split * len(X_seq))
    val_size = int(val_split * len(X_seq))
    
    X_train = X_seq[:train_size]
    y_train = y_seq[:train_size]
    
    X_val = X_seq[train_size:train_size+val_size]
    y_val = y_seq[train_size:train_size+val_size]
    
    X_test = X_seq[train_size+val_size:]
    y_test = y_seq[train_size+val_size:]
    
    print(f"✅ Données splitées :")
    print(f"   Train      : {len(X_train)} séquences ({train_split*100:.0f}%)")
    print(f"   Validation : {len(X_val)} séquences ({val_split*100:.0f}%)")
    print(f"   Test       : {len(X_test)} séquences ({(1-train_split-val_split)*100:.0f}%)")
    print("=" * 60)
    
    return X_train, y_train, X_val, y_val, X_test, y_test, scaler_X, scaler_y


def train_model(data_path, config_path="config/config.yaml", use_tensorboard=True):
    """
    Entraîne le modèle LSTM.
    
    Args:
        data_path: Chemin vers les données avec features
        config_path: Chemin vers la configuration
        use_tensorboard: Activer TensorBoard
        
    Returns:
        Tuple (model, history, metrics_dict)
    """
    # Charger la configuration
    config = load_config(config_path)
    
    # Charger les données
    print(f"📂 Chargement des données : {data_path}")
    df = pd.read_csv(data_path)
    
    # Préparer les données
    X_train, y_train, X_val, y_val, X_test, y_test, scaler_X, scaler_y = prepare_data(df, config)
    
    # Construire le modèle
    n_features = len(config['features_optimized'])
    window = config['model']['window']
    model = build_lstm_model(input_shape=(window, n_features), config_path=config_path)
    
    # Callbacks
    callbacks = []
    
    # Early Stopping
    early_stop = EarlyStopping(
        monitor='val_loss',
        patience=config['callbacks']['early_stopping']['patience'],
        restore_best_weights=config['callbacks']['early_stopping']['restore_best_weights'],
        verbose=1
    )
    callbacks.append(early_stop)
    
    # Reduce Learning Rate
    reduce_lr = ReduceLROnPlateau(
        monitor='val_loss',
        factor=config['callbacks']['reduce_lr']['factor'],
        patience=config['callbacks']['reduce_lr']['patience'],
        min_lr=config['callbacks']['reduce_lr']['min_lr'],
        verbose=1
    )
    callbacks.append(reduce_lr)
    
    # TensorBoard
    if use_tensorboard:
        log_dir = config['callbacks']['tensorboard']['log_dir']
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tensorboard_cb = TensorBoard(
            log_dir=f"{log_dir}/{timestamp}_optimized",
            histogram_freq=1
        )
        callbacks.append(tensorboard_cb)
        print(f"📊 TensorBoard activé : {log_dir}/{timestamp}_optimized")
    
    # Entraînement
    print("\n" + "=" * 60)
    print("ENTRAÎNEMENT DU MODÈLE")
    print("=" * 60)
    
    batch_size = config['training']['batch_size']
    epochs = config['training']['epochs']
    
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        batch_size=batch_size,
        epochs=epochs,
        callbacks=callbacks,
        verbose=1
    )
    
    print("\n" + "=" * 60)
    print("ENTRAÎNEMENT TERMINÉ")
    print("=" * 60)
    
    # Évaluation
    print("\n" + "=" * 60)
    print("ÉVALUATION SUR TEST SET")
    print("=" * 60)
    
    metrics = evaluate_model(model, X_test, y_test, scaler_y)
    
    # Sauvegarder le modèle
    save_model(model, scaler_X, scaler_y, config, metrics)
    
    return model, history, metrics


def save_model(model, scaler_X, scaler_y, config, metrics):
    """
    Sauvegarde le modèle, les scalers et la configuration.
    
    Args:
        model: Modèle Keras entraîné
        scaler_X: Scaler des features
        scaler_y: Scaler de la cible
        config: Configuration
        metrics: Métriques d'évaluation
    """
    print("\n" + "=" * 60)
    print("SAUVEGARDE DU MODÈLE")
    print("=" * 60)
    
    # Créer le dossier de sauvegarde
    save_dir = Path(config['models']['save_dir'])
    save_dir.mkdir(parents=True, exist_ok=True)
    
    model_name = config['models']['model_name']
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Sauvegarder le modèle
    model_path = save_dir / f"{model_name}_{timestamp}.h5"
    model.save(model_path)
    print(f"✅ Modèle sauvegardé : {model_path}")
    
    # Sauvegarder les scalers
    scalers_path = save_dir / f"scalers_{timestamp}.pkl"
    with open(scalers_path, 'wb') as f:
        pickle.dump({'scaler_X': scaler_X, 'scaler_y': scaler_y}, f)
    print(f"✅ Scalers sauvegardés : {scalers_path}")
    
    # Sauvegarder la configuration complète
    config_save = {
        'timestamp': timestamp,
        'model_architecture': {
            'lstm1_units': config['model']['lstm1_units'],
            'lstm2_units': config['model']['lstm2_units'],
            'lstm3_units': config['model']['lstm3_units'],
            'dropout_rate': config['model']['dropout_rate'],
            'l2_reg': config['model']['l2_reg'],
            'window': config['model']['window']
        },
        'training': {
            'batch_size': config['training']['batch_size'],
            'epochs': config['training']['epochs'],
            'learning_rate': config['training']['learning_rate']
        },
        'features': config['features_optimized'],
        'target': config['target'],
        'metrics': metrics
    }
    
    config_path = save_dir / f"config_{timestamp}.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_save, f, indent=4, ensure_ascii=False)
    print(f"✅ Configuration sauvegardée : {config_path}")
    
    # Sauvegarder également en version "latest" pour faciliter l'utilisation
    model.save(save_dir / f"{model_name}_latest.h5")
    with open(save_dir / "scalers_latest.pkl", 'wb') as f:
        pickle.dump({'scaler_X': scaler_X, 'scaler_y': scaler_y}, f)
    with open(save_dir / "config_latest.json", 'w', encoding='utf-8') as f:
        json.dump(config_save, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Version 'latest' créée pour utilisation facile")
    print("=" * 60)


if __name__ == "__main__":
    # Entraîner le modèle
    data_path = "data/processed/data_with_features.csv"
    
    model, history, metrics = train_model(data_path)
    
    print("\n" + "🎉" * 30)
    print("MODÈLE PRÊT POUR LA PRODUCTION")
    print("🎉" * 30)
