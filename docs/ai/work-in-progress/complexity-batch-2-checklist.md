# Cyclomatic complexity batch 2 - progress checklist

Branch: refactor/complexity-batch-2
Threshold: 10. Order: by cumulative cyclomatic complexity per file (descending), one commit per file.

- [x] (144) app/api/routes/maintenance.py - full_backup_restore(12->7). Extracted _restore_all_backup_collections and _build_restore_response.
- [ ] (71) app/services/referentials_cache.py - _index_one_collection_document(13)
- [ ] (69) app/api/routes/caches.py - _build_cache_filter_query(21)
- [ ] (58) app/api/routes/auth.py - _extract_login_credentials(13)
- [ ] (27) tests/unit/test_maintenance_full_backup_create.py - TestFullBackupCreate(11). Already reduced 13->11 in batch 1; revisit, floor was due to assert count.
