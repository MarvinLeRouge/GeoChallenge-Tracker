# backend/app/core/utils.py
# Fonctions temporelles basiques (naive local et aware UTC).

import datetime as dt

def now():
    """Date/heure locale (naive).

    Description:
        Retourne `datetime.now()` sans timezone attachée. Pratique pour usages locaux
        mais à éviter pour les comparaisons cross-TZ (préférer `utcnow()`).

    Returns:
        datetime.datetime: Timestamp local (naive).
    """
    return dt.datetime.now()

def utcnow():
    """Date/heure UTC (timezone-aware).

    Description:
        Retourne `datetime.now(timezone.utc)` avec timezone UTC attachée. Recommandé
        pour les horodatages persistés et les comparaisons.

    Returns:
        datetime.datetime: Timestamp UTC (aware).
    """
    return dt.datetime.now(dt.timezone.utc)
