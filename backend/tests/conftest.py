"""
Configuration pytest globale
"""

import logging
import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def configure_logging_for_tests():
    """
    Configure le logging pour les tests : console uniquement, pas de fichiers
    """
    # Désactiver tous les handlers existants
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Handler console simple pour les tests
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)  # Seulement WARNING+ en tests
    formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.WARNING)

    yield
