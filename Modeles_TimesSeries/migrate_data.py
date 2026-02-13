"""
Script de migration pour organiser les fichiers CSV existants dans la nouvelle structure.

Ce script copie les fichiers CSV depuis le dossier data/dataclean vers la nouvelle
structure data/raw (sites, meteo, prix).

Usage:
    python migrate_data.py
"""
import shutil
from pathlib import Path
import sys

# Chemins
ROOT = Path(__file__).parent
OLD_DATA_DIR = ROOT.parent / "data" / "dataclean"
NEW_DATA_DIR = ROOT / "data" / "raw"

SITES_DIR = NEW_DATA_DIR / "sites"
METEO_DIR = NEW_DATA_DIR / "meteo"
PRIX_DIR = NEW_DATA_DIR / "prix"


def create_directories():
    """Crée les répertoires de la nouvelle structure."""
    print("📁 Création de la structure de dossiers...")
    SITES_DIR.mkdir(parents=True, exist_ok=True)
    METEO_DIR.mkdir(parents=True, exist_ok=True)
    PRIX_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✅ Dossiers créés :")
    print(f"   - {SITES_DIR}")
    print(f"   - {METEO_DIR}")
    print(f"   - {PRIX_DIR}")


def migrate_site_files():
    """Migre les fichiers de sites (dataclean_prm_*.csv)."""
    if not OLD_DATA_DIR.exists():
        print(f"⚠️ Le dossier {OLD_DATA_DIR} n'existe pas")
        return 0

    print(f"\n📂 Migration des fichiers de sites depuis {OLD_DATA_DIR}...")

    # Chercher tous les fichiers dataclean_prm_*.csv
    site_files = list(OLD_DATA_DIR.glob("dataclean_prm_*.csv"))

    if not site_files:
        print("⚠️ Aucun fichier de site trouvé")
        return 0

    copied = 0
    for file in site_files:
        dest = SITES_DIR / file.name
        if dest.exists():
            print(f"⏭️  {file.name} existe déjà, ignoré")
        else:
            shutil.copy2(file, dest)
            print(f"✅ Copié : {file.name}")
            copied += 1

    return copied


def migrate_meteo_files():
    """Migre les fichiers météo."""
    if not OLD_DATA_DIR.exists():
        return 0

    print(f"\n🌤️  Migration des fichiers météo...")

    # Fichiers météo possibles
    meteo_files = [
        "previsions_meteo.csv",
        "meteo.csv",
        "meteo_moyennes_3ans.csv"
    ]

    copied = 0
    for filename in meteo_files:
        source = OLD_DATA_DIR / filename
        if source.exists():
            dest = METEO_DIR / filename
            if dest.exists():
                print(f"⏭️  {filename} existe déjà, ignoré")
            else:
                shutil.copy2(source, dest)
                print(f"✅ Copié : {filename}")
                copied += 1

    # Chercher aussi dans data/raw existant
    old_raw = ROOT / "data" / "raw"
    if old_raw.exists():
        for filename in meteo_files:
            source = old_raw / filename
            if source.exists():
                dest = METEO_DIR / filename
                if not dest.exists():
                    shutil.copy2(source, dest)
                    print(f"✅ Copié depuis data/raw : {filename}")
                    copied += 1

    return copied


def migrate_prix_files():
    """Migre les fichiers de prix."""
    if not OLD_DATA_DIR.exists():
        return 0

    print(f"\n💰 Migration des fichiers de prix...")

    # Fichiers de prix possibles
    prix_files = [
        "prix_spot.csv",
        "prix_electricite.csv",
        "prix_energie_3_ans.csv"
    ]

    copied = 0
    for filename in prix_files:
        source = OLD_DATA_DIR / filename
        if source.exists():
            dest = PRIX_DIR / filename
            if dest.exists():
                print(f"⏭️  {filename} existe déjà, ignoré")
            else:
                shutil.copy2(source, dest)
                print(f"✅ Copié : {filename}")
                copied += 1

    return copied


def verify_migration():
    """Vérifie que la migration s'est bien passée."""
    print("\n" + "=" * 60)
    print("VÉRIFICATION DE LA MIGRATION")
    print("=" * 60)

    # Compter les fichiers
    sites = list(SITES_DIR.glob("*.csv"))
    meteo = list(METEO_DIR.glob("*.csv"))
    prix = list(PRIX_DIR.glob("*.csv"))

    print(f"\n📊 Résumé :")
    print(f"   Sites : {len(sites)} fichier(s)")
    for f in sites:
        print(f"      - {f.name}")

    print(f"   Météo : {len(meteo)} fichier(s)")
    for f in meteo:
        print(f"      - {f.name}")

    print(f"   Prix  : {len(prix)} fichier(s)")
    for f in prix:
        print(f"      - {f.name}")

    # Test avec le DataLoader
    print("\n🧪 Test avec le DataLoader...")
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from data_loader import get_data_loader

        loader = get_data_loader('csv', config_path='config/config.yaml')
        available_sites = loader.list_available_sites()

        print(f"✅ DataLoader OK : {len(available_sites)} site(s) détecté(s)")
        for prm in available_sites:
            print(f"      - PRM: {prm}")

    except Exception as e:
        print(f"⚠️ Erreur lors du test DataLoader : {e}")


def main():
    """Point d'entrée principal."""
    print("\n" + "🚀" * 30)
    print("MIGRATION DES DONNÉES VERS LA NOUVELLE STRUCTURE")
    print("🚀" * 30 + "\n")

    # Créer les dossiers
    create_directories()

    # Migrer les fichiers
    sites_copied = migrate_site_files()
    meteo_copied = migrate_meteo_files()
    prix_copied = migrate_prix_files()

    # Vérification
    verify_migration()

    # Résumé
    print("\n" + "✅" * 30)
    print("MIGRATION TERMINÉE")
    print("✅" * 30)
    print(f"\n📊 Total : {sites_copied + meteo_copied + prix_copied} fichier(s) copié(s)")
    print(f"   - Sites : {sites_copied}")
    print(f"   - Météo : {meteo_copied}")
    print(f"   - Prix  : {prix_copied}")

    if sites_copied > 0:
        print("\n💡 Prochaines étapes :")
        print("   1. Vérifiez que tous vos fichiers sont présents")
        print("   2. Testez avec : python main.py list-sites")
        print("   3. Entraînez un modèle : python main.py train --prm XXXXX")
    else:
        print("\n⚠️ Aucun fichier n'a été copié.")
        print("   Assurez-vous que vos fichiers CSV sont dans :")
        print(f"   {OLD_DATA_DIR}")
        print("   Ou copiez-les manuellement dans :")
        print(f"   {SITES_DIR}")


if __name__ == "__main__":
    main()
