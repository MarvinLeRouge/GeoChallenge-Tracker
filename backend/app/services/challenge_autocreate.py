
# backend/app/services/challenge_autocreate.py

"""
Création automatique des Challenges à partir des caches qui portent l'attribut "challenge".
Critère: présence de l'attribut geocaching.com `cache_attribute_id = 71` en positif.

Optimisations:
- On exclut d'emblée les caches déjà présentes dans `challenges`.
- Quand on balaye toute la base, on utilise un pipeline `$lookup` (indexé sur `challenges.cache_id`)
  pour éviter de charger un gros set en mémoire.
- Quand on limite à un sous-ensemble (ex: IDs importés), on fait un `$in` + exclusion locale.

Idempotent: un challenge est unique par `cache_id` (index unique requis sur `challenges(cache_id)`).
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Dict, Any
from datetime import datetime
from pymongo import UpdateOne
from bson import ObjectId

from app.db.mongodb import get_collection

# Constante métier: attribut "Challenge cache" (geocaching.com)
CHALLENGE_ATTRIBUTE_ID = 71


def _get_attribute_doc_id(attribute_id: int = CHALLENGE_ATTRIBUTE_ID) -> ObjectId:
    """Résout l'_id du document référentiel (collection `cache_attributes`) pour `cache_attribute_id`."""
    attr_coll = get_collection('cache_attributes')
    doc = attr_coll.find_one({'cache_attribute_id': attribute_id}, {'_id': 1})
    if not doc:
        raise RuntimeError(
            f"cache_attributes: aucun document avec cache_attribute_id={attribute_id}. "
            "Vérifie que le référentiel des attributs est seedé."
        )
    return doc['_id']


def _iter_new_challenge_caches_all(attribute_doc_id: ObjectId):
    """Balayage global optimisé via `$lookup` vers `challenges` pour ne retenir que les nouvelles."""
    caches = get_collection('caches')
    pipeline = [
        {
            '$match': {
                'attributes': {
                    '$elemMatch': {
                        'attribute_doc_id': attribute_doc_id,
                        'is_positive': True,
                    }
                }
            }
        },
        {
            '$lookup': {
                'from': 'challenges',
                'localField': '_id',
                'foreignField': 'cache_id',
                'as': 'existing'
            }
        },
        {
            '$match': {
                '$expr': {'$eq': [{'$size': '$existing'}, 0]}
            }
        },
        {
            '$project': {
                'title': 1,
                'description_html': 1
            }
        }
    ]
    return caches.aggregate(pipeline, allowDiskUse=True)


def _iter_new_challenge_caches_subset(attribute_doc_id: ObjectId, cache_ids: Iterable[ObjectId]):
    """Sous-ensemble: filtre par _id ∈ cache_ids puis exclusion par set des cache_id déjà connus."""
    caches = get_collection('caches')
    challenges = get_collection('challenges')

    cache_ids = list(cache_ids)
    if not cache_ids:
        return iter(())

    # Déjà connus (uniquement dans ce sous-ensemble)
    known_ids = set(challenges.distinct('cache_id', {'cache_id': {'$in': cache_ids}}))

    base_filter: Dict[str, Any] = {
        '_id': {'$in': [cid for cid in cache_ids if cid not in known_ids]},
        'attributes': {
            '$elemMatch': {
                'attribute_doc_id': attribute_doc_id,
                'is_positive': True,
            }
        }
    }
    projection = {'title': 1, 'description_html': 1}
    return caches.find(base_filter, projection)


def create_challenges_from_caches(*, cache_ids: Optional[Iterable[ObjectId]] = None) -> Dict[str, Any]:
    """Crée (ou laisse en place) les `Challenge` pour les caches qui portent l'attribut "challenge".

    - Si `cache_ids` est fourni: ne considère que ces caches (cas import GPX incrémental).
    - Sinon: balaye l'ensemble de la collection `caches` avec pipeline `$lookup`.

    Retourne un dict de stats: {'matched': int, 'created': int, 'skipped_existing': int}.
    """
    attr_doc_id = _get_attribute_doc_id(CHALLENGE_ATTRIBUTE_ID)

    if cache_ids is None:
        cursor = _iter_new_challenge_caches_all(attr_doc_id)
    else:
        cursor = _iter_new_challenge_caches_subset(attr_doc_id, cache_ids)

    challenges = get_collection('challenges')

    ops: List[UpdateOne] = []
    matched = 0
    for cache in cursor:
        matched += 1
        cache_id = cache['_id']
        title = cache.get('title') or 'Challenge'
        description = cache.get('description_html') or ''

        ops.append(
            UpdateOne(
                {'cache_id': cache_id},
                {
                    '$setOnInsert': {
                        'cache_id': cache_id,
                        'name': title,
                        'description': description,
                        'created_at': datetime.utcnow(),
                    },
                    '$set': {
                        'updated_at': datetime.utcnow(),
                    },
                },
                upsert=True,
            )
        )

    created = 0
    if ops:
        res = challenges.bulk_write(ops, ordered=False)
        created = len(res.upserted_ids) if getattr(res, 'upserted_ids', None) else 0

    skipped_existing = matched - created
    return {'matched': matched, 'created': created, 'skipped_existing': skipped_existing}

def create_new_challenges_from_caches(*, cache_ids: Optional[Iterable[ObjectId]] = None) -> Dict[str, Any]:
    """
    Wrapper haut-niveau : calcule explicitement l'ensemble des caches candidates,
    retire celles déjà présentes dans `challenges`, et délègue à `create_challenges_from_caches`.
    IMPORTANT : si aucun nouvel _id n'est à traiter, on retourne des stats vides
    (et on n'exécute PAS de scan global).
    """
    attr_doc_id = _get_attribute_doc_id(CHALLENGE_ATTRIBUTE_ID)
    caches = get_collection('caches')
    challenges = get_collection('challenges')

    if cache_ids is not None:
        subset = list(cache_ids)
        if not subset:
            return {'matched': 0, 'created': 0, 'skipped_existing': 0}
        known = set(challenges.distinct('cache_id', {'cache_id': {'$in': subset}}))
        new_ids = [cid for cid in subset if cid not in known]
        if not new_ids:
            return {'matched': 0, 'created': 0, 'skipped_existing': 0}
        return create_challenges_from_caches(cache_ids=new_ids)

    candidate_ids = caches.distinct('_id', {
        'attributes': {'$elemMatch': {'attribute_doc_id': attr_doc_id, 'is_positive': True}}
    })
    if not candidate_ids:
        return {'matched': 0, 'created': 0, 'skipped_existing': 0}

    known = set(challenges.distinct('cache_id', {'cache_id': {'$in': candidate_ids}}))
    new_ids = [cid for cid in candidate_ids if cid not in known]
    if not new_ids:
        return {'matched': 0, 'created': 0, 'skipped_existing': 0}
    return create_challenges_from_caches(cache_ids=new_ids)
