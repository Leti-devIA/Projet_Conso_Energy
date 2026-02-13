"""
Script pour générer les prédictions long terme pour tous les sites.

Usage:
    python generate_all_predictions.py
"""
import subprocess
import sys
from pathlib import Path

def main():
    """Génère les prédictions pour tous les sites disponibles."""
    print("\n" + "🚀" * 40)
    print("GÉNÉRATION DES PRÉDICTIONS POUR TOUS LES SITES")
    print("🚀" * 40 + "\n")

    # Lister tous les modèles disponibles
    models_dir = Path("models/saved")
    model_files = list(models_dir.glob("lstm_energy_forecast_latest_lstm_energy_forecast_*.h5"))

    # Extraire les PRMs des noms de fichiers
    prms = []
    for model_file in model_files:
        # Format: lstm_energy_forecast_latest_lstm_energy_forecast_30000540191777.h5
        prm = model_file.stem.split("_")[-1]
        prms.append(prm)

    if not prms:
        print("❌ Aucun modèle trouvé dans models/saved/")
        print("\nAssurez-vous d'avoir entraîné au moins un modèle :")
        print("   python main.py train --prm XXXXX")
        sys.exit(1)

    print(f"✅ {len(prms)} modèle(s) trouvé(s) :\n")
    for i, prm in enumerate(prms, 1):
        print(f"  {i}. PRM: {prm}")

    print("\n" + "=" * 80)

    # Générer les prédictions pour chaque site
    success_count = 0
    error_count = 0

    for i, prm in enumerate(prms, 1):
        print(f"\n{'='*80}")
        print(f"SITE {i}/{len(prms)} : PRM {prm}")
        print(f"{'='*80}\n")

        try:
            # Lancer la prédiction
            cmd = [
                "python", "main.py", "predict-longterm",
                "--prm", prm,
                "--years", "3",
                "--add-trend"
            ]

            result = subprocess.run(cmd, check=True, capture_output=False)

            print(f"\n✅ Prédictions générées pour le PRM {prm}")
            success_count += 1

        except subprocess.CalledProcessError as e:
            print(f"\n❌ Erreur pour le PRM {prm}")
            error_count += 1
            continue

    # Résumé
    print("\n" + "=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    print(f"✅ Succès : {success_count}/{len(prms)}")
    if error_count > 0:
        print(f"❌ Erreurs : {error_count}/{len(prms)}")

    print("\n💡 Prochaine étape :")
    print("   streamlit run dashboard_longterm.py")
    print("\n" + "🎉" * 40)


if __name__ == "__main__":
    main()
