#!/bin/bash
# ========================================
# Script de build et push vers Docker Hub
# ========================================
# Ce script construit les images Docker et les pousse sur Docker Hub.
# Utile pour déployer manuellement.

set -e  # Arrête si une erreur survient

# Variables (modifiez avec votre username Docker Hub)
DOCKER_USERNAME="${DOCKER_USERNAME:-votre-username}"
VERSION="${VERSION:-latest}"

echo "🐳 Build et push des images Docker..."
echo "Username : $DOCKER_USERNAME"
echo "Version  : $VERSION"
echo ""

# Vérifie que le username est défini
if [ "$DOCKER_USERNAME" = "votre-username" ]; then
    echo "❌ Erreur : Définissez votre DOCKER_USERNAME !"
    echo "   export DOCKER_USERNAME=votre-username"
    exit 1
fi

# Étape 1 : Connexion à Docker Hub
echo "🔐 Connexion à Docker Hub..."
if [ -z "$DOCKER_PASSWORD" ]; then
    docker login
else
    echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
fi

echo ""

# Étape 2 : Build API DataClean
echo "🏗️ Build API DataClean..."
cd api/api-dataclean
docker build -t "$DOCKER_USERNAME/api-dataclean:$VERSION" .
cd ../..

echo ""

# Étape 3 : Build API Inference
echo "🏗️ Build API Inference..."
cd api/api-inference
docker build -t "$DOCKER_USERNAME/api-inference:$VERSION" .
cd ../..

echo ""

# Étape 4 : Push vers Docker Hub
echo "📤 Push vers Docker Hub..."
docker push "$DOCKER_USERNAME/api-dataclean:$VERSION"
docker push "$DOCKER_USERNAME/api-inference:$VERSION"

echo ""
echo "✅ Build et push terminés !"
echo "📍 Images disponibles :"
echo "   - $DOCKER_USERNAME/api-dataclean:$VERSION"
echo "   - $DOCKER_USERNAME/api-inference:$VERSION"