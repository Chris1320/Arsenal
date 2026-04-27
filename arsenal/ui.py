import os
import sys
import shutil
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QLineEdit,
    QTextEdit,
    QFileDialog,
    QProgressBar,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QRadioButton,
    QButtonGroup,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, QSize
from PySide6.QtGui import QPixmap, QIcon
from loguru import logger

from arsenal import info
from arsenal.config import ConfigManager
from arsenal.metadata import MetadataManager
from arsenal.hashing import HashingWorker
from arsenal.category_manager import CategoryManagerWidget


class AddEntryWidget(QWidget):
    """
    Widget for adding a new application or game entry to the Arsenal archive.
    """

    def __init__(
        self, config_manager: ConfigManager, metadata_manager: MetadataManager
    ):
        super().__init__()
        self.config_manager = config_manager
        self.metadata_manager = metadata_manager
        self._init_ui()
        self.files_to_hash = []
        self.hashing_thread = None
        self.hashing_worker = None

        self.icon_path: str | None = None
        self.cover_path: str | None = None
        self.installer_path: Path | None = None
        self.installer_hash: str | None = None

    def refresh_data(self):
        """Refresh dynamic data like OS list and categories from metadata manager."""
        self.os_input.clear()
        self.os_input.addItems(self.metadata_manager.get_os_list())
        self._update_category_list()

    def _init_ui(self):
        """Initialize the UI components for the Add Entry form."""
        layout = QVBoxLayout()

        # Type Selection (Application vs Game)
        type_group_box = QGroupBox("Entry Type")
        type_layout = QHBoxLayout()
        self.radio_app = QRadioButton("Application")
        self.radio_game = QRadioButton("Game")
        self.radio_app.setChecked(True)
        self.entry_type_group = QButtonGroup()
        self.entry_type_group.addButton(self.radio_app)
        self.entry_type_group.addButton(self.radio_game)
        type_layout.addWidget(self.radio_app)
        type_layout.addWidget(self.radio_game)
        type_group_box.setLayout(type_layout)

        self.radio_app.toggled.connect(self._update_category_list)

        layout.addWidget(type_group_box)

        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.version_input = QLineEdit()
        self.author_input = QLineEdit()
        self.os_input = QComboBox()
        self.os_input.addItems(self.metadata_manager.get_os_list())

        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Version:", self.version_input)
        form_layout.addRow("Author:", self.author_input)
        form_layout.addRow("OS:", self.os_input)

        # Categories/Genres Dialog Setup
        self.category_dialog = QDialog(self)
        self.category_dialog.setWindowTitle("Select Categories/Genres")
        self.category_dialog.resize(400, 500)
        cat_dlg_layout = QVBoxLayout(self.category_dialog)
        self.category_list = QTreeWidget()
        self.category_list.setHeaderHidden(True)
        cat_dlg_layout.addWidget(self.category_list)
        cat_close_btn = QPushButton("Done")
        cat_close_btn.clicked.connect(self.category_dialog.accept)
        cat_dlg_layout.addWidget(cat_close_btn)

        self.category_btn = QPushButton("Select...")
        self.category_dialog.finished.connect(self._update_category_label)
        self.category_btn.clicked.connect(self.category_dialog.exec)
        self.category_label = QLabel("0 selected")
        cat_layout = QHBoxLayout()
        cat_layout.addWidget(self.category_btn)
        cat_layout.addWidget(self.category_label)
        cat_layout.addStretch()

        form_layout.addRow("Categories/Genres:", cat_layout)
        self._update_category_list()

        # Description Dialog Setup
        self.desc_dialog = QDialog(self)
        self.desc_dialog.setWindowTitle("Edit Description")
        self.desc_dialog.resize(700, 500)
        desc_dlg_layout = QVBoxLayout(self.desc_dialog)
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Markdown supported description...")
        desc_dlg_layout.addWidget(self.desc_input)
        desc_close_btn = QPushButton("Done")
        desc_close_btn.clicked.connect(self.desc_dialog.accept)
        desc_dlg_layout.addWidget(desc_close_btn)

        self.desc_btn = QPushButton("Edit...")
        self.desc_dialog.finished.connect(self._update_desc_label)
        self.desc_btn.clicked.connect(self.desc_dialog.exec)
        self.desc_label = QLabel("Empty")

        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        desc_layout.addWidget(self.desc_btn)
        desc_layout.addWidget(self.desc_label)
        desc_layout.addStretch()

        # Notes Dialog Setup
        self.notes_dialog = QDialog(self)
        self.notes_dialog.setWindowTitle("Edit Instructions/Notes")
        self.notes_dialog.resize(700, 500)
        notes_dlg_layout = QVBoxLayout(self.notes_dialog)
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Markdown supported notes...")
        notes_dlg_layout.addWidget(self.notes_input)
        notes_close_btn = QPushButton("Done")
        notes_close_btn.clicked.connect(self.notes_dialog.accept)
        notes_dlg_layout.addWidget(notes_close_btn)

        self.notes_btn = QPushButton("Edit...")
        self.notes_dialog.finished.connect(self._update_notes_label)
        self.notes_btn.clicked.connect(self.notes_dialog.exec)
        self.notes_label = QLabel("Empty")

        notes_layout = QHBoxLayout()
        notes_layout.addWidget(QLabel("Installation Instructions/Notes:"))
        notes_layout.addWidget(self.notes_btn)
        notes_layout.addWidget(self.notes_label)
        notes_layout.addStretch()

        image_layout = QHBoxLayout()
        self.cover_lbl = QLabel("Cover (Portrait)")
        self.cover_lbl.setAlignment(Qt.AlignCenter)
        self.cover_lbl.setStyleSheet(
            "border: 1px dashed gray; min-width: 120px; min-height: 180px;"
        )
        self.cover_btn = QPushButton("Select Cover...")
        self.cover_btn.clicked.connect(self._select_cover)

        self.icon_lbl = QLabel("Icon (1:1)")
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet(
            "border: 1px dashed gray; min-width: 120px; min-height: 120px;"
        )
        self.icon_btn = QPushButton("Select Icon...")
        self.icon_btn.clicked.connect(self._select_icon)

        cv_vbox = QVBoxLayout()
        cv_vbox.addWidget(self.cover_lbl)
        cv_vbox.addWidget(self.cover_btn)

        ic_vbox = QVBoxLayout()
        ic_vbox.addWidget(self.icon_lbl)
        ic_vbox.addWidget(self.icon_btn)

        image_layout.addLayout(cv_vbox)
        image_layout.addLayout(ic_vbox)

        # Screenshots UI
        self.screenshot_btn = QPushButton("Select Screenshots...")
        self.screenshot_btn.clicked.connect(self._select_screenshots)
        self.screenshot_label = QLabel("0 screenshots selected.")

        # File and Hash UI
        self.file_btn = QPushButton("Select Installation File(s)...")
        self.file_btn.clicked.connect(self._select_files)
        self.file_label = QLabel("No files selected.")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.hide()

        self.submit_btn = QPushButton("Add Entry")
        self.submit_btn.clicked.connect(self._save_entry)

        layout.addLayout(form_layout)
        layout.addLayout(desc_layout)
        layout.addLayout(notes_layout)
        layout.addLayout(image_layout)
        layout.addWidget(self.screenshot_btn)
        layout.addWidget(self.screenshot_label)
        layout.addWidget(self.file_btn)
        layout.addWidget(self.file_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

        self.cover_path = None
        self.icon_path = None
        self.screenshot_paths = []
        self.installer_paths = []
        self.installer_hashes = {}
        self._current_hash_index = 0

    def _update_category_list(self):
        """
        Update the category/genre list based on whether
        "Application" or "Game" is selected.
        """

        self.category_list.clear()
        if self.radio_game.isChecked():
            data_dict = self.metadata_manager.get_genres()
        else:
            data_dict = self.metadata_manager.get_categories()

        for main_cat, sub_cats in data_dict.items():
            parent = QTreeWidgetItem(self.category_list)
            parent.setText(0, main_cat)
            parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.Unchecked)

            for sub_cat in sub_cats:
                child = QTreeWidgetItem(parent)
                child.setText(0, sub_cat)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)

        self.category_list.expandAll()

    def _update_category_label(self):
        selected_categories = 0
        root_count = self.category_list.topLevelItemCount()
        for i in range(root_count):
            parent = self.category_list.topLevelItem(i)
            if parent.checkState(0) == Qt.Checked:
                selected_categories += 1
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.Checked:
                    selected_categories += 1
        self.category_label.setText(f"{selected_categories} selected")

    def _update_desc_label(self):
        if self.desc_input.toPlainText().strip():
            self.desc_label.setText("Provided")
        else:
            self.desc_label.setText("Empty")

    def _update_notes_label(self):
        if self.notes_input.toPlainText().strip():
            self.notes_label.setText("Provided")
        else:
            self.notes_label.setText("Empty")

    def _select_cover(self):
        """Open file dialog to select a cover image and display it in the UI."""
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Cover", "", "Images (*.png *.jpg *.jpeg)"
        )
        if fname:
            self.cover_path = fname
            self.cover_lbl.setPixmap(
                QPixmap(fname).scaled(120, 180, Qt.KeepAspectRatio)
            )

    def _select_icon(self):
        """Open file dialog to select an icon image and display it in the UI."""
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Icon", "", "Images (*.png *.jpg *.jpeg)"
        )
        if fname:
            self.icon_path = fname
            self.icon_lbl.setPixmap(QPixmap(fname).scaled(120, 120, Qt.KeepAspectRatio))

    def _select_screenshots(self):
        fnames, _ = QFileDialog.getOpenFileNames(
            self, "Select Screenshots", "", "Images (*.png *.jpg *.jpeg)"
        )
        if fnames:
            self.screenshot_paths = [Path(f) for f in fnames]
            self.screenshot_label.setText(
                f"{len(self.screenshot_paths)} screenshots selected."
            )

    def _select_files(self):
        """
        Open file dialog to select multiple installation files, start
        hashing process, and update the UI accordingly.
        """

        fnames, _ = QFileDialog.getOpenFileNames(self, "Select Installer(s)")
        if fnames:
            self.installer_paths = [Path(f) for f in fnames]
            self.file_label.setText(
                f"{len(self.installer_paths)} file(s) selected (Hashing...)"
            )
            self.progress_bar.show()
            self.progress_bar.setValue(0)
            self.submit_btn.setEnabled(False)
            self.installer_hashes = {}
            self._current_hash_index = 0

            self._hash_next_file()

    def _hash_next_file(self):
        if self._current_hash_index < len(self.installer_paths):
            current_path = self.installer_paths[self._current_hash_index]
            self.file_label.setText(
                f"Hashing File {self._current_hash_index + 1}/{len(self.installer_paths)}: {current_path.name}"
            )
            self.progress_bar.setValue(0)
            self._start_hashing(current_path)
        else:
            self.file_label.setText(
                f"{len(self.installer_paths)} file(s) ready to add."
            )
            self.progress_bar.hide()
            self.submit_btn.setEnabled(True)

    def _start_hashing(self, path: Path):
        """Start the hashing process in a separate thread to avoid blocking the UI."""
        self.hashing_thread = QThread()
        self.hashing_worker = HashingWorker(path)
        self.hashing_worker.moveToThread(self.hashing_thread)

        self.hashing_thread.started.connect(self.hashing_worker.run)
        self.hashing_worker.progress.connect(self.progress_bar.setValue)
        self.hashing_worker.finished.connect(self._hash_finished)
        self.hashing_worker.error.connect(self._hash_error)

        self.hashing_worker.finished.connect(self.hashing_thread.quit)
        self.hashing_worker.finished.connect(self.hashing_worker.deleteLater)
        self.hashing_worker.error.connect(self.hashing_thread.quit)
        self.hashing_worker.error.connect(self.hashing_worker.deleteLater)

        self.hashing_thread.finished.connect(self.hashing_thread.deleteLater)
        self.hashing_thread.finished.connect(self._on_thread_finished)

        self.hashing_thread.start()

    def _on_thread_finished(self):
        self._current_hash_index += 1
        self._hash_next_file()

    def _hash_finished(self, path: str, result_hash: str):
        """Handle completion of hashing, update UI with hash result."""
        self.installer_hashes[path] = result_hash
        logger.info(f"Hashing completed for {path}. Hash: {result_hash}")

    def _hash_error(self, err: str):
        """Handle hashing errors by updating the UI and continuing."""
        logger.error(f"Hash error: {err}")

    def _save_entry(self):
        """
        Save the new entry by creating the appropriate directory
        structure, writing the README, and copying files.
        """

        root: str = self.config_manager.get_arsenal_root()
        if not root:
            QMessageBox.warning(self, "Error", "Arsenal root not configured.")
            return

        name = self.name_input.text().strip()
        os_sys = self.os_input.currentText()
        selected_categories = []

        # Traverse tree for checked items
        root_count = self.category_list.topLevelItemCount()
        for i in range(root_count):
            parent = self.category_list.topLevelItem(i)
            if parent.checkState(0) == Qt.Checked:
                selected_categories.append(parent.text(0))
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.Checked:
                    selected_categories.append(f"{parent.text(0)}: {child.text(0)}")

        if not name:
            QMessageBox.warning(self, "Error", "Name is required.")
            return

        version = self.version_input.text().strip()
        folder_name = f"{name} {version}" if version else name

        # <Arsenal_Root>/<OS>/<App_Name> v<Version>/
        base_dir = Path(root) / os_sys / folder_name

        if base_dir.exists():
            QMessageBox.warning(
                self,
                "Error",
                f"The entry '{folder_name}' already exists in '{os_sys}'.",
            )
            return

        os.makedirs(base_dir / "files", exist_ok=True)

        is_game = self.radio_game.isChecked()
        type_str = "Game" if is_game else "Application"

        entry_data = {
            "name": name,
            "version": version,
            "author": self.author_input.text().strip(),
            "os": os_sys,
            "type": type_str,
            "categories": selected_categories,
            "description": self.desc_input.toPlainText(),
            "notes": self.notes_input.toPlainText(),
            "hashes": self.installer_hashes,
        }

        with open(base_dir / "entry.json", "w", encoding="utf-8") as f:
            json.dump(entry_data, f, indent=4)

        if self.cover_path:
            shutil.copy2(self.cover_path, base_dir / "cover.jpg")

        if self.icon_path:
            shutil.copy2(self.icon_path, base_dir / "icon.jpg")

        # Handle screenshots
        if self.screenshot_paths:
            gallery_dir = base_dir / "Gallery"
            os.makedirs(gallery_dir, exist_ok=True)
            for idx, screenshot_path in enumerate(self.screenshot_paths, start=1):
                extension = screenshot_path.suffix
                dest = gallery_dir / f"Screenshot_{idx:03d}{extension}"
                logger.info(f"Copying screenshot {screenshot_path} to {dest}")
                shutil.copy2(screenshot_path, dest)

        # Handle installation files
        file_operation = self.config_manager.get_file_operation().lower()
        if self.installer_paths:
            for file_path in self.installer_paths:
                if file_path.exists():
                    dest = base_dir / "files" / file_path.name
                    if file_operation == "move":
                        logger.info(f"Moving {file_path} to {dest}")
                        shutil.move(file_path, dest)
                    else:
                        logger.info(f"Copying {file_path} to {dest}")
                        shutil.copy2(file_path, dest)

        logger.success(f"Entry {name} successfully added.")
        QMessageBox.information(self, "Success", f"Entry '{name}' added successfully!")
        self._reset_form()

    def _reset_form(self):
        """
        Reset the form fields and UI elements to their
        default state after saving an entry.
        """

        self.name_input.clear()
        self.version_input.clear()
        self.author_input.clear()
        self.desc_input.clear()
        self.desc_label.setText("Empty")
        self.notes_input.clear()
        self.notes_label.setText("Empty")
        self.cover_path = None
        self.icon_path = None
        self.screenshot_paths = []
        self.installer_paths = []
        self.installer_hashes = {}
        self._current_hash_index = 0
        self.cover_lbl.clear()
        self.cover_lbl.setText("Cover (Portrait)")
        self.icon_lbl.clear()
        self.icon_lbl.setText("Icon (1:1)")
        self.screenshot_label.setText("0 screenshots selected.")
        self.file_label.setText("No files selected.")
        self.progress_bar.hide()
        self.radio_app.setChecked(True)
        # Clear checkboxes in the tree
        root_count = self.category_list.topLevelItemCount()
        for i in range(root_count):
            parent = self.category_list.topLevelItem(i)
            parent.setCheckState(0, Qt.Unchecked)
            for j in range(parent.childCount()):
                parent.child(j).setCheckState(0, Qt.Unchecked)
        self.category_label.setText("0 selected")


