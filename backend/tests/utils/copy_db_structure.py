#!/usr/bin/env python3
"""
Script de copie de structure DB (sans les données).

Usage:
    python scripts/copy_db_structure.py

Fonctionnalités:
- Drop la DB de test existante
- Crée toutes les collections (vides)
- Copie tous les indexes depuis la prod
- NE copie PAS les données

Temps estimé : 5-10 secondes
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Charger les variables d'environnement depuis la RACINE du projet
# Le fichier .env est à la racine, pas dans backend/
root_dir = Path(__file__).resolve().parents[2]  # Remonte à la racine du projet
env_file = root_dir / ".env"

print(f"📋 Chargement .env depuis : {env_file}")
load_dotenv(env_file)


# Configuration
MONGODB_USER = os.getenv("MONGODB_USER") or "geoChallengeTracker"
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD") or ""
MONGODB_URI_TPL = (
    os.getenv("MONGODB_URI_TPL")
    or "mongodb+srv://[[MONGODB_USER]]:[[MONGODB_PASSWORD]]@cluster0.u4qprao.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
PROD_DB_NAME = os.getenv("MONGODB_DB", "geoChallenge_Tracker")
TEST_DB_NAME = f"{PROD_DB_NAME}_TEST"

# Construire les URIs
PROD_URI = MONGODB_URI_TPL.replace("[[MONGODB_USER]]", MONGODB_USER).replace(
    "[[MONGODB_PASSWORD]]", MONGODB_PASSWORD
)
TEST_URI = PROD_URI


async def copy_structure():
    """Copie uniquement la structure et les indexes (sans données)."""

    print("=" * 60)
    print("📐 COPIE DE STRUCTURE DE BASE DE DONNÉES")
    print("=" * 60)
    print(f"📋 Source : {PROD_DB_NAME}")
    print(f"📋 Cible  : {TEST_DB_NAME}")
    print("=" * 60)

    prod_client = AsyncIOMotorClient(PROD_URI)
    test_client = AsyncIOMotorClient(TEST_URI)

    prod_db = prod_client[PROD_DB_NAME]
    test_db = test_client[TEST_DB_NAME]

    # Étape 1 : Drop la DB de test
    print("\n🗑️  Étape 1/4 : Suppression de la DB de test...")
    await test_client.drop_database(TEST_DB_NAME)
    print("   ✅ DB de test supprimée")

    # Étape 2 : Lister les collections
    print("\n📋 Étape 2/4 : Récupération des collections...")
    collection_names = await prod_db.list_collection_names()
    collection_names.sort()
    print(f"   ✓ Trouvé {len(collection_names)} collections")

    # Étape 3 : Créer les collections vides
    print("\n📦 Étape 3/4 : Création des collections (vides)...")
    for coll_name in collection_names:
        await test_db.create_collection(coll_name)
        print(f"   ✓ {coll_name}")

    # Étape 4 : Copier les indexes
    print("\n📑 Étape 4/4 : Copie des indexes...")
    total_indexes = 0

    for coll_name in collection_names:
        try:
            # Récupérer les indexes depuis la prod
            indexes_cursor = prod_db[coll_name].list_indexes()
            indexes = await indexes_cursor.to_list(length=None)
            coll_indexes = 0

            for idx in indexes:
                # Skip default _id index
                if idx.get("name") == "_id_":
                    continue

                # Extraire les clés de l'index
                key = idx.get("key", {})
                keys = [(k, v) for k, v in key.items()]

                if keys:
                    await test_db[coll_name].create_index(
                        keys,
                        name=idx.get("name"),
                        unique=idx.get("unique", False),
                        background=idx.get("background", False),
                    )
                    coll_indexes += 1

            if coll_indexes > 0:
                print(f"   ✓ {coll_name}: {coll_indexes} indexes")
                total_indexes += coll_indexes
        except Exception as e:
            print(f"   ⚠️  {coll_name}: Erreur ({e})")

    print(f"\n   📊 Total : {total_indexes} indexes copiés")

    # Cleanup
    prod_client.close()
    test_client.close()

    # Résumé
    print("\n" + "=" * 60)
    print("✅ COPIE DE STRUCTURE TERMINÉE")
    print("=" * 60)
    print(f"📊 Collections : {len(collection_names)} (vides)")
    print(f"📊 Indexes      : {total_indexes}")
    print("=" * 60)
    print(f"\n💡 DB de test prête : {TEST_DB_NAME}")
    print("💡 Pour tester : pytest tests/integration/ -v")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(copy_structure())
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        print("\nVérifie que :")
        print("1. Les variables d'environnement sont correctes dans .env")
        print("2. Tu as accès à MongoDB Atlas")
        print("3. La DB de production existe")
        exit(1)
