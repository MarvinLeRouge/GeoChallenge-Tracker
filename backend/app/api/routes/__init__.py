# backend/app/api/routes/__init__.py
# Route package: one module per API resource. The side-effect imports needed
# to register sibling-decorated routes (caches_search/caches_geo_search/
# caches_lookup on .caches's router) and the assembled `routers` list live in
# app.api.router_registry, not here, so this package's own __init__ never
# imports its own children - see that module for why.
