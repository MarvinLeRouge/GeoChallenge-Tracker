# Cyclomatic complexity batch - progress checklist

Branch: refactor/cyclomatic-complexity-batch
Order: by cumulative cyclomatic complexity per file (descending), one commit per file.

- [x] (72) app/services/query_builder.py - _compile_size_in(19->6), _extract_aggregate_spec(15->5), _compile_type_in(15->5), _compile_attributes(12->3), _compile_state_in(11->3)
- [x] (67) app/api/routes/maintenance.py - full_backup_restore(23->12), cleanup_analyze(21->7), cleanup_execute(12->3), list_all_backups(11->1). Caught+fixed a bug: extracted helpers inserted between @router decorator and handler broke route registration; fixed by relocating decorators+DONE comments.
- [x] (53) app/services/gpx_import/gpx_import_service.py - import_gpx_payload(18->3), _enrich_with_elevation(13->6), _process_single_gpx_file(11->4), _enrich_with_geocoding(11->5)
- [x] (50) app/services/user_challenge_tasks/task_expression_validator.py - validate_task_expression(25->10), TaskExpressionValidator class metric(13->5), validate_tasks_payload(12->4)
- [x] (46) app/services/progress.py - get_latest_and_history(25->8), _aggregate_total(21->4)
- [x] (42) tests/utils/duplicate_db_for_tests.py - duplicate_db_with_indexes(42->3). No unit test coverage exists (only used by live-DB integration conftest); verified via AST/ruff/mypy/import + print/await count sanity check instead.
- [x] (39) tests/_test_user_challenge_tasks_verbose.py - _render_expression_human(23->4), _sample_referentials(16->1)
- [x] (39) tests/_test_user_challenge_tasks_suite.py - _render_expression_human(23->4), _sample_referentials(16->1)
- [x] (39) app/api/routes/caches.py - by_filter(25->1), upload_gpx(14->2). Caught+fixed the decorator/DONE-comment-swallowing bug twice (proactively this time, verified all 6 route decorators against original pairing).
- [x] (33) app/services/referentials_cache.py - _map_collection(22->2), resolve_state_name(11->4)
- [x] (29) app/services/providers/elevation_opentopo.py - fetch(16->7), _split_params_by_url_and_count(13->4)
- [x] (28) app/services/targets/target_evaluator.py - build_cache_pipeline_for_task(16->5), _get_covered_dt_cells(12->1)
- [x] (28) app/services/cache_validators.py - validate_cache_comprehensive(28->6)
- [x] (25) app/services/matrix_verification.py - verify_user_matrix(25->7)
- [x] (25) app/services/parsers/MultiFormatGPXParser.py - _detect_format(13->6), _extract_cache_data(12->3)
- [x] (25) tests/unit/test_maintenance_full_backup_create.py - TestFullBackupCreate(13->11), test_backs_up_non_empty_non_system_collections_only(12->10). Remaining complexity is from the 8 assert statements themselves (counted as branches here), not business logic; diminishing returns beyond this.
- [x] (22) app/services/calendar_verification.py - verify_user_calendar(22->6)
- [x] (22) app/services/zones/zone_assigner.py - assign_zones_to_caches(22->6)
- [x] (21) app/services/user_stats.py - get_user_stats(21->4)
- [x] (21) app/api/routes/auth.py - login(21->3)
- [x] (19) app/services/gpx_import/data_normalizer.py - extract_cache_metadata(19->1)
- [x] (18) tests/_test_targets_smoke.py - test_targets_e2e_api(18->6). Found and preserved (not fixed, out of scope) a pre-existing bug: get_collection() called without await in several spots; kept new helpers unannotated like the original so mypy keeps skipping their body, same as before.
- [x] (17) app/services/user_challenges/user_challenge_validator.py - validate_patch_operation(17->7)
- [x] (16) backend/scripts/seed_zones.py - main(16->4)
- [x] (16) app/domain/models/challenge_ast.py - preprocess_expression_default_and(16->9). app/domain/models/* is excluded from coverage by .coveragerc; verified via 173 related tests passing + full suite.
- [x] (14) backend/scripts/backfill_country_codes.py - main(14->8)
- [x] (14) app/services/type_helpers.py - get_type_by_name(14->3)
- [x] (14) app/services/gpx_import/file_handler.py - extract_zip_files(14->7)
- [x] (13) backend/scripts/verify_fr_non_regression.py - compare_zones(13->3). Has dedicated tests (tests/unit/scripts/test_verify_fr_non_regression.py, 11 passed).
- [x] (13) app/db/seed_indexes.py - ensure_index(13->4)
- [x] (12) app/services/parsers/HTMLSanitizer.py - _serialize_node(12->6)
- [x] (12) app/api/routes/caches_geocoding.py - backfill_geocoding(12->7)
- [x] (12) tests/unit/test_matrix_verification.py - test_verify_user_matrix_partial(12->9). Extracted the inline Mock*/MockDB classes into a module-level helper (unique to this test, other tests in the file have their own similar inline mocks, left untouched/out of scope).
- [x] (12) tests/unit/test_data_normalizer.py - test_full_extraction(12->3). Converted 11 individual asserts to an expected-values dict + loop.
- [x] (11) app/services/gpx_import/cache_validator.py - validate_found_data(11->1). Extracted _validate_found_date and _validate_found_notes helpers.
- [x] (11) app/services/gpx_import/referential_mapper.py - map_cache_referentials(11->1). Extracted _map_country_and_state, _map_type_and_size, _map_attribute(s).
- [x] (11) app/services/zones/zone_service.py - get_zones_with_counts(11->5). Extracted _build_zone_match_and_group, _aggregate_zone_counts, _build_country_zone_items, _build_level_zone_items.
- [x] (11) app/services/location_parser.py - parse_location_to_lon_lat(11->5). Extracted _parse_simple_dd_fallback and _try_resolve_lat_lon_by_hemisphere, preserving the original's validation-skip on the hemisphere-resolved branches.
- [ ] (11) app/db/seed_data.py - seed_collection(11)

Note: tests/_test_user_challenge_tasks_verbose.py and _suite.py are near-duplicate
manual/debug scripts, not collected by CI (pytest tests/unit/) or default pytest
collection. Verify by running them explicitly, no CI safety net.
