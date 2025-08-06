import os
import sys
import pytest
from dotenv import load_dotenv

if __name__ == "__main__":
    # Charge les variables d'environnement depuis le .env si présent
    load_dotenv(dotenv_path="uv.env")

    # Dossier cible des tests
    test_path = os.path.join(os.path.dirname(__file__), "tests")

    # Lancement de pytest avec les options désirées
    exit_code = pytest.main([test_path, "-v"])
    sys.exit(exit_code)
