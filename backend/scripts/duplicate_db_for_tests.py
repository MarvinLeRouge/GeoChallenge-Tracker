#!/usr/bin/env python3
"""
Script de duplication de la DB de production vers la DB de test.

Usage:
    python scripts/duplicate_db_for_tests.py

Fonctionnalités:
- Drop la DB de test existante
- Copie toutes les collections depuis la prod
- Copie tous les indexes
- Anonymise les données sensibles (users)
- Affiche la progression

Temps estimé : 30-60 secondes pour 23 Mo
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


# Configuration depuis .env ou variables d'env
MONGODB_USER = os.getenv("MONGODB_USER")
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
TEST_URI = PROD_URI  # Même cluster, juste DB différente


async def duplicate_db():
    """Duplique la DB de production vers la DB de test avec anonymisation."""

    print("=" * 60)
    print("🔄 DUPLICATION DE BASE DE DONNÉES")
    print("=" * 60)
    print(f"📋 Source : {PROD_DB_NAME}")
    print(f"📋 Cible  : {TEST_DB_NAME}")
    print("=" * 60)

    prod_client = AsyncIOMotorClient(PROD_URI)
    test_client = AsyncIOMotorClient(TEST_URI)

    prod_db = prod_client[PROD_DB_NAME]
    test_db = test_client[TEST_DB_NAME]

    # Étape 1 : Drop la DB de test
    print("\n🗑️  Étape 1/5 : Suppression de la DB de test...")
    await test_client.drop_database(TEST_DB_NAME)
    print("   ✅ DB de test supprimée")

    # Étape 2 : Lister les collections
    print("\n📋 Étape 2/5 : Récupération des collections...")
    collection_names = await prod_db.list_collection_names()
    collection_names.sort()  # Tri alphabétique pour affichage propre
    print(f"   ✓ Trouvé {len(collection_names)} collections")

    # Étape 3 : Copier les données
    print("\n📦 Étape 3/5 : Copie des données...")
    total_docs = 0

    for coll_name in collection_names:
        # Récupérer tous les documents de la prod
        docs = await prod_db[coll_name].find().to_list(length=None)

        if not docs:
            # Créer collection vide
            await test_db.create_collection(coll_name)
            print(f"   ✓ {coll_name}: 0 documents (vide)")
            continue

        # Anonymiser les collections sensibles
        if coll_name == "users":
            for doc in docs:
                doc["email"] = f"test_{doc['_id']}@geochallenge.app"
                doc["username"] = f"test_{str(doc['_id'])[:8]}"
                # Garder password_hash pour les tests d'auth
            print(f"   🔒 {coll_name}: {len(docs)} documents (anonymisés)")
        else:
            print(f"   ✓ {coll_name}: {len(docs)} documents")

        # Insérer les documents
        await test_db[coll_name].insert_many(docs)
        total_docs += len(docs)

    print(f"\n   📊 Total : {total_docs} documents copiés")

    # Étape 4 : Copier les indexes
    print("\n📑 Étape 4/5 : Copie des indexes...")
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

                # Skip text indexes (causes issues with weights)
                if idx.get("name", "").startswith("text_"):
                    print(f"   ⚠️  {coll_name}: Skip text index '{idx.get('name')}'")
                    continue

                # Extraire les clés de l'index
                key = idx.get("key", {})
                keys = [(k, v) for k, v in key.items()]

                if keys:
                    try:
                        await test_db[coll_name].create_index(
                            keys,
                            name=idx.get("name"),
                            unique=idx.get("unique", False),
                            background=idx.get("background", False),
                        )
                        coll_indexes += 1
                    except Exception as e:
                        print(f"   ⚠️  {coll_name}: Skip index '{idx.get('name')}' ({e})")

            # Force create 2dsphere index on caches.loc if missing
            if coll_name == "caches":
                try:
                    # Vérifier si l'index 2dsphere existe déjà
                    existing_indexes = await test_db.caches.list_indexes().to_list(length=None)
                    has_2dsphere = any(
                        "2dsphere" in str(idx.get("key", {})) for idx in existing_indexes
                    )

                    if not has_2dsphere:
                        await test_db.caches.create_index(
                            [("loc", "2dsphere")], name="loc_2dsphere"
                        )
                        coll_indexes += 1
                        print(f"   ✓ {coll_name}: Created 2dsphere index on loc")
                except Exception as e:
                    print(f"   ⚠️  {coll_name}: Failed to create 2dsphere index ({e})")

            if coll_indexes > 0:
                print(f"   ✓ {coll_name}: {coll_indexes} indexes")
                total_indexes += coll_indexes
        except Exception as e:
            print(f"   ⚠️  {coll_name}: Erreur ({e})")

    print(f"\n   📊 Total : {total_indexes} indexes copiés")

    # Étape 5 : Vérification
    print("\n✅ Étape 5/5 : Vérification...")
    test_collections = await test_db.list_collection_names()
    test_collections.sort()

    if set(collection_names) == set(test_collections):
        print(f"   ✅ {len(test_collections)} collections vérifiées")
    else:
        print("   ⚠️  Warning: Collections mismatch!")
        print(f"      Prod: {collection_names}")
        print(f"      Test: {test_collections}")

    # Cleanup
    prod_client.close()
    test_client.close()

    # Résumé
    print("\n" + "=" * 60)
    print("✅ DUPLICATION TERMINÉE AVEC SUCCÈS")
    print("=" * 60)
    print(f"📊 Collections : {len(collection_names)}")
    print(f"📊 Documents   : {total_docs}")
    print(f"📊 Indexes      : {total_indexes}")
    print("🔒 Users        : Anonymisés")
    print("=" * 60)
    print(f"\n💡 DB de test prête : {TEST_DB_NAME}")
    print("💡 Pour tester : pytest tests/integration/ -v")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(duplicate_db())
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        print("\nVérifie que :")
        print("1. Les variables d'environnement sont correctes dans .env")
        print("2. Tu as accès à MongoDB Atlas")
        print("3. La DB de production existe")
        exit(1)
