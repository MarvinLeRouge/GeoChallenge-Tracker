# backend/tests/unit/test_dependency_security.py
# Guards against regressing to vulnerable dependency versions flagged by pip-audit.

from importlib.metadata import PackageNotFoundError, distribution, version

import pytest
from packaging.version import Version


class TestDependencySecurity:
    def test_pymongo_is_above_vulnerable_range(self):
        """pymongo < 4.18.2 is affected by CVE-2026-88029/96747/96748/96749."""
        assert Version(version("pymongo")) >= Version("4.18.2")

    def test_python_jose_is_not_installed(self):
        """python-jose 3.5.0 is affected by CVE-2026-85394 with no upstream fix; replaced by PyJWT."""
        with pytest.raises(PackageNotFoundError):
            distribution("python-jose")

    def test_pyjwt_is_installed(self):
        assert version("pyjwt") is not None
