# ADR 0010: Migrate from Motor to the PyMongo async API

**Status:** Accepted, implemented 2026-11-13 (CHORE-012)
**Date:** 2026-11-13
**Deciders:** Marvin Le Rouge
**Sources:** roadmap CHORE-008

## Context

The backend talks to MongoDB through Motor (`motor>=3.7.1`, on top of `pymongo>=4.19.0`).
MongoDB deprecated Motor in favor of PyMongo's native async API (`pymongo.AsyncMongoClient`,
GA since PyMongo 4.13): Motor reached end of life on 2026-05-14 and only gets critical bug
fixes until 2027-05-14. After that date a security issue in Motor would have no fix.

PyMongo is already a direct dependency at 4.19, so the replacement is installed; Motor adds
nothing but a wrapper layer that runs the sync driver in a thread pool.

Footprint measured on 2026-11-13:

- 20 files import Motor: `app/db/mongodb.py`, 15 services/routes (mostly type hints on
  `AsyncIOMotorDatabase` / `AsyncIOMotorCollection`), and 4 test utilities
  (`tests/integration/conftest.py`, `test_connectivity.py`, `duplicate_db_for_tests.py`,
  `copy_db_structure.py`).
- No change streams, GridFS or Tornado integration.

## Decision

Migrate to `pymongo.AsyncMongoClient` in one dedicated task, before 2027-05-14, rather than
waiting for a Motor CVE.

API differences the migration must handle (Motor -> PyMongo async):

| Motor | PyMongo async | Occurrences in `app/` + `scripts/` |
|---|---|---|
| `coll.aggregate(pipeline)` returns a cursor synchronously | `await coll.aggregate(pipeline)` returns the cursor | 17 calls |
| `coll.list_indexes()` returns a cursor synchronously | `await coll.list_indexes()` | 7 calls (incl. tests/utils) |
| `client.close()` | `await client.close()` | 6 calls |
| `AsyncIOMotorClient/Database/Collection` | `AsyncMongoClient`, `AsyncDatabase`, `AsyncCollection` (`pymongo.asynchronous.*`) | 20 files |
| `cursor.to_list(length=None)` | `cursor.to_list()` (`length` still accepted) | unchanged |

`find`, `find_one`, `insert_*`, `update_*`, `delete_*`, `count_documents`, `bulk_write` and
async iteration over cursors keep the same shape.

Plan, one branch:

1. `app/db/mongodb.py`: `AsyncMongoClient`, same lazy singleton and lifespan close
   (`await client.close()`).
2. Replace type hints in services and routes (mechanical).
3. Await every `aggregate()` and `list_indexes()` call. A missed `await` passes type
   checking only if hints are loose, so grep the result: no `.aggregate(` without `await`.
4. Update unit-test mocks: about 29 test files mock `aggregate` as a plain call returning
   a cursor; they must return an awaitable (`AsyncMock` returning the cursor mock).
5. Remove `motor` from `pyproject.toml`, relock.
6. Verify: unit suite, integration suite on the disposable mongo (CI job), and a
   production-image smoke test (login, GPX import, zones map) before merging.

## Consequences

- One fewer dependency and no thread-pool indirection; PyMongo async is the maintained path.
- Large but mechanical diff (about 20 source files and 30 test files). The risky part is a
  forgotten `await` on `aggregate()`, which fails at runtime, not import time: the integration
  suite covers the main aggregation routes (zones, by-filter, stats), the unit mocks the rest.
- Until the migration lands, Motor stays pinned at 3.7.x and its end-of-life dates are
  tracked in the roadmap (CHORE-008 delivered this plan; the migration itself is a new task).

## Implementation notes (2026-11-13)

- 34 calls rewritten to `await` (`aggregate`, `list_indexes`, client `close`) by an AST script, so none was missed by hand; `tests/unit/test_mongo_async_calls.py` fails if a non-awaited `aggregate()` / `list_indexes()` comes back (checked against the Motor code: it fails there).
- 51 unit-test mocks moved to `AsyncMock` / `async def aggregate`.
- Verified: unit suite, integration suite on a disposable mongo (CI mode and with the sample GPX), and the production image against a seeded disposable mongo, with the same results as the Motor image (login, GPX import, by-filter, zones, stats, challenges).
