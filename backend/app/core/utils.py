# backend/app/api/core/utils.py

import datetime as dt

def now():
    return dt.datetime.now()

def utcnow():
    return dt.now(dt.timezone.utc)
