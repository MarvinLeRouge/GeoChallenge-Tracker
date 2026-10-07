# Module size batch - progress checklist

Branch: refactor/module-size-batch
Threshold: 400 non-blank lines. Order: by line count descending, one commit per original file (split into siblings, behavior/public API preserved). maintenance.py moved to the end: splitting it requires updating patch.object targets across ~10 test files (module-level mock patching), higher risk than the rest of the batch.

- [x] (884) backend/tests/unit/test_progress.py - split into _progress_test_helpers.py (shared, 141 lines) + test_progress_ensure_uc_owned.py (27) + test_progress_evaluate.py (314) + test_progress_latest_and_history.py (240) + test_progress_evaluate_new.py (63) + test_progress_tasks_and_attrs.py (51) + test_progress_aggregates.py (168). All patches use string targets ("app.services.progress.X"), not module-object patching, so no patch-target fixes needed. 57/57 tests preserved.
- [x] (653) backend/app/services/progress.py - split into progress.py (347 SLOC) + progress_snapshot_helpers.py (202 SLOC, pure builders, not mocked) + progress_aggregates.py (132 SLOC, DB-touching aggregate/count/date helpers, individually mocked by tests). progress.py calls the aggregates module via `progress_aggregates.X(...)` (module-qualified, not `from X import Y`) to keep patch("app.services.progress_aggregates.X") effective. Updated patch targets + local imports in test_progress_aggregates.py, test_progress_evaluate.py, _progress_test_helpers.py accordingly.
- [x] (639) backend/app/api/routes/caches.py - split into caches.py (140 SLOC, upload/import) + caches_search.py (246 SLOC, filter-query building + by_filter) + caches_geo_search.py (162 SLOC, within_bbox/within_radius) + caches_lookup.py (100 SLOC, get_by_gc/get_by_id). All 4 share the same `router` object (imported from .caches). Caught and fixed a critical bug: app/api/routes/__init__.py only imported .caches, so the 3 new submodules' @router decorators never ran in the real app (silent route loss, masked in unit tests which import each submodule directly) - fixed by adding a side-effect import of the 3 new submodules in __init__.py. Verified via tests/integration/test_endpoints_caches.py against the real app: identical 29 passed/4 failed (pre-existing, unrelated) before and after.
- [x] (620) frontend/src/pages/profile/MyProfile.vue - split into MyProfile.vue (154 lines, orchestration) + components/profile/ProfileLocationCard.vue (318 lines, props-driven, no duplicate useUserProfile() call) + components/profile/ProfileFoundCachesSync.vue (174 lines, standalone). Verified via vue-tsc/eslint/prettier, 407 frontend unit tests, and a live browser check (user confirmed /profile/location displays normally). Also fixed an unrelated dev-stack issue found along the way: geo-backend container was running a stale image missing PyJWT (pre-dates this session's pymongo/jose fix merge) - rebuilt via `docker compose up -d --build backend`.
- [x] (547) backend/tests/integration/test_endpoints_caches.py - split by concern (no shared module-level fixtures, straightforward): test_endpoints_caches_upload.py (75 SLOC), test_endpoints_caches_by_filter.py (248 SLOC), test_endpoints_caches_bbox_and_radius.py (159 SLOC), test_endpoints_caches_lookup.py (68 SLOC). 33/33 tests preserved; same 4 pre-existing failures (missing text index in test DB) before and after.
- [x] (524) frontend/src/app/AppShell.vue - split into AppShell.vue (63 lines, header/FAB/router-view/toaster) + AppShellMenuDrawer.vue (91 lines, dialog/overlay/panel shell, open/close via defineExpose) + AppShellMenuNav.vue (386 lines, accordion nav content, emits logout). Verified via vue-tsc/eslint/prettier, 407 frontend unit tests, and a live browser check (user confirmed drawer open/close, accordion sections, theme toggle, and logout all work).
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
