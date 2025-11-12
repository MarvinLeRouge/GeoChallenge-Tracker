import os
from pathlib import Path


def _default_backup_root() -> Path:
    # 1) Si env explicite, on le respecte
    env = os.getenv("BACKUP_DIR")
    if env:
        return Path(env)

    # 2) Si on est DANS Docker, utiliser /backups
    # (fichier indicateur présent dans la plupart des images)
    if Path("/.dockerenv").exists():
        return Path("/backups")

    # 3) Dev HORS Docker: repo_root/backups
    # (__file__ = app/core/config_backup.py -> repo_root = parents[3])
    # repo_root/
    # ├── backend/
    # │   └── app/
    # │       └── core/config_backup.py  <-- ici
    # └── backups/   (cible)
    return Path(__file__).resolve().parents[3] / "backups"


# Configuration des backups
BACKUP_ROOT_DIR = _default_backup_root()
CLEANUP_BACKUP_DIR = BACKUP_ROOT_DIR / "db_cleanup"
FULL_BACKUP_DIR = BACKUP_ROOT_DIR / "full_backup"


def ensure_backup_dirs():
    """Crée les dossiers de backup si nécessaire"""
    CLEANUP_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    FULL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Vérifie les permissions
    if not os.access(CLEANUP_BACKUP_DIR, os.W_OK):
        raise PermissionError(f"Cannot write to backup directory: {CLEANUP_BACKUP_DIR}")


# Initialise au démarrage
ensure_backup_dirs()
