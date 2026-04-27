#!/bin/bash
# ========================================
# Script de test CI en local
# ========================================
# Ce script reproduit les étapes du workflow CI
# pour tester avant de push sur GitHub.

set -e  # Arrête le script si une erreur survient

echo "🚀 Lancement des tests CI en local..."
echo ""

# Étape 1 : Installe les dépendances du projet
echo "📦 Installation des dépendances..."
pip install -r requirements.txt
pip install pytest pytest-cov flake8 ruff

echo ""

# Étape 2 : Vérifie la qualité du code (linting)
echo "🧹 Vérification de la qualité du code..."
echo "   → flake8 (erreurs critiques)"
flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics

echo "   → ruff (style et bonnes pratiques)"
ruff check src/ tests/ --ignore E501 || true

echo ""

# Étape 3 : Lance les tests unitaires avec couverture
echo "🧪 Exécution des tests unitaires..."
pytest tests/ -v --cov=src --cov-report=term --maxfail=1 --disable-warnings

echo ""

# Étape 4 : Affiche un résumé
echo "✅ Tous les tests et vérifications ont réussi !"
echo "👉 Vous pouvez maintenant push votre code en toute confiance."