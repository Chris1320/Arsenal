import json
from pathlib import Path

from loguru import logger

from arsenal.config import ConfigManager


class MetadataManager:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.data: dict[str, list[str] | dict[str, list[str]]] = {
            "os": [
                "Windows",
                "Linux",
                "macOS",
                "Android",
                "iOS",
                "Cross-Platform",
                "Firmware/Embedded",
                "Sony PSP",
                "Super Nintendo Entertainment System (SNES)",
                "Other",
            ],
            "categories": {
                "Accessibility": [],
                "Communication": ["Chat Applications", "Email Clients", "Social Media"],
                "Crackers & Keygens": ["Emulators", "Keygens", "Patchers & Bypassers"],
                "Customization": ["Icon Packs", "Themes"],
                "Device Drivers": [
                    "Graphics Drivers",
                    "Graphics Tablet Drivers",
                    "Network Drivers",
                    "Printer Drivers",
                ],
                "Disk Utilities": [
                    "Cloning Tools",
                    "Defragmenters",
                    "Partition Managers",
                ],
                "Education & Science": [
                    "Calculators",
                    "Research Tools",
                    "Simulation Software",
                ],
                "Emulators": [
                    "Console Emulators",
                    "Containerization",
                    "Virtual Machines",
                ],
                "File Management": [
                    "File Managers",
                    "File Recovery",
                    "File Synchronization",
                    "FTP Clients",
                    "WebDAV Clients",
                ],
                "Libraries": [
                    "Frameworks",
                    "Runtime Environments",
                    "Software Development Kits (SDKs)",
                ],
                "Media": [
                    "Audio Players",
                    "Audio Synthesizers",
                    "Graphic Design",
                    "Image Viewers",
                    "Video Players",
                ],
                "Media Editing": [
                    "3D Modeling",
                    "Digital Audio Workstations (DAWs)",
                    "Image Editors",
                    "Livestreaming",
                    "Plugins & Effects",
                    "Transcoders",
                    "Video Editors",
                ],
                "Monitor Utilities": [
                    "Color Calibration",
                    "Multi-Monitor Management",
                    "Other Monitor Tools",
                ],
                "Networking": [
                    "Browsers",
                    "Firewalls",
                    "FTP Clients",
                    "Network Analyzers",
                    "SSH Clients",
                    "VPN Clients",
                ],
                "Others": [
                    "Miscellaneous Tools",
                    "Operating Systems",
                    "Other Software",
                ],
                "Printer Utilities": [
                    "Other Printer Tools",
                    "Print Spoolers",
                    "Printer Maintenance",
                ],
                "Productivity": [
                    "Calendars",
                    "Note-Taking",
                    "Office Suites",
                ],
                "Remote Assistance": [
                    "Remote Desktop",
                    "Remote Input",
                ],
                "Reverse Engineering": [
                    "Debuggers",
                    "Decompilers",
                    "Disassemblers",
                ],
                "Security & Privacy": [
                    "Antivirus",
                    "Encryption",
                    "Privacy Cleaners",
                ],
                "Software Development": [
                    "Compilers",
                    "Database Tools",
                    "Debugging Tools",
                    "Git Clients",
                    "Integrated Development Environments (IDEs)",
                    "Other Development Tools",
                ],
                "Testing Tools": [
                    "Keyboard Testers",
                    "Mouse Testers",
                ],
                "Utilities": [
                    "Archivers",
                    "Benchmarking Tools",
                ],
            },
            "genres": {
                "Action Role-Playing": [],
                "Adult Only": [],
                "Anime": [],
                "Arcade & Rhythm": [],
                "Building & Automation Sims": [],
                "Card & Board": [],
                "Casual": [],
                "City & Settlement Builders": [],
                "Dating Sims": [],
                "Farming & Crafting Sims": [],
                "Fighting & Martial Arts": [],
                "First-Person Shooter": [],
                "Hobby & Job Sims": [],
                "Horror": [],
                "Individual Sports": [],
                "Life & Immersive Sims": [],
                "Military Strategy": [],
                "Mystery & Detective": [],
                "Open World": [],
                "Platformers & Runners": [],
                "Racing": [],
                "Racing Sim": [],
                "Real-Time Strategy": [],
                "Rogue-Likes & Rogue-Lites": [],
                "Sandbox & Physics Sims": [],
                "Sci-Fi & Cyberpunk": [],
                "Space & Flight Sims": [],
                "Sports Sims & Sports Managers": [],
                "Strategy & Tactical Role-Playing": [],
                "Survival": [],
                "Team Sports": [],
                "Third-Person Shooter": [],
                "Tower Defense": [],
                "Turn-Based Role-Playing": [],
                "Turn-Based Strategy": [],
                "Visual Novels": [],
            },
        }
        self.load()

    def get_metadata_file(self) -> Path | None:
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
                    for k in self.data:
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

    def get_os_list(self) -> list[str]:
        return self.data["os"]  # pyright: ignore[reportReturnType]

    def get_categories(self) -> dict[str, list[str]]:
        return self.data["categories"]  # pyright: ignore[reportReturnType]

    def get_genres(self) -> dict[str, list[str]]:
        return self.data["genres"]  # pyright: ignore[reportReturnType]

    def set_os_list(self, os_list: list[str]):
        self.data["os"] = os_list
        self.save()

    def set_categories(self, categories: dict[str, list[str]]):
        self.data["categories"] = categories
        self.save()

    def set_genres(self, genres: dict[str, list[str]]):
        self.data["genres"] = genres
        self.save()
