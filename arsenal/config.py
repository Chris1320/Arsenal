import os
from pathlib import Path

from PySide6.QtCore import QSettings


from arsenal import info


def get_config_path() -> Path:
    """Get the path to the configuration file in the user's profile directory."""
    user_profile = Path(
        os.environ.get("USERPROFILE") or os.environ.get("HOME", "~")
    ).expanduser()
    return user_profile / info.DEFAULT_USERDATA_DIRNAME / "config.ini"


def get_log_dir() -> Path:
    """Get the path to the logs directory in the user's profile directory."""
    user_profile = Path(
        os.environ.get("USERPROFILE") or os.environ.get("HOME", "~")
    ).expanduser()
    return user_profile / info.DEFAULT_USERDATA_DIRNAME / "logs"


class ConfigManager:
    """
    Manages application configuration using QSettings
    to store values in an INI file.
    """

    def __init__(self):
        config_path = get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(str(config_path), QSettings.Format.IniFormat)

    def get_arsenal_root(self) -> str:
        return str(self.settings.value("arsenal_root", ""))

    def set_arsenal_root(self, path: str):
        self.settings.setValue("arsenal_root", path)
        self.settings.sync()

    def get_file_operation(self) -> str:
        return str(self.settings.value("file_operation", "Move"))

    def set_file_operation(self, operation: str):
        self.settings.setValue("file_operation", operation)
        self.settings.sync()
