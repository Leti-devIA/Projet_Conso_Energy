#!/usr/bin/env python
"""
Lanceur de tests (version pédagogique).

But : faciliter l'exécution des tests pendant le développement et la soutenance.

Usage:
    python run_tests.py
    python run_tests.py --coverage
    python run_tests.py --fast
    python run_tests.py --unit
    python run_tests.py --specific test_utils.py
"""

import sys
import subprocess
import argparse
from pathlib import Path

def run_pytest(pytest_args):
    cmd = [sys.executable, "-m", "pytest"] + pytest_args
    print("Commande:", " ".join(cmd))
    result = subprocess.run(cmd)
    return result.returncode

def run_command(cmd, description=""):
    """Exécute une commande shell et retourne le code de sortie."""
    if description:
        print(f"\n{'='*60}")
        print(f"🧪 {description}")
        print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Gestionnaire de tests pour Prophet Energy Forecast"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Générer un rapport de couverture de code",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Exécuter les tests en parallèle",
    )
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Exécuter uniquement les tests unitaires",
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Exécuter uniquement les tests d'intégration",
    )
    parser.add_argument(
        "--specific",
        type=str,
        help="Exécuter un fichier de test spécifique",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Mode silencieux (moins de verbosité)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Mode verbose (plus de détails)",
    )

    args = parser.parse_args()

    # Construire la commande pytest avec l'interpréteur Python actif
    cmd = [sys.executable, "-m", "pytest"]

    # Markers
    if args.unit:
        cmd.extend(["-m", "unit"])
    elif args.integration:
        cmd.extend(["-m", "integration"])

    # Test spécifique
    if args.specific:
        cmd.append(f"tests/{args.specific}")
    else:
        cmd.append("tests")

    # Options de verbosité
    if args.quiet:
        cmd.append("-q")
    elif args.verbose:
        cmd.extend(["-vv", "-s"])
    else:
        cmd.append("-v")

    # Parallélisation
    if args.fast:
        cmd.extend(["-n", "auto"])
        print("⚡ Exécution en parallèle...")

    # Coverage
    if args.coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
        ])

    # Exécuter
    returncode = run_command(cmd, "EXÉCUTION DES TESTS")

    if args.coverage:
        print(f"\n✅ Rapport de couverture généré dans : htmlcov/index.html")

    if returncode == 0:
        print("\n✅ Tous les tests sont passés!")
    else:
        print(f"\n❌ {returncode} test(s) échoué(s)")

    return returncode


if __name__ == "__main__":
    sys.exit(main())
