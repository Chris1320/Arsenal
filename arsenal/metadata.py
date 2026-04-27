import json
from pathlib import Path

from loguru import logger

from arsenal.config import ConfigManager


class MetadataManager:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.data = {
            "os": [
                "Windows",
                "macOS",
                "Linux",
                "Android",
                "iOS/iPadOS",
                "Cross-Platform",
                "Legacy",
                "Sony PSP",
                "Super Nintendo Entertainment System (SNES)",
                "Firmware/Embedded",
                "Other",
            ],
            "categories": {
                "Accessibility": ["Screen Readers", "Magnifiers", "Alternative Inputs"],
                "Communication": ["Chat Applications", "Social Media", "Email Clients"],
                "Dev & Reverse Engineering": [
                    "Testing Tools",
                    "Debugging",
                    "Decompilers",
                    "Disassemblers",
                ],
                "Development": ["IDEs", "Compilers", "Git Clients", "Database Tools"],
                "Education & Science": [
                    "Calculators",
                    "Simulation Software",
                    "Research Tools",
                ],
                "Emulation": [
                    "Console Emulators",
                    "Virtual Machines",
                    "VMware",
                    "Docker",
                ],
                "Graphics & Design": [
                    "Photoshop",
                    "Vector Art",
                    "3D Modeling",
                    "Blender",
                ],
                "Multimedia: Audio": ["DAWs", "Players", "Converters", "Synthesizers"],
                "Multimedia: Video": [
                    "Video Editors",
                    "Transcoders",
                    "Livestreaming",
                ],
                "Networking & Remote": [
                    "Browsers",
                    "SSH",
                    "FTP",
                    "VPN",
                    "Remote Assistance",
                ],
                "Productivity": ["Office Suites", "Note-Taking", "Calendars"],
                "Security & Privacy": ["Antivirus", "Encryption", "Privacy Cleaners"],
                "Storage & Recovery": ["Disk Utilities", "Recovery Tools"],
                "System & Hardware": [
                    "Device Drivers",
                    "Monitor/Printer Utilities",
                    "Tweaking Tools",
                ],
                "Utilities": ["Archivers", "File Managers", "Benchmarking Tools"],
                "Others": ["Miscellaneous Tools"],
            },
            "genres": {
                "Action": ["Shooters", "Beat 'Em Ups"],
                "Adventure": ["Point-And-Click", "Narrative"],
                "Fighting": ["1v1", "Arena"],
                "Horror": ["Survival", "Psychological"],
                "Metroidvania": ["Exploration-Based Platformers"],
                "Platformer": ["2D/3D Precision"],
                "Puzzle": ["Logic", "Brain Teasers"],
                "Rhythm": ["Music-Based Gameplay"],
                "Roguelike / Roguelite": ["Procedural Generation", "Permadeath"],
                "RPG": ["JRPGs", "CRPGs", "Action-RPGs"],
                "Sandbox / Survival": ["Crafting", "Open-World Survival"],
                "Simulation": ["Life", "Flight", "Driving"],
                "Souls-like": ["High-Difficulty Action-RPGs"],
                "Sports & Racing": [],
                "Strategy": ["RTS", "Turn-Based", "4X"],
                "Tactical Shooter": ["Squad-Based Combat"],
                "Other": [],
            },
        }
        self.load()

    def get_metadata_file(self) -> Path:
        root = self.config_manager.get_arsenal_root()
        if not root:
            return None

        return Path(root) / "metadata.json"

    def load(self):
        metadata_file = self.get_metadata_file()
        if metadata_file and metadata_file.exists():
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    # Merge loaded data with default keys if missing
                    for k in self.data.keys():
                        if k in loaded_data:
                            self.data[k] = loaded_data[k]

                logger.info("Metadata loaded successfully.")

            except Exception as e:
                logger.error(f"Failed to load metadata: {e}")

    def save(self):
        metadata_file = self.get_metadata_file()
        if not metadata_file:
            logger.warning("No arsenal root set, cannot save metadata.")
            return

        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)

            logger.info("Metadata saved successfully.")

        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def get_os_list(self):
        return self.data["os"]

    def get_categories(self):
        return self.data["categories"]

    def get_genres(self):
        return self.data["genres"]

    def set_os_list(self, os_list):
        self.data["os"] = os_list
        self.save()

    def set_categories(self, categories):
        self.data["categories"] = categories
        self.save()

    def set_genres(self, genres):
        self.data["genres"] = genres
        self.save()
