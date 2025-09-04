
from datetime import datetime
from typing import Dict, Any

import json
import pytest
from bson import ObjectId
from rich import print as rprint

from app.core.utils import *
from app.db.mongodb import get_collection
from app.services.user_challenge_tasks import list_tasks, put_tasks, validate_only

ADMIN_ROLE = "admin"

def _name_for(coll: str, _id: ObjectId) -> str:
    doc = get_collection(coll).find_one({"_id": _id}, {"name": 1, "code": 1})
    if not doc:
        return str(_id)
    return doc.get("name") or doc.get("code") or str(_id)

def _attr_name(caid: int) -> str:
    doc = get_collection("cache_attributes").find_one({"cache_attribute_id": caid}, {"name": 1, "name_reverse": 1, "code": 1})
    if not doc:
        return f"attr:{caid}"
    return doc.get("name") or doc.get("name_reverse") or doc.get("code") or f"attr:{caid}"

def _render_expression_human(expr: Dict[str, Any]) -> str:
    if not isinstance(expr, dict):
        return json.dumps(expr, default=str, indent=2)

    kind = expr.get("kind")
    if kind == "and":
        nodes = expr.get("nodes", [])
        return " AND ".join(_render_expression_human(n) for n in nodes)
    if kind == "or":
        nodes = expr.get("nodes", [])
        return "(" + " OR ".join(_render_expression_human(n) for n in nodes) + ")"
    if kind == "not":
        return "NOT (" + _render_expression_human(expr.get("node")) + ")"

    if kind == "type_in":
        ids = [ _name_for("cache_types", ObjectId(str(i))) for i in expr.get("type_ids", []) ]
        return f"type in [{', '.join(ids)}]"
    if kind == "size_in":
        ids = [ _name_for("cache_sizes", ObjectId(str(i))) for i in expr.get("size_ids", []) ]
        return f"size in [{', '.join(ids)}]"
    if kind == "country_is":
        cid = expr.get("country_id")
        name = _name_for("countries", ObjectId(str(cid))) if cid else "?"
        return f"country is {name}"
    if kind == "state_in":
        ids = [ _name_for("states", ObjectId(str(i))) for i in expr.get("state_ids", []) ]
        return f"state in [{', '.join(ids)}]"
    if kind == "difficulty_between":
        a = expr.get("min"); b = expr.get("max")
        return f"difficulty {a}–{b}"
    if kind == "terrain_between":
        a = expr.get("min"); b = expr.get("max")
        return f"terrain {a}–{b}"
    if kind == "placed_year":
        return f"placed in {expr.get('year')}"
    if kind == "placed_before":
        return f"placed before {expr.get('date')}"
    if kind == "placed_after":
        return f"placed after {expr.get('date')}"
    if kind == "attributes":
        parts = []
        for a in expr.get("attributes", []):
            label = _attr_name(a.get("cache_attribute_id"))
            parts.append(f"{label}={'yes' if a.get('is_positive', True) else 'no'}")
        return "attributes(" + ", ".join(parts) + ")"

    return json.dumps(expr, default=str, indent=2)

@pytest.fixture(scope="module")
def admin_user_id():
    user = get_collection("users").find_one({"role": ADMIN_ROLE}, {"_id": 1, "username": 1, "email": 1})
    if not user:
        pytest.skip("No admin user found in DB.")
    rprint(f"[setup] Admin: _id={user['_id']} username={user.get('username')} email={user.get('email')}")
    return user["_id"]

