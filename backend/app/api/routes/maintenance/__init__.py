# app/api/routes/maintenance/__init__.py
# Maintenance route package: admin-only DB maintenance, backup/restore, and
# diagnostic endpoints, split by concern into sibling modules that all
# decorate the shared `router` defined in ._router.
#
# This file deliberately imports nothing from its own package (not even
# ._router): a submodule always needs its parent package initialized first,
# so any import written here would form a cycle with that submodule. Both
# the `router` object and the side-effect imports of the sibling modules are
# wired from app.api.router_registry instead, which sits outside this
# package entirely.
