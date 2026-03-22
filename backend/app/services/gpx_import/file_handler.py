# backend/app/services/gpx_import/file_handler.py
# GPX and ZIP file management — validation, extraction, writing.

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException


class FileHandler:
    """GPX and ZIP file management service.

    Description:
        Responsible for validating, extracting, and materializing
        GPX files and ZIP archives.
    """

    def __init__(self, uploads_dir: Path | None = None):
        """Initialize the file handler.

        Args:
            uploads_dir: Upload storage directory.
        """
        self.uploads_dir = uploads_dir or Path("../uploads/gpx").resolve()
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    def is_zip_file(self, data: bytes) -> bool:
        """Detect a ZIP file via magic signature.

        Args:
            data: File data.

        Returns:
            bool: True if it is a ZIP, False otherwise.
        """
        return data[:4] == b"PK\x03\x04"

    def safe_join(self, base: Path, *paths: str) -> Path:
        """Join paths while preventing path traversal.

        Args:
            base: Base path.
            *paths: Paths to join.

        Returns:
            Path: Safe joined path.

        Raises:
            ValueError: If a path traversal attempt is detected.
        """
        result = base
        for path in paths:
            result = result / path

        # Verify we remain within the base directory
        try:
            result.resolve().relative_to(base.resolve())
        except ValueError as e:
            raise ValueError(f"Path traversal attempt detected: {path}") from e

        return result

    def validate_gpx_content(self, data: bytes) -> None:
        """Validate the minimal content of a GPX file.

        Args:
            data: GPX file data.

        Raises:
            HTTPException: If the content is not valid.
        """
        if len(data) < 50:
            raise HTTPException(status_code=400, detail="File too small to be a valid GPX")

        # Basic XML/GPX check
        try:
            # Try to parse the first 1000 characters
            sample = data[:1000].decode("utf-8", errors="ignore")
            if "<gpx" not in sample.lower():
                raise HTTPException(
                    status_code=400, detail="Not a valid GPX file (missing <gpx> element)"
                )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid GPX content: {str(e)}") from e

    def validate_gpx_file(self, path: Path) -> None:
        """Validate a GPX file by path.

        Args:
            path: Path to the GPX file.

        Raises:
            HTTPException: If the file is not valid.
        """
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"GPX file not found: {path}")

        if path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail=f"GPX file is empty: {path}")

        # Validate content
        try:
            with open(path, "rb") as f:
                header = f.read(1000)
            self.validate_gpx_content(header)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot read GPX file: {str(e)}") from e

    def write_gpx_file(self, data: bytes, filename: str | None = None) -> Path:
        """Write a single GPX file to disk.

        Args:
            data: GPX file content.
            filename: Optional filename.

        Returns:
            Path: Path of the created file.
        """
        # Validate content first
        self.validate_gpx_content(data)

        # Generate a unique filename
        if filename:
            # Sanitize the filename
            clean_name = "".join(c for c in filename if c.isalnum() or c in ".-_")
            if not clean_name.endswith(".gpx"):
                clean_name += ".gpx"
        else:
            clean_name = f"upload_{uuid.uuid4()}.gpx"

        # Write the file
        file_path = self.uploads_dir / clean_name

        # Avoid name collisions
        counter = 1
        while file_path.exists():
            base_name = clean_name.rsplit(".", 1)[0]
            file_path = self.uploads_dir / f"{base_name}_{counter}.gpx"
            counter += 1

        with open(file_path, "wb") as f:
            f.write(data)

        return file_path

    def extract_zip_files(self, data: bytes) -> list[Path]:
        """Extract GPX files from a ZIP archive.

        Args:
            data: ZIP archive data.

        Returns:
            list[Path]: List of paths of extracted GPX files.

        Raises:
            HTTPException: If extraction fails or no GPX files are found.
        """
        extracted_paths = []

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zip_file:
                # Limit the number of files
                if len(zip_file.namelist()) > 100:
                    raise HTTPException(
                        status_code=400, detail="ZIP contains too many files (max 100)"
                    )

                for zip_info in zip_file.infolist():
                    # Skip directories
                    if zip_info.is_dir():
                        continue

                    # Filter to GPX files only
                    if not zip_info.filename.lower().endswith(".gpx"):
                        continue

                    # Limit individual file size
                    if zip_info.file_size > 50 * 1024 * 1024:  # 50MB max
                        continue

                    # Safe extraction
                    try:
                        with zip_file.open(zip_info) as gpx_file:
                            gpx_data = gpx_file.read()

                        # Save the GPX file
                        gpx_filename = Path(zip_info.filename).name
                        gpx_path = self.write_gpx_file(gpx_data, gpx_filename)
                        extracted_paths.append(gpx_path)

                    except Exception as e:
                        # Skip corrupt files but continue processing
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
        """Materialize files from raw data.

        Args:
            data: File data (GPX or ZIP).
            filename: Optional filename.

        Returns:
            list[Path]: List of created GPX file paths.
        """
        if self.is_zip_file(data):
            return self.extract_zip_files(data)
        else:
            single_file = self.write_gpx_file(data, filename)
            return [single_file]

    def cleanup_file(self, path: Path) -> None:
        """Delete a temporary file.

        Args:
            path: Path of the file to delete.
        """
        try:
            if path.exists():
                path.unlink()
        except Exception:
            # Ignore cleanup errors
            pass

    def cleanup_files(self, paths: list[Path]) -> None:
        """Delete multiple temporary files.

        Args:
            paths: List of file paths to delete.
        """
        for path in paths:
            self.cleanup_file(path)
