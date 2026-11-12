"""Guard for integration tests: only run against a local, disposable MongoDB.

The production cluster and the shared test database live on the same connection,
so a wrong `.env` would make integration tests write next to production data.
"""

LOCAL_MONGO_HOSTS = {"localhost", "127.0.0.1", "::1", "mongo"}
ALLOW_REMOTE_ENV_VAR = "ALLOW_REMOTE_TEST_DB"


def _uri_hosts(uri: str) -> list[str]:
    if "://" not in uri:
        return []
    netloc = uri.split("://", 1)[1].split("/", 1)[0].split("?", 1)[0]
    hosts = []
    for host_port in netloc.rsplit("@", 1)[-1].split(","):
        if host_port.startswith("["):
            hosts.append(host_port[1:].split("]", 1)[0])
        else:
            hosts.append(host_port.rsplit(":", 1)[0])
    return [h for h in hosts if h]


def is_local_mongo_uri(uri: str) -> bool:
    """Return True only if every host of a `mongodb://` URI is local.

    `mongodb+srv://` URIs are always remote (DNS seed list), so they are refused.
    """
    if not uri.startswith("mongodb://"):
        return False
    hosts = _uri_hosts(uri)
    return bool(hosts) and all(h in LOCAL_MONGO_HOSTS for h in hosts)
