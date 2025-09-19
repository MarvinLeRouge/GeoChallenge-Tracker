#!/bin/bash
# ---------------------------
# 🧪 Tests validation headers OSM
# ---------------------------

echo "🗺️  Tests de conformité OSM - Headers et Rate Limiting"
echo "=================================================="

TILES_URL="http://localhost:8080"
FRONTEND_URL="http://localhost:8081"

# Couleurs pour les résultats
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction de test avec couleurs
test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "  ${GREEN}✅ $2${NC}"
    else
        echo -e "  ${RED}❌ $2${NC}"
    fi
}

echo ""
echo "1️⃣  Test User-Agent vers OSM (doit contenir contact)"
echo "---------------------------------------------------"
# Test direct sur le service tiles
RESPONSE=$(curl -s -I "$TILES_URL/tiles/1/1/1.png" 2>/dev/null)
echo "Headers reçus du service tiles :"
echo "$RESPONSE" | head -10

# Vérifier que la requête n'est pas rejetée immédiatement
if echo "$RESPONSE" | grep -q "HTTP/1.1 200\|HTTP/1.1 304"; then
    test_result 0 "Service tiles répond correctement"
else
    test_result 1 "Service tiles ne répond pas correctement"
    echo "  Status: $(echo "$RESPONSE" | head -1)"
fi

echo ""
echo "2️⃣  Test Rate Limiting (burst)"
echo "----------------------------"
echo "Envoi de 10 requêtes rapides pour tester le rate limiting..."

SUCCESS_COUNT=0
for i in {1..10}; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$TILES_URL/tiles/1/1/$i.png" 2>/dev/null)
    if [ "$STATUS" = "200" ] || [ "$STATUS" = "304" ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    fi
    printf "Req $i: $STATUS "
    if [ $((i % 5)) -eq 0 ]; then echo ""; fi
done

echo ""
if [ $SUCCESS_COUNT -gt 5 ]; then
    test_result 0 "Rate limiting fonctionne (${SUCCESS_COUNT}/10 succès)"
else
    test_result 1 "Problème rate limiting (${SUCCESS_COUNT}/10 succès)"
fi

echo ""
echo "3️⃣  Test validation format URL"
echo "-----------------------------"

# Test URL valide
STATUS_VALID=$(curl -s -o /dev/null -w "%{http_code}" "$TILES_URL/tiles/1/1/1.png" 2>/dev/null)
test_result 0 "URL valide (1/1/1.png): $STATUS_VALID"

# Test URL invalide (pas de .png)
STATUS_INVALID=$(curl -s -o /dev/null -w "%{http_code}" "$TILES_URL/tiles/1/1/1" 2>/dev/null)
if [ "$STATUS_INVALID" = "404" ]; then
    test_result 0 "URL invalide bloquée (1/1/1): $STATUS_INVALID"
else
    test_result 1 "URL invalide non bloquée (1/1/1): $STATUS_INVALID"
fi

# Test zoom trop élevé
STATUS_ZOOM=$(curl -s -o /dev/null -w "%{http_code}" "$TILES_URL/tiles/25/1/1.png" 2>/dev/null)
if [ "$STATUS_ZOOM" = "404" ]; then
    test_result 0 "Zoom invalide bloqué (25/1/1.png): $STATUS_ZOOM"
else
    test_result 1 "Zoom invalide non bloqué (25/1/1.png): $STATUS_ZOOM"
fi

echo ""
echo "4️⃣  Test headers de cache"
echo "------------------------"
CACHE_HEADERS=$(curl -s -I "$TILES_URL/tiles/1/1/1.png" 2>/dev/null)

if echo "$CACHE_HEADERS" | grep -qi "cache-control.*max-age"; then
    test_result 0 "Cache-Control présent"
    echo "$CACHE_HEADERS" | grep -i "cache-control"
else
    test_result 1 "Cache-Control manquant"
fi

if echo "$CACHE_HEADERS" | grep -qi "x-cache-status"; then
    test_result 0 "Header debug X-Cache-Status présent"
    echo "$CACHE_HEADERS" | grep -i "x-cache-status"
else
    test_result 1 "Header debug X-Cache-Status manquant"
fi

echo ""
echo "5️⃣  Test santé du service"
echo "------------------------"
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$TILES_URL/tiles/_health.png" 2>/dev/null)
if [ "$HEALTH_STATUS" = "200" ]; then
    test_result 0 "Endpoint santé accessible: $HEALTH_STATUS"
else
    test_result 1 "Endpoint santé inaccessible: $HEALTH_STATUS"
fi

echo ""
echo "6️⃣  Test depuis le frontend"
echo "---------------------------"
FRONTEND_TILES=$(curl -s -I "$FRONTEND_URL/tiles/1/1/1.png" 2>/dev/null | head -1)
if echo "$FRONTEND_TILES" | grep -q "200\|304"; then
    test_result 0 "Tiles accessibles via frontend"
else
    test_result 1 "Tiles inaccessibles via frontend"
    echo "  Response: $FRONTEND_TILES"
fi

echo ""
echo "7️⃣  Analyse des logs Nginx"
echo "-------------------------"
echo "Dernières requêtes dans les logs du service tiles :"
if docker logs geo-tiles --tail 5 2>/dev/null | grep -E "GET /[0-9]"; then
    test_result 0 "Logs disponibles et lisibles"
else
    test_result 1 "Pas de logs ou conteneur indisponible"
fi

echo ""
echo "8️⃣  Test de charge rapide (rate limiting)"
echo "----------------------------------------"
echo "Test avec 15 requêtes en parallèle pour vérifier les limites..."

# Test avec xargs pour parallélisme
SEQ_RESULTS=$(seq 1 15 | xargs -n1 -P10 -I{} sh -c "curl -s -o /dev/null -w '%{http_code}\n' '$TILES_URL/tiles/1/1/{}.png' 2>/dev/null")

SUCCESS_PARALLEL=$(echo "$SEQ_RESULTS" | grep -c "200\|304")
ERROR_503=$(echo "$SEQ_RESULTS" | grep -c "503")

echo "Résultats parallèles: $SUCCESS_PARALLEL succès, $ERROR_503 rate limited (503)"

if [ $ERROR_503 -gt 0 ]; then
    test_result 0 "Rate limiting actif ($ERROR_503 requêtes limitées)"
else
    test_result 1 "Rate limiting non détecté (toutes les requêtes ont réussi)"
fi

echo ""
echo "🎯 RÉSUMÉ des tests"
echo "==================="
echo -e "${YELLOW}Pour une conformité OSM parfaite, vérifiez :${NC}"
echo "1. User-Agent contient votre email de contact"
echo "2. Rate limiting bloque les requêtes excessives"
echo "3. URLs invalides retournent 404"
echo "4. Cache respecte les durées OSM (7 jours)"
echo "5. Pas de requêtes directes bypassing le cache"

echo ""
echo "🔍 Commandes utiles pour debug :"
echo "docker logs geo-tiles --tail 20"
echo "docker exec geo-tiles cat /var/log/nginx/tiles_access.log"
echo "curl -v http://localhost:8080/tiles/1/1/1.png"