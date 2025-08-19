
import pprint
from datetime import datetime
from typing import Dict, Any, List

import pytest
from bson import ObjectId

from app.db.mongodb import get_collection
from app.services.user_challenge_tasks import list_tasks, put_tasks, validate_only

pp = pprint.PrettyPrinter(indent=2, width=120, compact=False)

ADMIN_ROLE = "admin"

def _pick_one(coll_name: str, query=None, projection=None):
    col = get_collection(coll_name)
    return col.find_one(query or {}, projection or {"_id": 1})

def _pick_many(coll_name: str, limit=2, query=None, projection=None):
    col = get_collection(coll_name)
    return list(col.find(query or {}, projection or {"_id": 1}).limit(limit))

def _name_for(coll: str, _id: ObjectId) -> str:
    doc = get_collection(coll).find_one({"_id": _id}, {"name": 1, "code": 1})
    if not doc:
        return str(_id)
    return doc.get("name") or doc.get("code") or str(_id)

def _attr_name(caid: int) -> str:
    doc = get_collection("cache_attribute").find_one({"cache_attribute_id": caid}, {"name": 1, "code": 1})
    if not doc:
        return f"attr:{caid}"
    return doc.get("name") or doc.get("code") or f"attr:{caid}"

def _render_expression_human(expr: Dict[str, Any]) -> str:
    # Very small renderer for common nodes
    if "and" in expr:
        return " AND ".join(_render_expression_human(x) for x in expr["and"])
    if "or" in expr:
        return "(" + " OR ".join(_render_expression_human(x) for x in expr["or"]) + ")"
    if "not" in expr:
        return "NOT (" + _render_expression_human(expr["not"]) + ")"
    if "type_in" in expr:
        ids = [ _name_for("cache_type", ObjectId(str(i))) if ObjectId.is_valid(str(i)) else str(i) for i in expr["type_in"] ]
        return f"type in [{', '.join(ids)}]"
    if "size_in" in expr:
        ids = [ _name_for("cache_size", ObjectId(str(i))) if ObjectId.is_valid(str(i)) else str(i) for i in expr["size_in"] ]
        return f"size in [{', '.join(ids)}]"
    if "country_is" in expr:
        cid = expr["country_is"]
        name = _name_for("country", ObjectId(str(cid))) if ObjectId.is_valid(str(cid)) else str(cid)
        return f"country is {name}"
    if "state_in" in expr:
        ids = [ _name_for("state", ObjectId(str(i))) if ObjectId.is_valid(str(i)) else str(i) for i in expr["state_in"] ]
        return f"state in [{', '.join(ids)}]"
    if "difficulty_between" in expr:
        a,b = expr["difficulty_between"]
        return f"difficulty {a}–{b}"
    if "terrain_between" in expr:
        a,b = expr["terrain_between"]
        return f"terrain {a}–{b}"
    if "placed_year" in expr:
        return f"placed in {expr['placed_year']}"
    if "placed_before" in expr:
        return f"placed before {expr['placed_before']}"
    if "placed_after" in expr:
        return f"placed after {expr['placed_after']}"
    if "attributes" in expr:
        parts = []
        for a in expr["attributes"]:
            label = _attr_name(a["cache_attribute_id"])
            parts.append(f"{label}={'yes' if a.get('is_positive', True) else 'no'}")
        return "attributes(" + ", ".join(parts) + ")"
    # fallback
    return pp.pformat(expr)

@pytest.fixture(scope="module")
def admin_user_id():
    user = get_collection("users").find_one({"role": ADMIN_ROLE}, {"_id": 1, "username": 1, "email": 1})
    if not user:
        pytest.skip("No admin user found in DB.")
    print(f"[setup] Admin: _id={user['_id']} username={user.get('username')} email={user.get('email')}")
    return user["_id"]

