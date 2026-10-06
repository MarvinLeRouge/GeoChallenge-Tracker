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
root_dir = Path(__file__).resolve().parents[3]  # Remonte à la racine du projet
env_file = root_dir / ".env"

print(f"📋 Chargement .env depuis : {env_file}")
load_dotenv(env_file)

# Configuration depuis .env ou variables d'env
MONGODB_USER = os.getenv("MONGODB_USER") or "geoChallengeTracker"
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD") or ""
MONGODB_URI_TPL = (
    os.getenv("MONGODB_URI_TPL")
    or "mongodb+srv://[[MONGODB_USER]]:[[MONGODB_PASSWORD]]@cluster0.u4qprao.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
PROD_DB_NAME = os.getenv("MONGODB_DB", "geoChallenge_Tracker")
PROD_DB_NAME = PROD_DB_NAME.replace("_TEST", "")
TEST_DB_NAME = f"{PROD_DB_NAME}_TEST"

# Construire les URIs
PROD_URI = MONGODB_URI_TPL.replace("[[MONGODB_USER]]", MONGODB_USER).replace(
    "[[MONGODB_PASSWORD]]", MONGODB_PASSWORD
)
TEST_URI = PROD_URI  # Même cluster, juste DB différente


async def _sync_missing_collections(prod_db, test_db, verbose):
    """Create any collection that exists in prod but not yet in the test db.

    Args:
        prod_db: Source (production) database handle.
        test_db: Target (test) database handle.
        verbose: Print progress to stdout.

    Returns:
        list: `prod_collection_names`, as seen before creating the missing ones.
    """
    if verbose:
        print("\n📋 Étape 1/4 : Récupération des collections...")
    prod_collection_names = await prod_db.list_collection_names()
    test_collection_names = await test_db.list_collection_names()
    missing_collection_names = list(set(prod_collection_names) - set(test_collection_names))
    missing_collection_names.sort()  # Tri alphabétique pour affichage propre
    nb_missing_collections = len(missing_collection_names)
    for i, coll_name in enumerate(missing_collection_names):
        await test_db.create_collection(coll_name)
        if verbose:
            print(f"   ✓ Collection {coll_name} créée : {i + 1} / {nb_missing_collections}")
    return prod_collection_names


async def _copy_collection_indexes(prod_db, test_db, coll_name, verbose):
    """Copy all (non-default, non-text) indexes of one collection from prod to test.

    Args:
        prod_db: Source database handle.
        test_db: Target database handle.
        coll_name: Collection name.
        verbose: Print progress to stdout.

    Returns:
        int: Number of indexes actually created.
    """
    coll_indexes = 0
    # Récupérer les indexes depuis la prod
    indexes_cursor = prod_db[coll_name].list_indexes()
    indexes = await indexes_cursor.to_list(length=None)

    for idx in indexes:
        # Skip default _id index
        if idx.get("name") == "_id_":
            continue

        # Skip text indexes (causes issues with weights)
        if idx.get("name", "").startswith("text_"):
            if verbose:
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
                if verbose:
                    print(f"   ⚠️  {coll_name}: Skip index '{idx.get('name')}' ({e})")

    return coll_indexes


async def _ensure_caches_2dsphere_index(test_db, verbose):
    """Force-create the `caches.loc` 2dsphere index if it's missing.

    Args:
        test_db: Target database handle.
        verbose: Print progress to stdout.

    Returns:
        int: 1 if the index was created, 0 otherwise.
    """
    try:
        # Vérifier si l'index 2dsphere existe déjà
        existing_indexes = await test_db.caches.list_indexes().to_list(length=None)
        has_2dsphere = any("2dsphere" in str(idx.get("key", {})) for idx in existing_indexes)

        if has_2dsphere:
            return 0

        await test_db.caches.create_index([("loc", "2dsphere")], name="loc_2dsphere")
        if verbose:
            print("   ✓ caches: Created 2dsphere index on loc")
        return 1
    except Exception as e:
        if verbose:
            print(f"   ⚠️  caches: Failed to create 2dsphere index ({e})")
        return 0


async def _copy_all_indexes(prod_db, test_db, prod_collection_names, verbose):
    """Copy indexes for every prod collection, plus the caches 2dsphere special case.

    Args:
        prod_db: Source database handle.
        test_db: Target database handle.
        prod_collection_names: Collections to copy indexes for.
        verbose: Print progress to stdout.

    Returns:
        int: Total number of indexes created.
    """
    if verbose:
        print("\n📑 Étape 2/4 : Copie des indexes...")
    total_indexes = 0

    for coll_name in prod_collection_names:
        try:
            coll_indexes = await _copy_collection_indexes(prod_db, test_db, coll_name, verbose)

            # Force create 2dsphere index on caches.loc if missing
            if coll_name == "caches":
                coll_indexes += await _ensure_caches_2dsphere_index(test_db, verbose)

            if coll_indexes > 0:
                if verbose:
                    print(f"   ✓ {coll_name}: {coll_indexes} indexes")
                total_indexes += coll_indexes
        except Exception as e:
            if verbose:
                print(f"   ⚠️  {coll_name}: Erreur ({e})")

    if verbose:
        print(f"\n   📊 Total : {total_indexes} indexes copiés")
    return total_indexes


def _anonymize_user_docs(docs):
    """Anonymize user documents in place (email/username), keeping password_hash.

    Args:
        docs: User documents to anonymize in place.
    """
    for doc in docs:
        doc["email"] = f"test_{doc['_id']}@geochallenge.app"
        doc["username"] = f"test_{str(doc['_id'])[:8]}"
        # Garder password_hash pour les tests d'auth


async def _copy_collection_documents(prod_db, test_db, coll_name, verbose):
    """Copy all documents of one collection from prod to test, unless already populated.

    Description:
        Anonymizes `users` documents (email/username) before inserting.

    Args:
        prod_db: Source database handle.
        test_db: Target database handle.
        coll_name: Collection name.
        verbose: Print progress to stdout.

    Returns:
        int: Number of documents inserted (0 if skipped).
    """
    # Vérifier si la collection de test contient déjà des documents
    count = await test_db[coll_name].count_documents({})
    if verbose:
        print(f"[DEBUG] {coll_name} a {count} docs avant duplication")
    if count > 0:
        if verbose:
            print(f"   ⚡ {coll_name} contient déjà {count} documents, skip")
        return 0

    # Récupérer tous les documents de la prod
    docs = await prod_db[coll_name].find().to_list(length=None)
    nb_docs_to_insert = len(docs)

    # Anonymiser les collections sensibles
    if coll_name == "users":
        _anonymize_user_docs(docs)
        if verbose:
            print(f"   🔒 {coll_name}: {len(docs)} documents (anonymisés)")
    else:
        if verbose:
            print(f"   ✓ {coll_name}: {len(docs)} documents")

    # Insérer les documents
    if nb_docs_to_insert > 0:
        await test_db[coll_name].insert_many(docs)
    return nb_docs_to_insert


async def _copy_all_documents(prod_db, test_db, prod_collection_names, verbose):
    """Copy documents for every prod collection into the test db.

    Args:
        prod_db: Source database handle.
        test_db: Target database handle.
        prod_collection_names: Collections to copy documents for.
        verbose: Print progress to stdout.

    Returns:
        int: Total number of documents inserted.
    """
    if verbose:
        print("\n📦 Étape 3/4 : Copie des données...")
    total_docs = 0

    for coll_name in prod_collection_names:
        total_docs += await _copy_collection_documents(prod_db, test_db, coll_name, verbose)

    if verbose:
        print(f"\n   📊 Total : {total_docs} documents copiés")
    return total_docs


async def _verify_collections_match(test_db, prod_collection_names, verbose):
    """Verify that the test db now has the same collections as prod.

    Args:
        test_db: Target database handle.
        prod_collection_names: Expected collection names.
        verbose: Print progress to stdout.

    Returns:
        list: The test db's collection names, as observed.
    """
    if verbose:
        print("\n✅ Étape 4/4 : Vérification...")
    test_collection_names = await test_db.list_collection_names()

    if set(test_collection_names) == set(prod_collection_names):
        if verbose:
            print(f"   ✅ {len(test_collection_names)} collections vérifiées")
    else:
        if verbose:
            print("   ⚠️  Warning: Collections mismatch!")
            print(f"      Prod: {prod_collection_names}")
            print(f"      Test: {test_collection_names}")

    return test_collection_names


def _print_duplication_summary(test_collection_names, total_docs, total_indexes):
    """Print the final summary banner.

    Args:
        test_collection_names: Test db's collection names.
        total_docs: Total documents copied.
        total_indexes: Total indexes copied.
    """
    print("\n" + "=" * 60)
    print("✅ DUPLICATION TERMINÉE AVEC SUCCÈS")
    print("=" * 60)
    print(f"📊 Collections : {len(test_collection_names)}")
    print(f"📊 Documents   : {total_docs}")
    print(f"📊 Indexes      : {total_indexes}")
    print("🔒 Users        : Anonymisés")
    print("=" * 60)
    print(f"\n💡 DB de test prête : {TEST_DB_NAME}")
    print("💡 Pour tester : pytest tests/integration/ -v")
    print("=" * 60)


async def duplicate_db_with_indexes(verbose):
    """Duplique la DB de production vers la DB de test avec anonymisation."""

    if verbose:
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

    prod_collection_names = await _sync_missing_collections(prod_db, test_db, verbose)

    total_indexes = await _copy_all_indexes(prod_db, test_db, prod_collection_names, verbose)
    total_docs = await _copy_all_documents(prod_db, test_db, prod_collection_names, verbose)
    test_collection_names = await _verify_collections_match(test_db, prod_collection_names, verbose)

    # Cleanup
    prod_client.close()
    test_client.close()

    # Résumé
    if verbose:
        _print_duplication_summary(test_collection_names, total_docs, total_indexes)


if __name__ == "__main__":
    try:
        asyncio.run(duplicate_db_with_indexes(verbose=True))
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        print("\nVérifie que :")
        print("1. Les variables d'environnement sont correctes dans .env")
        print("2. Tu as accès à MongoDB Atlas")
        print("3. La DB de production existe")
        exit(1)
