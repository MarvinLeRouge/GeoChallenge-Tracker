# backend/tests/test_challenge_autocreate.py

import pytest
from bson import ObjectId

from app.db.mongodb import get_collection
from app.services.challenge_autocreate import (
    CHALLENGE_ATTRIBUTE_ID,
    create_new_challenges_from_caches,
)

@pytest.fixture(scope="function")
def initial_counts():
    caches_count = get_collection("caches").count_documents({})
    challenges_count = get_collection("challenges").count_documents({})
    return {"caches": caches_count, "challenges": challenges_count}

@pytest.fixture(scope="function")
def inserted_ids():
    return {"caches": set()}

@pytest.fixture(autouse=True, scope="function")
def teardown_cleanup(inserted_ids, initial_counts):
    yield
    # Remove only what we inserted
    if inserted_ids["caches"]:
        get_collection("caches").delete_many({"_id": {"$in": list(inserted_ids["caches"])}})
        get_collection("challenges").delete_many({"cache_id": {"$in": list(inserted_ids["caches"])}})
    # Assert state restored
    assert get_collection("caches").count_documents({}) == initial_counts["caches"]
    assert get_collection("challenges").count_documents({}) == initial_counts["challenges"]

def _get_seeded_challenge_attribute_doc_id():
    doc = get_collection("cache_attributes").find_one(
        {"cache_attribute_id": CHALLENGE_ATTRIBUTE_ID},
        {"_id": 1},
    )
    if not doc:
        pytest.skip("Référentiel `cache_attributes` non seedé (id 71 manquant).")
    return doc["_id"]

def insert_cache_with_attrs(*, attrs, inserted_ids, title="T", desc="D"):
    doc = {
        "_id": ObjectId(),
        "GC": f"GC{str(ObjectId())[-6:]}",
        "title": title,
        "description_html": desc,
        "attributes": attrs,
    }
    get_collection("caches").insert_one(doc)
    inserted_ids["caches"].add(doc["_id"])
    return doc["_id"]

def test_subset_only_creates_and_is_idempotent(initial_counts, inserted_ids):
    attr_doc_id = _get_seeded_challenge_attribute_doc_id()

    # Insert 2 challenge caches + 1 non-challenge
    ids = [
        insert_cache_with_attrs(attrs=[{"attribute_doc_id": attr_doc_id, "is_positive": True}], inserted_ids=inserted_ids, title="C1"),
        insert_cache_with_attrs(attrs=[{"attribute_doc_id": attr_doc_id, "is_positive": True}], inserted_ids=inserted_ids, title="C2"),
        insert_cache_with_attrs(attrs=[{"attribute_doc_id": ObjectId(), "is_positive": True}], inserted_ids=inserted_ids, title="NC"),
    ]

    # Act only on the subset we control
    stats1 = create_new_challenges_from_caches(cache_ids=ids)
    # Among subset, 2 are challenge candidates; both new
    assert stats1["created"] == 2

    # Second run should do nothing (and must not scan globally)
    stats2 = create_new_challenges_from_caches(cache_ids=ids)
    assert stats2["created"] == 0

def test_no_candidates_in_subset(inserted_ids):
    attr_doc_id = _get_seeded_challenge_attribute_doc_id()

    # Insert only non-challenge or negative challenge
    ids = [
        insert_cache_with_attrs(attrs=[{"attribute_doc_id": ObjectId(), "is_positive": True}], inserted_ids=inserted_ids, title="NC1"),
        insert_cache_with_attrs(attrs=[{"attribute_doc_id": attr_doc_id, "is_positive": False}], inserted_ids=inserted_ids, title="NEG"),
    ]

    stats = create_new_challenges_from_caches(cache_ids=ids)
    assert stats["created"] == 0
