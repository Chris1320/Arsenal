import hashlib
from pathlib import Path

from blake3 import blake3
from PySide6.QtCore import QObject, Signal  # pylint: disable=no-name-in-module
from loguru import logger


class HashingWorker(QObject):
    progress = Signal(int)
    finished = Signal(str, str)
    error = Signal(str)

    def __init__(self, file_path: Path, algorithm: str = "BLAKE3"):
        super().__init__()
        self.file_path = file_path
        self.algorithm = algorithm
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            logger.info(f"Started hashing: {self.file_path} using {self.algorithm}")

            algo = self.algorithm.lower()
            if algo == "blake3":
                hasher = blake3(max_threads=blake3.AUTO)
            elif algo == "sha256":
                hasher = hashlib.sha256()
            elif algo == "md5":
                hasher = hashlib.md5()
            elif algo == "sha1":
                hasher = hashlib.sha1()
            else:
                # Fallback to sha256 if selected algorithm is not available or unknown
                hasher = hashlib.sha256()
                algo = "sha256"

            file_size = self.file_path.stat().st_size
            processed = 0

            with open(self.file_path, "rb") as f:
                # Use 1MB chunks to benefit from blake3 multithreading
                for chunk in iter(lambda: f.read(1048576), b""):
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
