#!/bin/bash
set -e  # Arrêter si erreur

# Récupérer la date du dernier commit
BUILD_DATE=$(git log -1 --format=%cI 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)

echo "🔨 Building with BUILD_DATE=$BUILD_DATE"

# Modifier ou ajouter BUILD_DATE dans .env
if grep -q "^BUILD_DATE=" .env 2>/dev/null; then
    # Remplacer la ligne existante (compatible Mac et Linux)
    sed -i.bak "s|^BUILD_DATE=.*|BUILD_DATE=$BUILD_DATE|" .env && rm .env.bak
else
    # Ajouter si inexistant
    echo "BUILD_DATE=$BUILD_DATE" >> .env
fi

echo "✅ BUILD_DATE updated in .env"

echo "✅ Build complete!"
echo "💡 Now run: docker compose up"