# Cyclomatic complexity batch 2 - progress checklist

Branch: refactor/complexity-batch-2
Threshold: 10. Order: by cumulative cyclomatic complexity per file (descending), one commit per file.

- [x] (144) app/api/routes/maintenance.py - full_backup_restore(12->7). Extracted _restore_all_backup_collections and _build_restore_response.
- [x] (71) app/services/referentials_cache.py - _index_one_collection_document(13->1). Extracted _index_code_field, _index_name_field, _index_aliases_field, _index_numeric_id_field.
- [x] (69) app/api/routes/caches.py - _build_cache_filter_query(21->2). Extracted _apply_simple_equality_filters, _build_min_max_range, _apply_difficulty_terrain_filters, _apply_placed_date_filter, _build_attribute_elem_match, _apply_attribute_filters, _build_bbox_geo_filter.
- [x] (58) app/api/routes/auth.py - _extract_login_credentials(13->3). Extracted _extract_form_credentials and _extract_json_credentials.
- [x] (27) tests/unit/test_maintenance_full_backup_create.py - TestFullBackupCreate(11->10), test_backs_up_non_empty_non_system_collections_only(10->9). Consolidated the 3 response-body assertions (message/total_collections/total_documents) into an expected-values dict + loop; the remaining asserts (status_code, len(backup_files), database, collection keys, 2x not-in) are heterogeneous one-offs, not worth looping.
