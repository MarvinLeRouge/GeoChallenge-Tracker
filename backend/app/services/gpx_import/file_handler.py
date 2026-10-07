# backend/app/services/gpx_import/file_handler.py
# GPX and ZIP file management — validation, extraction, writing.

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException

# Cumulative cap on decompressed bytes across a whole ZIP archive, enforced while
# streaming (not just checked against the declared, spoofable zip_info.file_size),
# to bound memory/disk usage against a zip-bomb-style archive.
MAX_TOTAL_EXTRACTED_SIZE = 200 * 1024 * 1024  # 200 MB
_EXTRACT_CHUNK_SIZE = 1024 * 1024  # 1 MB


def _default_uploads_dir() -> Path:
    """Resolve the default GPX uploads directory.

    Same container-side path (/app/uploads/gpx) in dev and prod, both running
    under Docker. Falls back to a repo-relative path when running outside a
    container (e.g. CI, native pytest), mirroring backup_config.py's approach.
    """
    if Path("/.dockerenv").exists():
        return Path("/app/uploads/gpx")
    return Path(__file__).resolve().parents[4] / "uploads" / "gpx"


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
        self.uploads_dir = uploads_dir or _default_uploads_dir()
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

    @staticmethod
    def _should_skip_zip_entry(zip_info: zipfile.ZipInfo) -> bool:
        """Decide whether to skip a ZIP entry (not a non-oversized .gpx file).

        Args:
            zip_info: ZIP entry metadata.

        Returns:
            bool: True if this entry should be skipped.
        """
        if zip_info.is_dir():
            return True
        if not zip_info.filename.lower().endswith(".gpx"):
            return True
        if zip_info.file_size > 50 * 1024 * 1024:  # 50MB max
            return True
        return False

    @staticmethod
    def _stream_extract_gpx_entry(
        zip_file: zipfile.ZipFile, zip_info: zipfile.ZipInfo, total_extracted_size: int
    ) -> tuple[bytes, int]:
        """Stream-read one GPX entry, enforcing the cumulative extraction size cap.

        Description:
            Streams in chunks and enforces the cumulative cap as it goes, rather than
            trusting `zip_info.file_size` (part of the attacker-controlled central
            directory) before reading.

        Args:
            zip_file: The open ZIP archive.
            zip_info: The entry to read.
            total_extracted_size: Cumulative bytes extracted so far (across entries).

        Returns:
            tuple[bytes, int]: `(gpx_data, new_total_extracted_size)`.

        Raises:
            HTTPException: 400 if the cumulative cap is exceeded.
        """
        gpx_data = bytearray()
        with zip_file.open(zip_info) as gpx_file:
            while chunk := gpx_file.read(_EXTRACT_CHUNK_SIZE):
                total_extracted_size += len(chunk)
                if total_extracted_size > MAX_TOTAL_EXTRACTED_SIZE:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "ZIP archive exceeds the maximum cumulative "
                            f"extracted size ({MAX_TOTAL_EXTRACTED_SIZE // (1024 * 1024)} MB)"
                        ),
                    )
                gpx_data.extend(chunk)
        return bytes(gpx_data), total_extracted_size

    def _process_zip_entry(
        self,
        zip_file: zipfile.ZipFile,
        zip_info: zipfile.ZipInfo,
        total_extracted_size: int,
        extracted_paths: list[Path],
    ) -> int:
        """Extract one GPX entry (if applicable), writing it and recording its path.

        Description:
            Skips non-GPX/oversized/directory entries. On a cumulative-cap overflow,
            cleans up already-extracted files and re-raises. Other errors are logged
            and the entry is skipped.

        Args:
            zip_file: The open ZIP archive.
            zip_info: The entry to process.
            total_extracted_size: Cumulative bytes extracted so far.
            extracted_paths: Paths extracted so far, mutated in place.

        Returns:
            int: Updated `total_extracted_size`.
        """
        if self._should_skip_zip_entry(zip_info):
            return total_extracted_size

        try:
            # Stream in chunks and enforce the cumulative cap as we go,
            # rather than trusting zip_info.file_size (part of the
            # attacker-controlled central directory) before reading.
            gpx_data, total_extracted_size = self._stream_extract_gpx_entry(
                zip_file, zip_info, total_extracted_size
            )

            # Save the GPX file
            gpx_filename = Path(zip_info.filename).name
            gpx_path = self.write_gpx_file(gpx_data, gpx_filename)
            extracted_paths.append(gpx_path)

        except HTTPException:
            # Cumulative cap exceeded: clean up what was already
            # extracted and abort the whole archive, don't just skip.
            self.cleanup_files(extracted_paths)
            raise
        except Exception as e:
            # Skip corrupt files but continue processing
            print(f"Warning: Failed to extract {zip_info.filename}: {str(e)}")

        return total_extracted_size

    def extract_zip_files(self, data: bytes) -> list[Path]:
        """Extract GPX files from a ZIP archive.

        Args:
            data: ZIP archive data.

        Returns:
            list[Path]: List of paths of extracted GPX files.

        Raises:
            HTTPException: If extraction fails or no GPX files are found.
        """
        extracted_paths: list[Path] = []
        total_extracted_size = 0

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zip_file:
                # Limit the number of files
                if len(zip_file.namelist()) > 100:
                    raise HTTPException(
                        status_code=400, detail="ZIP contains too many files (max 100)"
                    )

                for zip_info in zip_file.infolist():
                    total_extracted_size = self._process_zip_entry(
                        zip_file, zip_info, total_extracted_size, extracted_paths
                    )

        except HTTPException:
            raise
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