@pytest.fixture()
def uc_ctx(admin_user_id):
    challenges = get_collection("challenges")
    ch_doc = {
        "_id": ObjectId(),
        "name": "PyTest Dummy Challenge",
        "description": "Challenge for testing UserChallengeTasks",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    challenges.insert_one(ch_doc)

    ucs = get_collection("user_challenges")
    uc_doc = {
        "_id": ObjectId(),
        "user_id": admin_user_id,
        "challenge_id": ch_doc["_id"],
        "status": "pending",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    ucs.insert_one(uc_doc)

    rprint(f"[setup] Created challenge {ch_doc['name']} ({ch_doc['_id']})")
    rprint(f"[setup] Created user_challenge {uc_doc['_id']} for user {admin_user_id}")

    yield {
        "challenge_id": ch_doc["_id"],
        "user_challenge_id": uc_doc["_id"],
    }

    get_collection("user_challenge_tasks").delete_many({"user_challenge_id": uc_doc["_id"]})
    get_collection("user_challenges").delete_one({"_id": uc_doc["_id"]})
    get_collection("challenges").delete_one({"_id": ch_doc["_id"]})
    rprint(f"[teardown] Cleaned user_challenge {uc_doc['_id']} and challenge {ch_doc['_id']}")

def _sample_referentials():
    ct_tradi = get_collection("cache_types").find_one({"code": "traditional"}, {"_id": 1, "name": 1, "code": 1})
    attr_picnic = get_collection("cache_attributes").find_one({"code": "picnic"}, {"cache_attribute_id": 1, "name": 1, "code": 1})
    france = get_collection("countries").find_one({"name": "France"}, {"_id": 1, "name": 1})
    states_fr = list(get_collection("states").find({"country_id": france["_id"]}, {"_id": 1, "name": 1}).limit(2)) if france else []
    sizes = list(get_collection("cache_sizes").find({}, {"_id": 1, "name": 1}).limit(2))

    missing = []
    if not ct_tradi: missing.append("cache_types.code=traditional")
    if not attr_picnic: missing.append("cache_attributes.code=picnic")
    if not france: missing.append("countries.name=France")
    if len(states_fr) < 1: missing.append("states(country=France)")
    if len(sizes) < 1: missing.append("cache_sizes")
    if missing:
        raise AssertionError("Missing referentials: " + ", ".join(missing))

    return {
        "type_ids": [ct_tradi["_id"]],
        "size_ids": [s["_id"] for s in sizes],
        "country_id": france["_id"],
        "state_ids": [s["_id"] for s in states_fr],
        "cache_attribute_id": attr_picnic["cache_attribute_id"],
        "labels": {
            "type": ct_tradi.get("name") or ct_tradi.get("code"),
            "attribute": attr_picnic.get("name") or attr_picnic.get("code") or "picnic",
            "country": france.get("name", "France"),
            "states": [s.get("name") for s in states_fr],
            "sizes": [get_collection("cache_sizes").find_one({"_id": sid}, {"name": 1}).get("name") for sid in [s["_id"] for s in sizes]],
        }
    }

def test_user_challenge_tasks_verbose(admin_user_id, uc_ctx):
    refs = _sample_referentials()
    rprint("\n[info] Available referentials:")
    rprint(refs)

    uc_id = uc_ctx["user_challenge_id"]

    tasks_payload = [
        {
            "title": "Traditional with picnic",
            "expression": {
                "kind": "and",
                "nodes": [
                    { "kind": "type_in", "type_ids": refs["type_ids"]},
                    { "kind": "attributes", "attributes": [ { "cache_attribute_id": refs["cache_attribute_id"], "is_positive": True } ] }
                ]
            },
            "constraints": { "min_count": 3 },
            "status": "todo",
        },
        {
            "title": "Any size in France, placed before 2010",
            "expression": {
                "kind": "and",
                "nodes": [
                    { "kind": "size_in", "size_ids": refs["size_ids"] },
                    { "kind": "country_is", "country_id": refs["country_id"]},
                    { "kind": "placed_before", "date": "2010-01-01" }
                ]
            },
            "constraints": { "min_count": 2 },
            "status": "in_progress",
        },
        {
            "title": "French states, moderate D/T",
            "expression": {
                "kind": "and",
                "nodes": [
                    { "kind": "state_in", "state_ids": refs["state_ids"]},
                    { "kind": "difficulty_between", "min": 1.5, "max": 3.0 },
                    { "kind": "terrain_between", "min": 1.5, "max": 3.0 }
                ]
            },
            "constraints": { "min_count": 1 },
            "status": "done",
        },
    ]

    rprint("\n[print] Human-readable conditions:")
    for i, t in enumerate(tasks_payload):
        rprint(f"  - Task {i+1}: {t['title']}")
        rprint(f"    AST: {json.dumps(t['expression'], default=str, indent=2)}")
        rprint(f"    Human: {_render_expression_human(t['expression'])}")

    res_val = validate_only(admin_user_id, uc_id, tasks_payload)
    rprint("\n[result] validate_only:", res_val)
    assert res_val["ok"] is True, "Validation failed when it should pass"

    res_put = put_tasks(admin_user_id, uc_id, tasks_payload)
    rprint("\n[result] put_tasks -> stored items:")
    rprint(res_put)
    assert len(res_put) == len(tasks_payload)
    assert [i["order"] for i in res_put] == list(range(len(tasks_payload)))

    res_list = list_tasks(admin_user_id, uc_id)
    rprint("\n[result] list_tasks -> items:")
    rprint(res_list)
    assert [i["order"] for i in res_list] == list(range(len(tasks_payload)))

    done = next((i for i in res_list if i["status"] == "done"), None)
    assert done is not None and done.get("progress", {}).get("percent") == 100, "Done task did not get 100% progress"