@pytest.fixture()
def uc_ctx(admin_user_id):
    # Create a dummy challenge
    challenges = get_collection("challenges")
    ch_doc = {
        "_id": ObjectId(),
        "name": "PyTest Dummy Challenge",
        "description": "Challenge for testing UserChallengeTasks",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    challenges.insert_one(ch_doc)

    # Create a user_challenge for admin
    ucs = get_collection("user_challenges")
    uc_doc = {
        "_id": ObjectId(),
        "user_id": admin_user_id,
        "challenge_id": ch_doc["_id"],
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    ucs.insert_one(uc_doc)

    print(f"[setup] Created challenge {_name_for('challenges', ch_doc['_id'])} ({ch_doc['_id']})")
    print(f"[setup] Created user_challenge {uc_doc['_id']} for user {admin_user_id}")

    yield {
        "challenge_id": ch_doc["_id"],
        "user_challenge_id": uc_doc["_id"],
    }

    # Teardown: delete tasks, uc, challenge
    get_collection("user_challenge_tasks").delete_many({"user_challenge_id": uc_doc["_id"]})
    get_collection("user_challenges").delete_one({"_id": uc_doc["_id"]})
    get_collection("challenges").delete_one({"_id": ch_doc["_id"]})
    print(f"[teardown] Cleaned user_challenge {uc_doc['_id']} and challenge {ch_doc['_id']}")


def _sample_referentials():
    # Require all referentials to be present; fail fast if missing
    tps = _pick_many("cache_type", limit=2, projection={"_id": 1, "name": 1})
    szs = _pick_many("cache_size", limit=2, projection={"_id": 1, "name": 1})
    ctry = _pick_one("country", projection={"_id": 1, "name": 1})
    sts = _pick_many("state", limit=2, projection={"_id": 1, "name": 1})
    attr = get_collection("cache_attribute").find_one({}, {"cache_attribute_id": 1, "name": 1})

    missing = []
    if not tps: missing.append("cache_type")
    if not szs: missing.append("cache_size")
    if not ctry: missing.append("country")
    if not sts: missing.append("state")
    if not attr: missing.append("cache_attribute")
    if missing:
        raise AssertionError("Missing referentials: " + ", ".join(missing))

    return {
        "type_ids": [t["_id"] for t in tps],
        "size_ids": [s["_id"] for s in szs],
        "country_id": ctry["_id"],
        "state_ids": [s["_id"] for s in sts],
        "cache_attribute_id": attr["cache_attribute_id"],
    }

def test_user_challenge_tasks_verbose(admin_user_id, uc_ctx):
    refs = _sample_referentials()

    uc_id = uc_ctx["user_challenge_id"]
    print("\n[info] Using referentials:")
    pp.pprint(refs)

    # Build 3 tasks with 2-4 conditions each
    tasks_payload = [
        {
            "title": "Tradis with picnic",
            "expression": {
                "and": [
                    { "type_in": refs["type_ids"][:1] },
                    { "attributes": [ { "cache_attribute_id": refs["cache_attribute_id"], "is_positive": True } ] }
                ]
            },
            "constraints": { "min_count": 3 },
            "status": "todo",
        },
        {
            "title": "Any size in chosen country, placed before 2010",
            "expression": {
                "and": [
                    { "size_in": refs["size_ids"] },
                    { "country_is": refs["country_id"] },
                    { "placed_before": "2010-01-01" }
                ]
            },
            "constraints": { "min_count": 2 },
            "status": "in_progress",
        },
        {
            "title": "State-specific, moderate D/T",
            "expression": {
                "and": [
                    { "state_in": refs["state_ids"] },
                    { "difficulty_between": [1.5, 3.0] },
                    { "terrain_between": [1.5, 3.0] }
                ]
            },
            "constraints": { "min_count": 1 },
            "status": "done",  # expect progress 100%
        },
    ]

    print("\n[print] Human-readable conditions:")
    for i, t in enumerate(tasks_payload):
        print(f"  - Task {i+1}: {t['title']}")
        print(f"    AST: {pp.pformat(t['expression'])}")
        print(f"    Human: {_render_expression_human(t['expression'])}")

    # 1) Validate-only
    res_val = validate_only(admin_user_id, uc_id, tasks_payload)
    print("\n[result] validate_only:", res_val)
    assert res_val["ok"] is True, "Validation failed when it should pass"

    # 2) PUT tasks
    res_put = put_tasks(admin_user_id, uc_id, tasks_payload)
    print("\n[result] put_tasks -> stored items:")
    pp.pprint(res_put)
    assert len(res_put) == len(tasks_payload)
    assert all(isinstance(i["order"], int) and 0 <= i["order"] < len(tasks_payload) for i in res_put)

    # 3) GET list tasks
    res_list = list_tasks(admin_user_id, uc_id)
    print("\n[result] list_tasks -> items:")
    pp.pprint(res_list)
    assert [i["order"] for i in res_list] == list(range(len(tasks_payload)))

    # Check that 'done' task has progress 100%
    done = next((i for i in res_list if i["status"] == "done"), None)
    assert done is not None and done.get("progress", {}).get("percent") == 100, "Done task did not get 100% progress"
