import sys

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from loguru import logger

from arsenal import info
from arsenal.config import ConfigManager, get_log_dir
from arsenal.metadata import MetadataManager
from arsenal.ui import MainWindow


def setup_logging():
    """
    Set up logging to a file in the logs directory with
    rotation and retention policies.
    """

    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_dir / "arsenal_{time}.log"),
        rotation="10 MB",
        retention="7 days",
        level="INFO",
    )


def main():
    """The main entry point for the Arsenal application."""

    app = QApplication(sys.argv)
    app.setApplicationName(info.NAME)
    app.setOrganizationName(info.AUTHOR)

    setup_logging()
    logger.info(f"Starting {info.NAME} Application")

    config_manager = ConfigManager()

    # Check configuration on startup
    if not config_manager.get_arsenal_root():
        msg = QMessageBox()
        msg.setWindowTitle("Initial Setup")
        msg.setText(
            f"No {info.NAME} root folder selected. Please select a root folder to continue."
        )
        msg.exec()

        directory = QFileDialog.getExistingDirectory(
            None, f"Select {info.NAME} Root Directory"
        )
        if directory:
            config_manager.set_arsenal_root(directory)
            logger.info(f"{info.NAME} root set to: {directory}")

        else:
            logger.warning("Setup cancelled. Exiting.")
            sys.exit(0)

    metadata_manager = MetadataManager(config_manager)
    window = MainWindow(config_manager, metadata_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
