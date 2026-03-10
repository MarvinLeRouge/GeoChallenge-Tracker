"""
Tests d'intégration pour la base de données.

Niveau : MÉTIER / CONTENU

Ces tests vérifient le CONTENU de la base de données de test :
- Les collections ont-elles le bon contenu ?
- Les données de référence sont-elles présentes ?
- L'admin de test existe-t-il ?
- La DB est-elle bien isolée de la prod ?

⚠️ Ce fichier teste le CONTENU MÉTIER :
   - "Les données sont-elles présentes dans la DB ?"
   - "Les collections ont-elles le bon contenu ?"
   - Tests fonctionnels sur les données de test

📁 À distinguer de `test_connectivity.py` qui teste l'INFRASTRUCTURE :
   - "Est-ce que je peux me connecter à MongoDB ?"
   - "Les objets de base de données sont-ils accessibles ?"
"""

import pytest

# =============================================================================
# DATABASE CONNECTIVITY TESTS
# =============================================================================


class TestDatabaseConnectivity:
    """Tests de connectivité à la DB de test."""

    @pytest.mark.asyncio
    async def test_verify_db_collections(self, test_db):
        """Vérifier le nom exact de la DB utilisée."""
        # Lister les collections pour être sûr qu'on est sur la bonne DB
        collections = await test_db.list_collection_names()
        collections_set = set(collections)
        collections_sample = {"users", "caches", "challenges", "user_challenges"}
        assert collections_sample.issubset(collections_set), "Des collections sont manquantes"

    @pytest.mark.asyncio
    async def test_test_db_has_referentials(self, test_db):
        """Test que les référentiels sont présents."""
        referential_collections = [
            "cache_types",
            "cache_sizes",
            "cache_attributes",
            "countries",
            "states",
        ]

        for coll_name in referential_collections:
            count = await test_db[coll_name].count_documents({})
            assert count > 0, f"Referential {coll_name} is empty"

    @pytest.mark.asyncio
    async def test_test_db_has_test_admin(self, test_db):
        """Test que l'admin de test existe."""
        admin = await test_db.users.find_one({"username": "testadmin"})

        assert admin is not None
        assert admin["email"].endswith("@geochallenge.app")
        assert admin["role"] == "admin"

    @pytest.mark.asyncio
    async def test_test_db_is_isolated(self, test_db, test_settings):
        """Test que la DB de test est différente de la prod."""
        # Vérifier que le nom de la DB contient _TEST
        assert test_settings.mongodb_db.endswith("_TEST")

        # Compter les users (devrait être < prod car anonymisés)
        user_count = await test_db.users.count_documents({})
        assert user_count > 0  # Au moins l'admin de test
