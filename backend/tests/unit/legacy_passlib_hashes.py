"""Real hashes produced by passlib 1.7.4 (the library used before CHORE-001).

Generated once with `CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")`
and argon2-cffi 25.1.0 / bcrypt 4.0.1, so the tests prove that every hash format
stored in production keeps verifying without passlib installed.
"""

PASSWORD = "Secure123!"

# passlib argon2 defaults: argon2id, m=65536, t=3, p=4.
ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$2lurtVbqfU/pvXfOGWNsjQ$WD+lVwKmWyZIOGVLjuU/evH4rCh1cJzVbc68yn5ZJfQ"

# passlib bcrypt default ident ($2b$), 12 rounds.
BCRYPT_HASH = "$2b$12$ELJMXyUIgdRpbB2nZ6ce/ewR9YxFfL4EFGbDbuioE/b49zLNc3.Ry"

# Older $2a$ ident, also produced by passlib when configured for it.
BCRYPT_2A_HASH = "$2a$12$q3YQyOWUPsLAY.nUMk0XkOPg.UeTkK/aS.ygwV.OC37oXCHIC5bty"

# 84 UTF-8 bytes: passlib silently hashed only the first 72 bytes ("é" * 36).
LONG_PASSWORD = "é" * 40 + "tail"
LONG_PASSWORD_TRUNCATED = "é" * 36
BCRYPT_LONG_HASH = "$2b$12$BmS0nEqnZ9TG5hMwO6g3QeH1/p0Jsm8wPeoJ6hTyXVOYiGlDE7aXC"
