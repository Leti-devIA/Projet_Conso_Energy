"""
Script de debug métriques (usage pédagogique).

Permet de vérifier rapidement :
- l'alignement temporel entre réel et prédiction,
- les métriques principales,
- un éventuel décalage horaire.
"""

import argparse
import sys
import numpy as np
import pandas as pd

def mae(y, yhat): return np.mean(np.abs(y - yhat))
def rmse(y, yhat): return np.sqrt(np.mean((y - yhat) ** 2))
def mape(y, yhat, eps=1e-6):
    denom = np.maximum(np.abs(y), eps)
    return np.mean(np.abs((y - yhat) / denom)) * 100
def r2(y, yhat):
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

def main(prm):
    y_path = fr"c:\Users\36MONNIE-L\Documents\Projet Conso Energ\Modeles_TimesSeries\data\processed\data_processed_{prm}.csv"
    p_path = fr"c:\Users\36MONNIE-L\Documents\Projet Conso Energ\Modeles_TimesSeries\data\predictions\prophet_predictions_{prm}.csv"

    y_df = pd.read_csv(y_path, parse_dates=["datetime"])
    p_df = pd.read_csv(p_path, parse_dates=["datetime"])

    print(f"[actual] min={y_df['datetime'].min()} max={y_df['datetime'].max()} rows={len(y_df)}")
    print(f"[pred  ] min={p_df['datetime'].min()} max={p_df['datetime'].max()} rows={len(p_df)}")

    df = y_df[["datetime", "puissance_moy_heure"]].merge(
        p_df[["datetime", "puissance_moy_heure_pred"]],
        on="datetime",
        how="inner"
    ).dropna()

    if df.empty:
        print("\n❌ Aucune date commune: impossible de calculer des métriques.")
        print("👉 Compare un fichier de backtest (prédictions sur période historique), pas un forecast futur.")
        sys.exit(1)

    y = df["puissance_moy_heure"].values
    yhat = df["puissance_moy_heure_pred"].values

    print(f"\nLignes évaluées: {len(df)}")
    print(f"MAE  : {mae(y, yhat):.2f}")
    print(f"RMSE : {rmse(y, yhat):.2f}")
    print(f"MAPE : {mape(y, yhat):.2f}%")
    print(f"R2   : {r2(y, yhat):.4f}")
    print(f"% yhat == 0 : {(np.mean(yhat == 0) * 100):.2f}%")

    # test décalage horaire
    best = None
    for h in range(-6, 7):
        s = df.copy()
        s["pred_shift"] = s["puissance_moy_heure_pred"].shift(h)
        s = s.dropna()
        score = rmse(s["puissance_moy_heure"].values, s["pred_shift"].values)
        if best is None or score < best[1]:
            best = (h, score)
    print(f"Meilleur décalage horaire (RMSE): shift={best[0]}h, RMSE={best[1]:.2f}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prm", required=True)
    args = ap.parse_args()
    main(args.prm)