# backend/app/services/gpx_import/file_handler.py
# Gestion des fichiers GPX et ZIP - validation, extraction, écriture.

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException


class FileHandler:
    """Service de gestion des fichiers GPX et ZIP.

    Description:
        Responsable de la validation, extraction et matérialisation
        des fichiers GPX et archives ZIP.
    """

    def __init__(self, uploads_dir: Path | None = None):
        """Initialiser le gestionnaire de fichiers.

        Args:
            uploads_dir: Répertoire de stockage des uploads.
        """
        self.uploads_dir = uploads_dir or Path("../uploads/gpx").resolve()
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    def is_zip_file(self, data: bytes) -> bool:
        """Détecter un fichier ZIP via signature magique.

        Args:
            data: Données du fichier.

        Returns:
            bool: True si c'est un ZIP, False sinon.
        """
        return data[:4] == b"PK\x03\x04"

    def safe_join(self, base: Path, *paths: str) -> Path:
        """Joindre des chemins en empêchant le path traversal.

        Args:
            base: Chemin de base.
            *paths: Chemins à joindre.

        Returns:
            Path: Chemin sécurisé.

        Raises:
            ValueError: Si tentative de path traversal.
        """
        result = base
        for path in paths:
            result = result / path

        # Vérifier qu'on reste dans le répertoire de base
        try:
            result.resolve().relative_to(base.resolve())
        except ValueError as e:
            raise ValueError(f"Path traversal attempt detected: {path}") from e

        return result

    def validate_gpx_content(self, data: bytes) -> None:
        """Valider le contenu minimal d'un fichier GPX.

        Args:
            data: Données du fichier GPX.

        Raises:
            HTTPException: Si le contenu n'est pas valide.
        """
        if len(data) < 50:
            raise HTTPException(status_code=400, detail="File too small to be a valid GPX")

        # Vérification basique XML/GPX
        try:
            # Essayer de parser les 1000 premiers caractères
            sample = data[:1000].decode("utf-8", errors="ignore")
            if "<gpx" not in sample.lower():
                raise HTTPException(
                    status_code=400, detail="Not a valid GPX file (missing <gpx> element)"
                )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid GPX content: {str(e)}") from e

    def validate_gpx_file(self, path: Path) -> None:
        """Valider un fichier GPX par son chemin.

        Args:
            path: Chemin vers le fichier GPX.

        Raises:
            HTTPException: Si le fichier n'est pas valide.
        """
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"GPX file not found: {path}")

        if path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail=f"GPX file is empty: {path}")

        # Valider le contenu
        try:
            with open(path, "rb") as f:
                header = f.read(1000)
            self.validate_gpx_content(header)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot read GPX file: {str(e)}") from e

    def write_gpx_file(self, data: bytes, filename: str | None = None) -> Path:
        """Écrire un fichier GPX unique sur disque.

        Args:
            data: Contenu du fichier GPX.
            filename: Nom de fichier optionnel.

        Returns:
            Path: Chemin du fichier créé.
        """
        # Valider d'abord le contenu
        self.validate_gpx_content(data)

        # Générer un nom de fichier unique
        if filename:
            # Nettoyer et sécuriser le nom de fichier
            clean_name = "".join(c for c in filename if c.isalnum() or c in ".-_")
            if not clean_name.endswith(".gpx"):
                clean_name += ".gpx"
        else:
            clean_name = f"upload_{uuid.uuid4()}.gpx"

        # Écrire le fichier
        file_path = self.uploads_dir / clean_name

        # Éviter les collisions de noms
        counter = 1
        while file_path.exists():
            base_name = clean_name.rsplit(".", 1)[0]
            file_path = self.uploads_dir / f"{base_name}_{counter}.gpx"
            counter += 1

        with open(file_path, "wb") as f:
            f.write(data)

        return file_path

    def extract_zip_files(self, data: bytes) -> list[Path]:
        """Extraire les fichiers GPX d'une archive ZIP.

        Args:
            data: Données de l'archive ZIP.

        Returns:
            list[Path]: Liste des chemins des fichiers GPX extraits.

        Raises:
            HTTPException: Si l'extraction échoue ou aucun GPX trouvé.
        """
        extracted_paths = []

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zip_file:
                # Limiter le nombre de fichiers
                if len(zip_file.namelist()) > 100:
                    raise HTTPException(
                        status_code=400, detail="ZIP contains too many files (max 100)"
                    )

                for zip_info in zip_file.infolist():
                    # Ignorer les répertoires
                    if zip_info.is_dir():
                        continue

                    # Filtrer les fichiers GPX
                    if not zip_info.filename.lower().endswith(".gpx"):
                        continue

                    # Limiter la taille des fichiers individuels
                    if zip_info.file_size > 50 * 1024 * 1024:  # 50MB max
                        continue

                    # Extraction sécurisée
                    try:
                        with zip_file.open(zip_info) as gpx_file:
                            gpx_data = gpx_file.read()

                        # Sauvegarder le fichier GPX
                        gpx_filename = Path(zip_info.filename).name
                        gpx_path = self.write_gpx_file(gpx_data, gpx_filename)
                        extracted_paths.append(gpx_path)

                    except Exception as e:
                        # Ignorer les fichiers corrompus mais continuer
                        print(f"Warning: Failed to extract {zip_info.filename}: {str(e)}")
                        continue

        except zipfile.BadZipFile as e:
            raise HTTPException(status_code=400, detail="Invalid ZIP file") from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ZIP extraction failed: {str(e)}") from e

        if not extracted_paths:
            raise HTTPException(status_code=400, detail="No valid GPX files found in ZIP archive")

        return extracted_paths

    def materialize_files(self, data: bytes, filename: str | None = None) -> list[Path]:
        """Matérialiser les fichiers depuis les données brutes.

        Args:
            data: Données du fichier (GPX ou ZIP).
            filename: Nom de fichier optionnel.

        Returns:
            list[Path]: Liste des chemins des fichiers GPX créés.
        """
        if self.is_zip_file(data):
            return self.extract_zip_files(data)
        else:
            single_file = self.write_gpx_file(data, filename)
            return [single_file]

    def cleanup_file(self, path: Path) -> None:
        """Supprimer un fichier temporaire.

        Args:
            path: Chemin du fichier à supprimer.
        """
        try:
            if path.exists():
                path.unlink()
        except Exception:
            # Ignorer les erreurs de nettoyage
            pass

    def cleanup_files(self, paths: list[Path]) -> None:
        """Supprimer plusieurs fichiers temporaires.

        Args:
            paths: Liste des chemins à supprimer.
        """
        for path in paths:
            self.cleanup_file(path)
