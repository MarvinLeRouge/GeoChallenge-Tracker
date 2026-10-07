# Module size batch - progress checklist

Branch: refactor/module-size-batch
Threshold: 400 non-blank lines. Order: by line count descending, one commit per original file (split into siblings, behavior/public API preserved). maintenance.py moved to the end: splitting it requires updating patch.object targets across ~10 test files (module-level mock patching), higher risk than the rest of the batch.

- [x] (884) backend/tests/unit/test_progress.py - split into _progress_test_helpers.py (shared, 141 lines) + test_progress_ensure_uc_owned.py (27) + test_progress_evaluate.py (314) + test_progress_latest_and_history.py (240) + test_progress_evaluate_new.py (63) + test_progress_tasks_and_attrs.py (51) + test_progress_aggregates.py (168). All patches use string targets ("app.services.progress.X"), not module-object patching, so no patch-target fixes needed. 57/57 tests preserved.
- [ ] (653) backend/app/services/progress.py
- [ ] (639) backend/app/api/routes/caches.py
- [ ] (620) frontend/src/pages/profile/MyProfile.vue
- [ ] (547) backend/tests/integration/test_endpoints_caches.py
- [ ] (524) frontend/src/app/AppShell.vue
- [ ] (492) backend/tests/unit/test_target_service.py
- [ ] (457) frontend/tests/unit/zones-explorer.spec.ts
- [ ] (456) backend/app/services/targets/target_service.py
- [ ] (452) backend/tests/unit/test_target_evaluator.py
- [ ] (438) backend/tests/unit/test_gpx_parsers.py
- [ ] (436) backend/tests/_test_user_challenge_tasks_suite.py
- [ ] (434) backend/tests/unit/test_query_builder.py
- [ ] (433) backend/tests/unit/test_gpx_import_service_main.py
- [ ] (415) frontend/src/pages/userChallenges/Matrix.vue
- [ ] (907) backend/app/api/routes/maintenance.py - split into app/api/routes/maintenance/ package by concern (orphans, cleanup, full_backup, backups, gpx_upload, reports, targets_stats, test_email, _shared). Must update patch.object targets in ~10 affected test files (see list below), verify via full suite.

## maintenance.py: test files with module-level patch.object targets to fix
- tests/unit/test_maintenance_upload_size_limit.py
- tests/unit/test_maintenance_upload_error_branches.py
- tests/unit/test_maintenance_full_backup_create.py
- tests/unit/test_maintenance_restore_errors.py
- tests/unit/test_maintenance_backup_listing.py
- tests/unit/test_maintenance_test_email_default_recipient.py
- tests/unit/test_maintenance_user_targets_and_stats.py
- tests/unit/test_maintenance_restore_confirmation.py
- tests/unit/test_maintenance_db_cleanup.py
- tests/unit/test_maintenance_admin_reports.py
- tests/integration/test_authenticated.py (verify if it patches too)
