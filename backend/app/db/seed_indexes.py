# app/db/seed_indexes.py
"""
Idempotent index seeding for GeoChallenge Tracker.

- Uses get_collection() (no direct client here).
- Matching by KEYS: if an index with same keys exists, keep it when options match.
- If options differ (unique / partialFilterExpression / collation), drop & recreate.
- Text indexes: Mongo allows ONE per collection; we compare weights (fields) and replace if needed.
- Users: case-insensitive unique indexes (collation strength=2) on username & email.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.operations import IndexModel
from pymongo.collation import Collation
from app.db.mongodb import get_collection

# Direction can be 1/-1 for asc/desc, or string for special types ('2dsphere', '2d', etc.)
Direction = Union[int, str]
KeySpec = List[Tuple[str, Direction]]

# Case-insensitive (accent-sensitive) collation for users
COLLATION_CI = Collation(locale="en", strength=2)


def _normalize_key_from_mongo(key_doc: Dict[str, Any]) -> KeySpec:
    """Mongo returns an OrderedDict-like mapping; convert to list of (field, direction).
    Direction may be numeric (1/-1) or a string like '2dsphere'.
    """
    norm: KeySpec = []
    for k, v in key_doc.items():
        if isinstance(v, (int, float)):
            norm.append((k, int(v)))
        else:
            # e.g. '2dsphere', 'text'
            norm.append((k, str(v)))
    return norm


def _find_existing_by_keys(coll, keys: KeySpec) -> Optional[Dict[str, Any]]:
    for ix in coll.list_indexes():
        if 'key' in ix and _normalize_key_from_mongo(ix['key']) == keys:
            return ix
    return None


def _collation_to_dict(c: Optional[Collation]) -> Optional[Dict[str, Any]]:
    if c is None:
        return None
    # Collation has properties; we compare a subset that matters
    return {
        'locale': c.document.get('locale'),
        'strength': c.document.get('strength'),
        'caseLevel': c.document.get('caseLevel'),
        'caseFirst': c.document.get('caseFirst'),
        'numericOrdering': c.document.get('numericOrdering'),
        'alternate': c.document.get('alternate'),
        'maxVariable': c.document.get('maxVariable'),
        'backwards': c.document.get('backwards'),
    }


def _same_options(existing: Dict[str, Any], *, unique: Optional[bool], partial: Optional[Dict[str, Any]], collation: Optional[Collation]) -> bool:
    ex_unique = bool(existing.get('unique', False))
    if bool(unique) != ex_unique:
        return False
    ex_partial = existing.get('partialFilterExpression')
    if (partial or None) != (ex_partial or None):
        return False
    ex_collation = existing.get('collation')
    # ex_collation is a dict when present
    return ( _collation_to_dict(collation) or None ) == ( ex_collation or None )


def ensure_index(coll_name: str, keys: KeySpec, *, name: Optional[str] = None,
                 unique: Optional[bool] = None,
                 partial: Optional[Dict[str, Any]] = None,
                 collation: Optional[Collation] = None) -> None:
    coll = get_collection(coll_name)
    existing = _find_existing_by_keys(coll, keys)
    if existing and _same_options(existing, unique=unique, partial=partial, collation=collation):
        return
    if existing:
        coll.drop_index(existing['name'])
    opts: Dict[str, Any] = {}
    if name:
        opts['name'] = name
    if unique is not None:
        opts['unique'] = unique
    if partial:
        opts['partialFilterExpression'] = partial
    if collation is not None:
        opts['collation'] = collation
    coll.create_indexes([IndexModel(keys, **opts)])


def ensure_text_index(coll_name: str, fields: Iterable[str], *, name: Optional[str] = None) -> None:
    """Ensure a single text index over the given fields (weights = 1 each)."""
    coll = get_collection(coll_name)
    wanted = {f: 1 for f in fields}
    existing = None
    for ix in coll.list_indexes():
        if 'weights' in ix:  # text index
            existing = ix
            break
    if existing:
        # Compare weights (ignore stray '_id' entry if present)
        ex_weights = {k: v for k, v in existing.get('weights', {}).items() if k != '_id'}
        if ex_weights == wanted:
            return  # already desired
        coll.drop_index(existing['name'])
    keys = [(f, TEXT) for f in fields]
    coll.create_indexes([IndexModel(keys, name=name)])


def ensure_indexes() -> None:
    # ---------- users (CI uniques via collation) ----------
    ensure_index('users', [('username', ASCENDING)], name='uniq_username_ci', unique=True, collation=COLLATION_CI)
    ensure_index('users', [('email', ASCENDING)], name='uniq_email_ci', unique=True, collation=COLLATION_CI)
    # Non-unique helpers
    ensure_index('users', [('is_active', ASCENDING)])
    ensure_index('users', [('is_verified', ASCENDING)])
    ensure_index('users', [('location', '2dsphere')], name='geo_user_location_2dsphere')

    # ---------- countries ----------
    ensure_index('countries', [('name', ASCENDING)], name='uniq_country_name', unique=True)
    ensure_index('countries', [('code', ASCENDING)], unique=True, partial={'code': {'$type': 'string'}})

    # ---------- states ----------
    ensure_index('states', [('country_id', ASCENDING)])
    ensure_index('states', [('country_id', ASCENDING), ('name', ASCENDING)], name='uniq_state_name_per_country', unique=True)
    ensure_index('states', [('country_id', ASCENDING), ('code', ASCENDING)], name='uniq_state_code_per_country_if_present', unique=True, partial={'code': {'$type': 'string'}})

    # ---------- cache_attributes ----------
    ensure_index('cache_attributes', [('cache_attribute_id', ASCENDING)], name='uniq_cache_attribute_id', unique=True)
    ensure_index('cache_attributes', [('txt', ASCENDING)], name='uniq_cache_attribute_txt', unique=True, partial={'txt': {'$type': 'string'}})
    ensure_index('cache_attributes', [('name', ASCENDING)])

    # ---------- cache_sizes ----------
    ensure_index('cache_sizes', [('name', ASCENDING)], name='uniq_cache_size_name', unique=True)
    ensure_index('cache_sizes', [('code', ASCENDING)], name='uniq_cache_size_code_if_present', unique=True, partial={'code': {'$type': 'string'}})

    # ---------- cache_types ----------
    ensure_index('cache_types', [('name', ASCENDING)], name='uniq_cache_type_name', unique=True)
    ensure_index('cache_types', [('code', ASCENDING)], name='uniq_cache_type_code_if_present', unique=True, partial={'code': {'$type': 'string'}})

    # ---------- caches ----------
    ensure_index('caches', [('GC', ASCENDING)], name='uniq_gc_code', unique=True)
    ensure_index('caches', [('type_id', ASCENDING)])
    ensure_index('caches', [('size_id', ASCENDING)])
    ensure_index('caches', [('country_id', ASCENDING)])
    ensure_index('caches', [('state_id', ASCENDING)])
    ensure_index('caches', [('country_id', ASCENDING), ('state_id', ASCENDING)])
    ensure_index('caches', [('difficulty', ASCENDING)])
    ensure_index('caches', [('terrain', ASCENDING)])
    ensure_index('caches', [('placed_at', DESCENDING)])
    ensure_text_index('caches', ['title', 'description_html'], name='text_title_desc')
    ensure_index('caches', [('loc', '2dsphere')], name='geo_loc_2dsphere')
    # Caches: accelerate attribute-based filters (RuleAttributes)
    ensure_index('caches', [('attributes.attribute_doc_id', ASCENDING), ('attributes.is_positive', ASCENDING)], name='ix_caches__attributes_attrdocid_ispos')
    # NEW: combos fréquents pour targets
    ensure_index('caches', [('type_id', ASCENDING), ('size_id', ASCENDING)], name='ix_caches__type_size')
    ensure_index('caches', [('difficulty', ASCENDING), ('terrain', ASCENDING)], name='ix_caches__difficulty_terrain')

    # ---------- found_caches ----------
    ensure_index('found_caches', [('user_id', ASCENDING), ('cache_id', ASCENDING)], name='uniq_user_cache_found', unique=True)
    ensure_index('found_caches', [('user_id', ASCENDING), ('found_date', DESCENDING)])
    ensure_index('found_caches', [('cache_id', ASCENDING)])

    # ---------- challenges ----------
    ensure_index('challenges', [('cache_id', ASCENDING)], name='uniq_mother_cache', unique=True)
    ensure_text_index('challenges', ['name', 'description'], name='text_name_desc')

    # ---------- user_challenges ----------
    ensure_index('user_challenges', [('user_id', ASCENDING), ('challenge_id', ASCENDING)],
                 name='uniq_user_challenge_pair', unique=True)
    ensure_index('user_challenges', [('user_id', ASCENDING)])
    ensure_index('user_challenges', [('challenge_id', ASCENDING)])
    ensure_index('user_challenges', [('status', ASCENDING)])
    # UserChallenges: fast listing by user + status sorted by most recently updated
    ensure_index('user_challenges', [('user_id', ASCENDING), ('status', ASCENDING), ('updated_at', DESCENDING)],  name='ix_user_challenges__by_user_status_updated')

    # ---------- user_challenge_tasks ----------
    ensure_index('user_challenge_tasks', [('user_challenge_id', ASCENDING), ('order', ASCENDING)])
    ensure_index('user_challenge_tasks', [('user_challenge_id', ASCENDING), ('status', ASCENDING)])
    ensure_index('user_challenge_tasks', [('user_challenge_id', ASCENDING)])
    ensure_index('user_challenge_tasks', [('last_evaluated_at', DESCENDING)])

    # ---------- progress ----------
    ensure_index('progress', [('user_challenge_id', ASCENDING), ('checked_at', ASCENDING)], name='uniq_progress_time_per_challenge', unique=True)

    # ---------- targets ----------
    # Unicité d’un target par (UC, cache)
    ensure_index('targets', [('user_challenge_id', ASCENDING), ('cache_id', ASCENDING)], name='uniq_target_per_challenge_cache', unique=True)

    # Filtrages et tris courants
    ensure_index('targets', [('user_challenge_id', ASCENDING), ('satisfies_task_ids', ASCENDING)])
    ensure_index('targets', [('user_challenge_id', ASCENDING), ('primary_task_id', ASCENDING)])
    ensure_index('targets', [('cache_id', ASCENDING)])
    ensure_index('targets', [('user_challenge_id', ASCENDING), ('score', DESCENDING)], name='uc_score_desc')

    # (NOUVEAU) Tri global par user : user_id est dénormalisé dans targets
    ensure_index('targets', [('user_id', ASCENDING), ('score', DESCENDING)], name='user_score_desc')

    # (NOUVEAU) Index géospatial : 'loc' (GeoJSON Point) est dénormalisé dans targets
    ensure_index('targets', [('loc', '2dsphere')], name='geo_targets_loc_2dsphere')

    # Tri récents si besoin d’ordonnancement temporel
    ensure_index('targets', [('updated_at', DESCENDING), ('created_at', DESCENDING)], name='updated_created_desc')


if __name__ == "__main__":
    ensure_indexes()
