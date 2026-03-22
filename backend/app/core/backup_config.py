import os
from pathlib import Path


def _default_backup_root() -> Path:
    # 1) If an explicit env var is set, use it
    env = os.getenv("BACKUP_DIR")
    if env:
        return Path(env)

    # 2) If running inside Docker, use /backups
    # (indicator file present in most Docker images)
    if Path("/.dockerenv").exists():
        return Path("/backups")

    # 3) Dev outside Docker: repo_root/backups
    # (__file__ = app/core/backup_config.py -> repo_root = parents[3])
    # repo_root/
    # ├── backend/
    # │   └── app/
    # │       └── core/backup_config.py  <-- here
    # └── backups/   (target)
    return Path(__file__).resolve().parents[3] / "backups"


# Backup configuration
BACKUP_ROOT_DIR = _default_backup_root()
CLEANUP_BACKUP_DIR = BACKUP_ROOT_DIR / "db_cleanup"
FULL_BACKUP_DIR = BACKUP_ROOT_DIR / "full_backup"


def ensure_backup_dirs():
    """Creates backup directories if they do not already exist."""
    CLEANUP_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    FULL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Check write permissions
    if not os.access(CLEANUP_BACKUP_DIR, os.W_OK):
        raise PermissionError(f"Cannot write to backup directory: {CLEANUP_BACKUP_DIR}")