class BrowseWidget(QWidget):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.entries = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)

        # Left pane: Controls + List
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)

        # Controls
        controls_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self._filter_list)

        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.currentTextChanged.connect(self._filter_list)

        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Detail", "Grid"])
        self.view_mode_combo.currentTextChanged.connect(self._change_view_mode)

        controls_layout.addWidget(self.search_input)
        controls_layout.addWidget(self.category_filter)
        controls_layout.addWidget(self.view_mode_combo)

        left_layout.addLayout(controls_layout)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.currentItemChanged.connect(self._on_item_selected)
        left_layout.addWidget(self.list_widget)

        # Right pane: Details
        self.right_pane = QScrollArea()
        self.right_pane.setWidgetResizable(True)
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)

        self.detail_cover = QLabel()
        self.detail_cover.setAlignment(Qt.AlignCenter)
        self.detail_title = QLabel("<h2>Select an entry</h2>")
        self.detail_meta = QLabel()
        self.detail_meta.setWordWrap(True)
        self.detail_desc = QLabel()
        self.detail_desc.setWordWrap(True)
        self.detail_notes = QLabel()
        self.detail_notes.setWordWrap(True)

        self.right_layout.addWidget(self.detail_cover)
        self.right_layout.addWidget(self.detail_title)
        self.right_layout.addWidget(self.detail_meta)
        self.right_layout.addWidget(self.detail_desc)
        self.right_layout.addWidget(self.detail_notes)
        self.right_layout.addStretch()

        self.right_pane.setWidget(self.right_widget)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_pane)
        splitter.addWidget(self.right_pane)
        splitter.setSizes([400, 400])

        main_layout.addWidget(splitter)

    def refresh_data(self):
        """Scan the filesystem for entry.json and populate."""
        root = self.config_manager.get_arsenal_root()
        self.entries = []
        categories_set = set()

        if root and Path(root).exists():
            for os_dir in Path(root).iterdir():
                if not os_dir.is_dir():
                    continue
                for entry_dir in os_dir.iterdir():
                    if not entry_dir.is_dir():
                        continue
                    json_file = entry_dir / "entry.json"
                    if json_file.exists():
                        try:
                            with open(json_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            data["_path"] = str(entry_dir)
                            self.entries.append(data)
                            for cat in data.get("categories", []):
                                categories_set.add(cat)
                        except Exception as e:
                            logger.error(f"Error reading {json_file}: {e}")

        # Update category filter
        current_cat = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories")
        self.category_filter.addItems(sorted(list(categories_set)))
        if current_cat in categories_set:
            self.category_filter.setCurrentText(current_cat)
        self.category_filter.blockSignals(False)

        self._populate_list()

    def _populate_list(self):
        self.list_widget.clear()
        search_text = self.search_input.text().lower()
        cat_text = self.category_filter.currentText()

        for data in self.entries:
            name = data.get("name", "Unknown")
            type_str = data.get("type", "Unknown")
            cats = data.get("categories", [])

            # Filter
            if search_text and search_text not in name.lower():
                continue
            if cat_text != "All Categories" and cat_text not in cats:
                continue

            item = QListWidgetItem()

            # Setup text depending on view mode
            if self.view_mode_combo.currentText() == "Detail":
                item.setText(f"{name} v{data.get('version', '')} ({type_str})")
            else:
                item.setText(name)

            # Display Icon or Cover
            icon_path = Path(data["_path"]) / "icon.jpg"
            cover_path = Path(data["_path"]) / "cover.jpg"

            if self.view_mode_combo.currentText() == "Grid" and cover_path.exists():
                item.setIcon(QIcon(str(cover_path)))
            elif icon_path.exists():
                item.setIcon(QIcon(str(icon_path)))
            else:
                # Placeholder icon logic or leave blank
                pass

            item.setData(Qt.UserRole, data)
            self.list_widget.addItem(item)

        self._change_view_mode(self.view_mode_combo.currentText())

    def _filter_list(self, _):
        self._populate_list()

    def _change_view_mode(self, mode: str):
        if mode == "Grid":
            self.list_widget.setViewMode(QListWidget.IconMode)
            self.list_widget.setIconSize(QSize(120, 180))
            self.list_widget.setResizeMode(QListWidget.Adjust)
            self.list_widget.setWordWrap(True)
        else:
            self.list_widget.setViewMode(QListWidget.ListMode)
            self.list_widget.setIconSize(QSize(48, 48))
            self.list_widget.setResizeMode(QListWidget.Fixed)

        # Re-apply texts if mode changed without repopulating entirely
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.UserRole)
            if mode == "Grid":
                item.setText(data.get("name", "Unknown"))
                cover_path = Path(data["_path"]) / "cover.jpg"
                if cover_path.exists():
                    item.setIcon(QIcon(str(cover_path)))
            else:
                item.setText(
                    f"{data.get('name', 'Unknown')} v{data.get('version', '')} ({data.get('type', 'Unknown')})"
                )
                icon_path = Path(data["_path"]) / "icon.jpg"
                if icon_path.exists():
                    item.setIcon(QIcon(str(icon_path)))
                else:
                    item.setIcon(QIcon())

    def _on_item_selected(self, current: QListWidgetItem, previous):
        if not current:
            self.detail_title.setText("<h2>Select an entry</h2>")
            self.detail_cover.clear()
            self.detail_meta.clear()
            self.detail_desc.clear()
            self.detail_notes.clear()
            return

        data = current.data(Qt.UserRole)
        self.detail_title.setText(f"<h2>{data.get('name', 'Unknown')}</h2>")

        cover_path = Path(data["_path"]) / "cover.jpg"
        if cover_path.exists():
            self.detail_cover.setPixmap(
                QPixmap(str(cover_path)).scaled(240, 360, Qt.KeepAspectRatio)
            )
        else:
            self.detail_cover.clear()

        meta_text = (
            f"<b>Version:</b> {data.get('version', 'N/A')}<br>"
            f"<b>Author:</b> {data.get('author', 'N/A')}<br>"
            f"<b>OS:</b> {data.get('os', 'N/A')}<br>"
            f"<b>Type:</b> {data.get('type', 'N/A')}<br>"
            f"<b>Categories:</b> {', '.join(data.get('categories', []))}"
        )
        self.detail_meta.setText(meta_text)

        desc = data.get("description", "")
        self.detail_desc.setText(f"<h3>Description</h3><p>{desc}</p>" if desc else "")

        notes = data.get("notes", "")
        self.detail_notes.setText(
            f"<h3>Instructions/Notes</h3><p>{notes}</p>" if notes else ""
        )


