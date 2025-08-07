import os
import secrets

ENV_PATH = ".env"
SECRET_KEY_NAME = "JWT_SECRET_KEY"
ANCHOR_COMMENT = "# Auth"

def generate_secret_key(bits: int = 512) -> str:
    return secrets.token_hex(bits // 8)

def env_key_exists(path: str, key: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, "r") as f:
        return any(line.strip().startswith(f"{key}=") for line in f)

def insert_key_after_anchor(path: str, key: str, value: str, anchor: str) -> bool:
    if not os.path.exists(path):
        return False

    with open(path, "r") as f:
        lines = f.readlines()

    inserted = False
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if not inserted and line.strip() == anchor:
            new_lines.append(f"{key}={value}\n")
            inserted = True

    if not inserted:
        # append at the end
        new_lines.append(f"\n{key}={value}\n")

    with open(path, "w") as f:
        f.writelines(new_lines)

    return inserted

if __name__ == "__main__":
    if env_key_exists(ENV_PATH, SECRET_KEY_NAME):
        print(f"🔐 Clé {SECRET_KEY_NAME} déjà définie dans {ENV_PATH}. Aucune modification.")
    else:
        new_key = generate_secret_key()
        inserted = insert_key_after_anchor(ENV_PATH, SECRET_KEY_NAME, new_key, ANCHOR_COMMENT)
        if inserted:
            print(f"✅ Clé {SECRET_KEY_NAME} ajoutée après '{ANCHOR_COMMENT}' dans {ENV_PATH}.")
        else:
            print(f"⚠️ Aucun marqueur '{ANCHOR_COMMENT}' trouvé. Clé ajoutée à la fin de {ENV_PATH}.")
