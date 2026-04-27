import hashlib
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from loguru import logger


class HashingWorker(QObject):
    progress = Signal(int)
    finished = Signal(str, str)
    error = Signal(str)

    def __init__(self, file_path: Path):
        super().__init__()
        self.file_path = file_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            logger.info(f"Started hashing: {self.file_path}")
            # Use BLAKE3 if available, otherwise fallback to SHA-256
            if hasattr(hashlib, "blake3"):
                hasher = hashlib.blake3()
                algo = "blake3"
            else:
                hasher = hashlib.sha256()
                algo = "sha256"

            file_size = self.file_path.stat().st_size
            processed = 0

            with open(self.file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    if self._is_cancelled:
                        logger.warning(f"Hashing cancelled for: {self.file_path}")
                        self.error.emit("Cancelled")
                        return
                    hasher.update(chunk)
                    processed += len(chunk)
                    if file_size > 0:
                        self.progress.emit(int((processed / file_size) * 100))

            final_hash = hasher.hexdigest()
            logger.success(f"Finished hashing {self.file_path} ({algo}): {final_hash}")
            self.progress.emit(100)
            self.finished.emit(str(self.file_path), final_hash)
        except Exception as e:
            logger.error(f"Error hashing {self.file_path}: {e}")
            self.error.emit(str(e))
