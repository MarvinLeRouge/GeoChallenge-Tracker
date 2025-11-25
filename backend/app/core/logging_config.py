"""Configuration du système de logging centralisé."""

import json
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
import os
import glob

from bson import ObjectId


class CustomJSONEncoder(json.JSONEncoder):
    """Encodeur JSON personnalisé pour gérer ObjectId et datetime."""

    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class DataLogger:
    """Logger spécialisé pour les données lourdes en JSON."""

    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

    def log_data(
        self,
        calling_context: str,
        data: Dict[str, Any],
        user_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log des données lourdes en JSON."""
        today = datetime.now().strftime("%Y-%m-%d")
        json_file = self.logs_dir / f"{today}-data.json"

        entry = {
            "datetime": datetime.now().isoformat(),
            "calling_context": calling_context,
            "user_data": user_data or {},
            "data": data
        }

        # Maintenir un fichier JSON valide au format tableau
        if json_file.exists():
            # Lire le contenu existant et supprimer le crochet fermant final
            with open(json_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Retirer les espaces blancs et le dernier crochet fermant
            content = content.rstrip()
            if content.endswith(']'):
                content = content[:-1]  # Supprimer ']'
                # Ajouter une virgule si ce n'est pas le premier élément
                if content.rstrip().endswith('}'):
                    content += ','
            elif content.endswith('}'):
                content += ','

            # Réécrire le fichier avec la nouvelle entrée
            with open(json_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.write(json.dumps(entry, cls=CustomJSONEncoder))
                f.write(']')
        else:
            # Créer un nouveau fichier avec le tableau JSON contenant l'entrée
            with open(json_file, "w", encoding="utf-8") as f:
                f.write('[')
                f.write(json.dumps(entry, cls=CustomJSONEncoder))
                f.write(']')


def setup_logging() -> tuple[logging.Logger, logging.Logger, DataLogger]:
    """Configure le système de logging avec rotation quotidienne.

    Returns:
        tuple: (logger_generic, logger_errors, data_logger)
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Nettoyage des logs anciens (> 30 jours)
    cleanup_old_logs(logs_dir)

    # Format des logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Logger générique (INFO+)
    generic_logger = logging.getLogger("geocaching.generic")
    generic_logger.setLevel(logging.INFO)

    if not generic_logger.handlers:  # Éviter les doublons
        generic_handler = logging.handlers.TimedRotatingFileHandler(
            filename=logs_dir / "generic.log",
            when="midnight",
            interval=1,
            encoding="utf-8"
        )
        generic_handler.suffix = "%Y-%m-%d"
        generic_handler.setFormatter(formatter)
        generic_logger.addHandler(generic_handler)

    # Logger erreurs (ERROR+)
    error_logger = logging.getLogger("geocaching.errors")
    error_logger.setLevel(logging.ERROR)

    if not error_logger.handlers:  # Éviter les doublons
        error_handler = logging.handlers.TimedRotatingFileHandler(
            filename=logs_dir / "errors.log",
            when="midnight",
            interval=1,
            encoding="utf-8"
        )
        error_handler.suffix = "%Y-%m-%d"
        error_handler.setFormatter(formatter)
        error_logger.addHandler(error_handler)

    # Data logger pour JSON
    data_logger = DataLogger(str(logs_dir))

    return generic_logger, error_logger, data_logger


def cleanup_old_logs(logs_dir: Path, retention_days: int = 30) -> None:
    """Supprime les logs plus anciens que retention_days."""
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    # Patterns de fichiers à nettoyer
    patterns = [
        f"{logs_dir}/*-generic.log*",
        f"{logs_dir}/*-errors.log*",
        f"{logs_dir}/*-data.json",
        f"{logs_dir}/generic.log*",
        f"{logs_dir}/errors.log*"
    ]

    for pattern in patterns:
        for file_path in glob.glob(pattern):
            file_name = os.path.basename(file_path)

            # Extraire la date du nom de fichier
            for date_part in file_name.split('-'):
                if len(date_part) == 10 and date_part.count('-') == 2:
                    try:
                        if date_part < cutoff_str:
                            os.remove(file_path)
                            print(f"Supprimé: {file_path}")
                        break
                    except (ValueError, OSError):
                        continue


# Instance globale (lazy initialization)
_loggers: Optional[tuple[logging.Logger, logging.Logger, DataLogger]] = None


def get_loggers() -> tuple[logging.Logger, logging.Logger, DataLogger]:
    """Retourne les loggers configurés (singleton)."""
    global _loggers
    if _loggers is None:
        _loggers = setup_logging()
    return _loggers


def extract_user_data(user_id: Optional[ObjectId] = None, request = None) -> Dict[str, Any]:
    """Extrait les données utilisateur pour le logging."""
    user_data = {}

    if user_id:
        user_data["user_id"] = user_id

    if request:
        # IP depuis FastAPI request
        if hasattr(request, 'client') and request.client:
            user_data["ip"] = request.client.host

        # User-Agent optionnel
        if hasattr(request, 'headers'):
            user_agent = request.headers.get("user-agent")
            if user_agent:
                user_data["user_agent"] = user_agent

    return user_data