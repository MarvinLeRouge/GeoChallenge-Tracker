import pytest
from bson import ObjectId

from app.db.mongodb import get_collection
from app.services.user_challenges import patch_user_challenge

ADMIN_ROLE = "admin"
EXPECTED_TOTAL = 222
EXPECTED_COMPLETED = 90


@pytest.fixture(scope="module")
async def admin_user_id():
    coll_users = await get_collection("users")
    user = await coll_users.find_one({"role": ADMIN_ROLE}, {"_id": 1})
    if not user:
        pytest.skip("No admin user found in DB.")
    return user["_id"]


async def _counts(user_id: ObjectId):
    coll_uc = await get_collection("user_challenges")
    total = await coll_uc.count_documents({"user_id": user_id})
    completed = await coll_uc.count_documents(
        {
            "user_id": user_id,
            "$or": [{"status": "completed"}, {"computed_status": "completed"}],
        }
    )
    accepted = await coll_uc.count_documents(
        {
            "user_id": user_id,
            "status": "accepted",
            "computed_status": {"$ne": "completed"},
        }
    )
    dismissed = await coll_uc.count_documents(
        {
            "user_id": user_id,
            "status": "dismissed",
            "computed_status": {"$ne": "completed"},
        }
    )
    pending = await coll_uc.count_documents(
        {
            "user_id": user_id,
            "status": {"$nin": ["accepted", "dismissed", "completed"]},
            "computed_status": {"$ne": "completed"},
        }
    )
    return {
        "total": total,
        "completed": completed,
        "accepted": accepted,
        "dismissed": dismissed,
        "pending": pending,
    }


async def _pick_pending(user_id: ObjectId, n: int):
    coll_uc = await get_collection("user_challenges")
    cursor = coll_uc.find(
        {
            "user_id": user_id,
            "status": {"$nin": ["accepted", "dismissed", "completed"]},
            "computed_status": {"$ne": "completed"},
        },
        {
            "_id": 1,
            "status": 1,
            "computed_status": 1,
            "manual_override": 1,
            "progress": 1,
            "override_reason": 1,
            "overridden_at": 1,
            "notes": 1,
            "updated_at": 1,
        },
    ).limit(n)
    docs = await cursor.to_list(length=None)
    return docs


@pytest.fixture()
def saved_docs():
    return {}


@pytest.fixture(autouse=True)
def _revert_after(saved_docs):
    yield
    if not saved_docs:
        return
    uc = get_collection("user_challenges")
    for _id, original in saved_docs.items():
        uc.replace_one({"_id": _id}, original)


def test_effective_status_counts_and_revert(admin_user_id, saved_docs):
    user_id = admin_user_id

    # 1) Sanity: initial counts match expectations
    initial = _counts(user_id)
    assert initial["total"] == EXPECTED_TOTAL, (
        f"Expected total={EXPECTED_TOTAL}, got {initial['total']}"
    )
    assert initial["completed"] == EXPECTED_COMPLETED, (
        f"Expected completed={EXPECTED_COMPLETED}, got {initial['completed']}"
    )

    # 2) Pick pending UCs to modify
    needed = 6
    docs = _pick_pending(user_id, needed)
    if len(docs) < 3:
        pytest.skip("Not enough pending user_challenges to run this test.")
    # Save originals for revert
    for d in docs:
        saved_docs[d["_id"]] = get_collection("user_challenges").find_one({"_id": d["_id"]})

    # Plan: 2 -> dismissed, 2 -> accepted, 2 -> completed (manual override)
    n = len(docs)
    nd = min(2, n)
    na = min(2, max(0, n - nd))
    nc = min(2, max(0, n - nd - na))

    to_dismiss = [d["_id"] for d in docs[0:nd]]
    to_accept = [d["_id"] for d in docs[nd : nd + na]]
    to_complete = [d["_id"] for d in docs[nd + na : nd + na + nc]]

    # 3) Apply changes
    for _id in to_dismiss:
        patch_user_challenge(user_id, _id, status="dismissed", notes=None, override_reason=None)
    for _id in to_accept:
        patch_user_challenge(user_id, _id, status="accepted", notes=None, override_reason=None)
    for _id in to_complete:
        patch_user_challenge(
            user_id,
            _id,
            status="completed",
            notes="pytest-completed",
            override_reason="pytest",
        )

    # 4) Check counts
    after = _counts(user_id)
    assert after["total"] == initial["total"], "Total must stay constant"

    assert after["dismissed"] == initial["dismissed"] + len(to_dismiss)
    assert after["accepted"] == initial["accepted"] + len(to_accept)
    assert after["completed"] == initial["completed"] + len(to_complete)

    # Pending is the complement (effective)
    expected_pending = initial["pending"] - (len(to_dismiss) + len(to_accept) + len(to_complete))
    assert after["pending"] == expected_pending, (
        f"Expected pending={expected_pending}, got {after['pending']}"
    )
