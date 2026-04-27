#!/bin/bash
# ========================================
# Script de déploiement local
# ========================================
# Ce script déploie le projet complet avec Docker Compose.
# Utile pour tester avant le déploiement automatique.

set -e  # Arrête si une erreur survient

echo "🚀 Déploiement du projet Conso Energ..."
echo ""

# Étape 1 : Vérifie que Docker est installé
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé !"
    echo "   Installez Docker : https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✅ Docker détecté"
echo ""

# Étape 2 : Build les images Docker
echo "🏗️ Construction des images Docker..."
docker-compose build

echo ""

# Étape 3 : Arrête les anciens conteneurs
echo "🛑 Arrêt des anciens conteneurs..."
docker-compose down

echo ""

# Étape 4 : Démarre les nouveaux conteneurs
echo "▶️ Démarrage des services..."
docker-compose up -d

echo ""

# Étape 5 : Affiche le statut
echo "📊 Statut des services :"
docker-compose ps

echo ""
echo "✅ Déploiement terminé !"
echo "🌍 Services disponibles :"
echo "   - API DataClean  : http://localhost:8000"
echo "   - API Inference  : http://localhost:8001"
echo "   - Dashboard      : http://localhost:8501"
echo ""
echo "📝 Voir les logs : docker-compose logs -f"