class MainWindow(QMainWindow):
    def __init__(
        self, config_manager: ConfigManager, metadata_manager: MetadataManager
    ):
        super().__init__()
        self.config_manager = config_manager
        self.metadata_manager = metadata_manager
        self.setWindowTitle(f"{info.NAME} v{info.VERSION} - {info.DESCRIPTION}")
        self.resize(1000, 700)
        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Sidebar
        sidebar = QVBoxLayout()
        self.btn_browse = QPushButton("Browse Archive")
        self.btn_add = QPushButton("Add New Entry")
        self.btn_settings = QPushButton("Settings")

        sidebar.addWidget(self.btn_browse)
        sidebar.addWidget(self.btn_add)
        sidebar.addWidget(self.btn_settings)
        sidebar.addStretch()

        # Stacked Widget
        self.stacked_widget = QStackedWidget()

        self.browse_widget = BrowseWidget(self.config_manager)

        self.add_widget = AddEntryWidget(self.config_manager, self.metadata_manager)

        self.settings_widget = QWidget()
        settings_layout = QVBoxLayout(self.settings_widget)
        self.root_lbl = QLabel(
            f"Arsenal Root: {self.config_manager.get_arsenal_root()}"
        )
        change_root_btn = QPushButton("Change Root...")
        change_root_btn.clicked.connect(self._change_root)
        settings_layout.addWidget(self.root_lbl)
        settings_layout.addWidget(change_root_btn)

        # File Operation Setting
        file_op_layout = QHBoxLayout()
        file_op_layout.addWidget(QLabel("Installation File Operation:"))
        self.file_op_combo = QComboBox()
        self.file_op_combo.addItems(["Move", "Copy"])
        self.file_op_combo.setCurrentText(
            self.config_manager.get_file_operation().capitalize()
        )
        self.file_op_combo.currentTextChanged.connect(
            self.config_manager.set_file_operation
        )
        file_op_layout.addWidget(self.file_op_combo)
        file_op_layout.addStretch()
        settings_layout.addLayout(file_op_layout)

        settings_layout.addWidget(
            QLabel("Metadata Management (OS, Categories, Genres)")
        )
        # Category Manager Widget added to Settings
        self.category_manager_widget = CategoryManagerWidget(self.metadata_manager)
        settings_layout.addWidget(self.category_manager_widget, 1)

        self.stacked_widget.addWidget(self.browse_widget)
        self.stacked_widget.addWidget(self.add_widget)
        self.stacked_widget.addWidget(self.settings_widget)

        # Connections
        self.btn_browse.clicked.connect(
            lambda: [
                self.browse_widget.refresh_data(),
                self.stacked_widget.setCurrentIndex(0),
            ]
        )
        self.btn_add.clicked.connect(
            lambda: [
                self.add_widget.refresh_data(),
                self.stacked_widget.setCurrentIndex(1),
            ]
        )
        self.btn_settings.clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(2)
        )

        main_layout.addLayout(sidebar, 1)
        main_layout.addWidget(self.stacked_widget, 4)

    def _change_root(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Arsenal Root Directory"
        )
        if directory:
            old_root = self.config_manager.get_arsenal_root()

            if (
                old_root
                and Path(old_root).resolve() != Path(directory).resolve()
                and Path(old_root).exists()
            ):
                reply = QMessageBox.question(
                    self,
                    "Move Files",
                    "Do you want to move your existing archive and metadata to the new location?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    try:
                        for item in os.listdir(old_root):
                            src = os.path.join(old_root, item)
                            dst = os.path.join(directory, item)
                            logger.info(f"Moving {src} to {dst}")
                            shutil.move(src, dst)

                    except Exception as e:
                        logger.error(f"Failed to move files to new root: {e}")
                        QMessageBox.critical(
                            self, "Error", f"Failed to move some files: {e}"
                        )
                        return

            self.config_manager.set_arsenal_root(directory)
            QMessageBox.information(
                self,
                "Restart Required",
                "The Arsenal root folder has been changed. The application must restart to apply changes.\n\nThe application will now close.",
            )
            sys.exit(0)
