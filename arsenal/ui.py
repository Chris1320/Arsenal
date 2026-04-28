import os
import sys
import shutil
import json
from pathlib import Path

from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
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
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import (
    Qt,
    QThread,
    QSize,
    Signal,
)  # pylint: disable=no-name-in-module
from PySide6.QtGui import QPixmap, QIcon, QImage  # pylint: disable=no-name-in-module
from loguru import logger

from arsenal import info
from arsenal.config import ConfigManager
from arsenal.metadata import MetadataManager
from arsenal.hashing import HashingWorker
from arsenal.category_manager import CategoryManagerWidget


class VerifyDialog(QDialog):
    def __init__(self, entry_data, parent=None):
        super().__init__(parent)
        self.entry_data = entry_data
        self.setWindowTitle(f"Verify Files - {entry_data.get('name')}")
        self.resize(700, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["File", "Expected Hash", "Actual Hash"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Initializing...")
        layout.addWidget(self.status_lbl)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        layout.addWidget(self.close_btn)

        self.files_to_hash = list(self.entry_data.get("hashes", {}).keys())
        self.current_index = 0
        self.hashing_thread = None
        self.hashing_worker = None

        self._populate_table()
        self._hash_next_file()

    def _populate_table(self):
        hashes = self.entry_data.get("hashes", {})
        self.table.setRowCount(len(hashes))
        for row, (filename, expected) in enumerate(hashes.items()):
            self.table.setItem(row, 0, QTableWidgetItem(filename))
            self.table.setItem(row, 1, QTableWidgetItem(expected))

            actual_item = QTableWidgetItem("Pending...")
            self.table.setItem(row, 2, actual_item)

    def _hash_next_file(self):
        if self.current_index < len(self.files_to_hash):
            file_key = self.files_to_hash[self.current_index]
            filename = Path(file_key).name
            base_dir = Path(self.entry_data.get("_path"))
            fpath = base_dir / "files" / filename

            self.status_lbl.setText(f"Verifying {filename}...")
            self.progress_bar.setValue(0)

            if not fpath.exists():
                self._hash_finished(str(fpath), "FILE NOT FOUND")
                return

            algo = self.entry_data.get("hashing_algorithm", "BLAKE3")

            self.hashing_thread = QThread()
            self.hashing_worker = HashingWorker(fpath, algo)
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
        else:
            self.status_lbl.setText("Verification complete.")
            self.progress_bar.setValue(100)
            self.close_btn.setEnabled(True)

    def _on_thread_finished(self):
        self.current_index += 1
        self._hash_next_file()

    def _hash_finished(self, path: str, result_hash: str):
        file_key = self.files_to_hash[self.current_index]
        expected_hash = self.entry_data.get("hashes", {}).get(file_key)

        actual_item = QTableWidgetItem(result_hash)
        if result_hash == expected_hash:
            actual_item.setForeground(Qt.green)
        else:
            actual_item.setForeground(Qt.red)

        self.table.setItem(self.current_index, 2, actual_item)

    def _hash_error(self, err: str):
        actual_item = QTableWidgetItem(f"ERROR: {err}")
        actual_item.setForeground(Qt.red)
        self.table.setItem(self.current_index, 2, actual_item)

    def reject(self):
        try:
            if self.hashing_thread and self.hashing_thread.isRunning():
                if self.hashing_worker:
                    self.hashing_worker.cancel()
                self.hashing_thread.quit()
                self.hashing_thread.wait()
        except RuntimeError:
            pass
        super().reject()


class EditEntryDialog(QDialog):
    def __init__(self, entry_data, config_manager, metadata_manager, parent=None):
        super().__init__(parent)
        self.entry_data = entry_data
        self.config_manager = config_manager
        self.metadata_manager = metadata_manager
        self.setWindowTitle(f"Edit Entry - {entry_data.get('name')}")
        self.resize(500, 400)
        self._init_ui()
        self._populate_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.version_input = QLineEdit()
        self.author_input = QLineEdit()
        self.os_input = QComboBox()
        self.os_input.addItems(self.metadata_manager.get_os_list())

        self.primary_installer_combo = QComboBox()
        base_dir = Path(self.entry_data.get("_path", ""))
        files_dir = base_dir / "files"
        if files_dir.exists():
            for root_dir, _, files in os.walk(files_dir):
                for f in files:
                    abs_path = Path(root_dir) / f
                    rel_path = abs_path.relative_to(files_dir)
                    self.primary_installer_combo.addItem(
                        str(rel_path).replace("\\", "/")
                    )

        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Version:", self.version_input)
        form_layout.addRow("Author:", self.author_input)
        form_layout.addRow("OS:", self.os_input)
        form_layout.addRow("Primary Installer:", self.primary_installer_combo)

        # Categories Setup
        self.category_dialog = QDialog(self)
        self.category_dialog.setWindowTitle("Select Categories/Genres")
        self.category_dialog.resize(400, 500)
        cat_dlg_layout = QVBoxLayout(self.category_dialog)
        self.category_list = QTreeWidget()
        self.category_list.setHeaderHidden(True)
        self.category_list.itemChanged.connect(self._on_category_item_changed)
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

        # Description Setup
        self.desc_dialog = QDialog(self)
        self.desc_dialog.setWindowTitle("Edit Description")
        self.desc_dialog.resize(700, 500)
        desc_dlg_layout = QVBoxLayout(self.desc_dialog)
        self.desc_input = QTextEdit()
        desc_dlg_layout.addWidget(self.desc_input)
        desc_close_btn = QPushButton("Done")
        desc_close_btn.clicked.connect(self.desc_dialog.accept)
        desc_dlg_layout.addWidget(desc_close_btn)

        self.desc_btn = QPushButton("Edit...")
        self.desc_dialog.finished.connect(self._update_desc_label)
        self.desc_btn.clicked.connect(self.desc_dialog.exec)
        self.desc_label = QLabel("Empty")
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(self.desc_btn)
        desc_layout.addWidget(self.desc_label)
        desc_layout.addStretch()
        form_layout.addRow("Description:", desc_layout)

        # Notes Setup
        self.notes_dialog = QDialog(self)
        self.notes_dialog.setWindowTitle("Edit Notes")
        self.notes_dialog.resize(700, 500)
        notes_dlg_layout = QVBoxLayout(self.notes_dialog)
        self.notes_input = QTextEdit()
        notes_dlg_layout.addWidget(self.notes_input)
        notes_close_btn = QPushButton("Done")
        notes_close_btn.clicked.connect(self.notes_dialog.accept)
        notes_dlg_layout.addWidget(notes_close_btn)

        self.notes_btn = QPushButton("Edit...")
        self.notes_dialog.finished.connect(self._update_notes_label)
        self.notes_btn.clicked.connect(self.notes_dialog.exec)
        self.notes_label = QLabel("Empty")
        notes_layout = QHBoxLayout()
        notes_layout.addWidget(self.notes_btn)
        notes_layout.addWidget(self.notes_label)
        notes_layout.addStretch()
        form_layout.addRow("Notes:", notes_layout)

        layout.addLayout(form_layout)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
        layout.addWidget(self.save_btn)

    def _populate_data(self):
        self.name_input.setText(self.entry_data.get("name", ""))
        self.version_input.setText(self.entry_data.get("version", ""))
        self.author_input.setText(self.entry_data.get("author", ""))
        self.os_input.setCurrentText(self.entry_data.get("os", ""))
        self.primary_installer_combo.setCurrentText(
            self.entry_data.get("primary_installer", "")
        )
        self.desc_input.setPlainText(self.entry_data.get("description", ""))
        self.notes_input.setPlainText(self.entry_data.get("notes", ""))
        self._update_desc_label()
        self._update_notes_label()

        self.category_list.clear()
        is_game = self.entry_data.get("type") == "Game"
        data_dict = (
            self.metadata_manager.get_genres()
            if is_game
            else self.metadata_manager.get_categories()
        )
        existing_cats = set(self.entry_data.get("categories", []))

        for main_cat, sub_cats in data_dict.items():
            parent = QTreeWidgetItem(self.category_list)
            parent.setText(0, main_cat)
            parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable)
            parent.setCheckState(
                0, Qt.Checked if main_cat in existing_cats else Qt.Unchecked
            )

            for sub_cat in sub_cats:
                child = QTreeWidgetItem(parent)
                child.setText(0, sub_cat)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child_cat_str = f"{main_cat}: {sub_cat}"
                child.setCheckState(
                    0, Qt.Checked if child_cat_str in existing_cats else Qt.Unchecked
                )

        self.category_list.expandAll()
        self._update_category_label()

    def _on_category_item_changed(self, item: QTreeWidgetItem, column: int):
        if item.checkState(0) == Qt.Checked:
            parent = item.parent()
            if parent:
                self.category_list.blockSignals(True)
                parent.setCheckState(0, Qt.Checked)
                self.category_list.blockSignals(False)

    def _update_category_label(self):
        selected = 0
        root_count = self.category_list.topLevelItemCount()
        for i in range(root_count):
            parent = self.category_list.topLevelItem(i)
            if parent.checkState(0) == Qt.Checked:
                selected += 1
            for j in range(parent.childCount()):
                if parent.child(j).checkState(0) == Qt.Checked:
                    selected += 1
        self.category_label.setText(f"{selected} selected")

    def _update_desc_label(self):
        self.desc_label.setText(
            "Provided" if self.desc_input.toPlainText().strip() else "Empty"
        )

    def _update_notes_label(self):
        self.notes_label.setText(
            "Provided" if self.notes_input.toPlainText().strip() else "Empty"
        )

    def _save_changes(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name is required.")
            return

        version = self.version_input.text().strip()
        os_sys = self.os_input.currentText()

        selected_categories = []
        root_count = self.category_list.topLevelItemCount()
        for i in range(root_count):
            parent = self.category_list.topLevelItem(i)
            if parent.checkState(0) == Qt.Checked:
                selected_categories.append(parent.text(0))
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.Checked:
                    selected_categories.append(f"{parent.text(0)}: {child.text(0)}")

        # Calculate new path if name, version, or OS changed
        root = self.config_manager.get_arsenal_root()
        folder_name = f"{name} {version}" if version else name
        type_folder = (
            "Games" if self.entry_data.get("type") == "Game" else "Applications"
        )
        new_dir = Path(root) / os_sys / type_folder / folder_name
        old_dir = Path(self.entry_data.get("_path"))

        if new_dir.resolve() != old_dir.resolve():
            if new_dir.exists():
                QMessageBox.warning(
                    self,
                    "Error",
                    f"A folder named '{folder_name}' already exists in '{os_sys}/{type_folder}'.",
                )
                return
            try:
                new_dir.parent.mkdir(parents=True, exist_ok=True)
                old_dir.rename(new_dir)
                self.entry_data["_path"] = str(new_dir)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename directory:\n{e}")
                return

        # Update JSON payload
        self.entry_data["name"] = name
        self.entry_data["version"] = version
        self.entry_data["author"] = self.author_input.text().strip()
        self.entry_data["os"] = os_sys
        self.entry_data["categories"] = selected_categories
        self.entry_data["description"] = self.desc_input.toPlainText()
        self.entry_data["notes"] = self.notes_input.toPlainText()
        self.entry_data["primary_installer"] = (
            self.primary_installer_combo.currentText()
        )

        # We don't want to save '_path' inside the json file itself, so we copy dict
        save_data = dict(self.entry_data)
        save_data.pop("_path", None)

        try:
            with open(new_dir / "entry.json", "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save changes:\n{e}")
            return

        QMessageBox.information(self, "Success", "Entry updated successfully.")
        self.accept()


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

        self.radio_app.toggled.connect(self._on_entry_type_changed)

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
        self.category_list.itemChanged.connect(self._on_category_item_changed)
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
        self.file_btns_layout = QHBoxLayout()
        self.add_file_btn = QPushButton("Add File(s)...")
        self.add_file_btn.clicked.connect(self._add_files)
        self.add_folder_btn = QPushButton("Add Folder...")
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.clear_files_btn = QPushButton("Clear Files")
        self.clear_files_btn.clicked.connect(self._clear_files)
        self.file_btns_layout.addWidget(self.add_file_btn)
        self.file_btns_layout.addWidget(self.add_folder_btn)
        self.file_btns_layout.addWidget(self.clear_files_btn)

        self.file_label = QLabel("No files selected.")

        self.primary_installer_combo = QComboBox()

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
        layout.addLayout(self.file_btns_layout)
        layout.addWidget(self.file_label)
        layout.addWidget(QLabel("Primary Installer:"))
        layout.addWidget(self.primary_installer_combo)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

        self.cover_path = None
        self.icon_path = None
        self.screenshot_paths = []
        self.installer_paths = []
        self.flattened_files = []
        self.installer_hashes = {}
        self._current_hash_index = 0

        self._on_entry_type_changed()

    def _on_entry_type_changed(self):
        self._update_category_list()
        is_game = self.radio_game.isChecked()
        self.cover_lbl.setVisible(is_game)
        self.cover_btn.setVisible(is_game)
        if not is_game:
            self.cover_path = None
            self.cover_lbl.clear()
            self.cover_lbl.setText("Cover (Portrait)")

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

    def _on_category_item_changed(self, item: QTreeWidgetItem, column: int):
        if item.checkState(0) == Qt.Checked:
            parent = item.parent()
            if parent:
                # Temporarily block signals to avoid infinite loops if we were checking multiple things,
                # though setting check state will just emit the signal for the parent.
                self.category_list.blockSignals(True)
                parent.setCheckState(0, Qt.Checked)
                self.category_list.blockSignals(False)

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

    def _add_files(self):
        fnames, _ = QFileDialog.getOpenFileNames(self, "Select Installer File(s)")
        if fnames:
            self.installer_paths.extend([Path(f) for f in fnames])
            self._prepare_hashing()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Installer Folder")
        if folder:
            self.installer_paths.append(Path(folder))
            self._prepare_hashing()

    def _clear_files(self):
        try:
            if self.hashing_thread and self.hashing_thread.isRunning():
                self.hashing_worker.cancel()
        except RuntimeError:
            pass  # Object already deleted

        self.installer_paths = []
        self.flattened_files = []
        self.installer_hashes = {}
        self.primary_installer_combo.clear()
        self.file_label.setText("No files selected.")
        self.progress_bar.hide()
        self.submit_btn.setEnabled(True)

    def _prepare_hashing(self):
        try:
            if self.hashing_thread and self.hashing_thread.isRunning():
                self.hashing_worker.cancel()
        except RuntimeError:
            pass  # Object already deleted

        self.flattened_files = []
        for p in self.installer_paths:
            if p.is_file():
                self.flattened_files.append((p, p.name))
            elif p.is_dir():
                for root, _, files in os.walk(p):
                    for f in files:
                        abs_path = Path(root) / f
                        rel_path = abs_path.relative_to(p.parent)
                        self.flattened_files.append(
                            (abs_path, str(rel_path).replace("\\", "/"))
                        )

        self.file_label.setText(
            f"{len(self.installer_paths)} items ({len(self.flattened_files)} files) selected (Hashing...)"
        )

        self.primary_installer_combo.clear()
        self.primary_installer_combo.addItems([rel for _, rel in self.flattened_files])

        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.submit_btn.setEnabled(False)
        self.installer_hashes = {}
        self._current_hash_index = 0

        self._hash_next_file()

    def _hash_next_file(self):
        if self._current_hash_index < len(self.flattened_files):
            abs_path, rel_path = self.flattened_files[self._current_hash_index]
            self.file_label.setText(
                f"Hashing File {self._current_hash_index + 1}/{len(self.flattened_files)}: {rel_path}"
            )
            self.progress_bar.setValue(0)
            self._start_hashing(abs_path)
        else:
            self.file_label.setText(
                f"{len(self.installer_paths)} items ({len(self.flattened_files)} files) ready to add."
            )
            self.progress_bar.hide()
            self.submit_btn.setEnabled(True)

    def _start_hashing(self, path: Path):
        """Start the hashing process in a separate thread to avoid blocking the UI."""
        self.hashing_thread = QThread()
        algo = self.config_manager.get_hashing_algorithm()
        self.hashing_worker = HashingWorker(path, algo)
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
        self.hashing_thread.destroyed.connect(self._on_thread_destroyed)

        self.hashing_thread.start()

    def _on_thread_destroyed(self):
        self.hashing_thread = None

    def _on_thread_finished(self):
        self._current_hash_index += 1
        self._hash_next_file()

    def _hash_finished(self, path: str, result_hash: str):
        """Handle completion of hashing, update UI with hash result."""
        _, rel_path = self.flattened_files[self._current_hash_index]
        self.installer_hashes[rel_path] = result_hash
        logger.info(f"Hashing completed for {rel_path}. Hash: {result_hash}")

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

        is_game = self.radio_game.isChecked()
        type_str = "Game" if is_game else "Application"
        type_folder = "Games" if is_game else "Applications"

        # <Arsenal_Root>/<OS>/<Type_Folder>/<App_Name> v<Version>/
        base_dir = Path(root) / os_sys / type_folder / folder_name

        if base_dir.exists():
            QMessageBox.warning(
                self,
                "Error",
                f"The entry '{folder_name}' already exists in '{os_sys}/{type_folder}'.",
            )
            return

        os.makedirs(base_dir / "files", exist_ok=True)

        file_sizes = {}
        for abs_path, rel_path in self.flattened_files:
            if abs_path.exists():
                file_sizes[rel_path] = abs_path.stat().st_size

        entry_data = {
            "entry_version": info.VERSION,
            "name": name,
            "version": version,
            "author": self.author_input.text().strip(),
            "os": os_sys,
            "type": type_str,
            "categories": selected_categories,
            "description": self.desc_input.toPlainText(),
            "notes": self.notes_input.toPlainText(),
            "hashing_algorithm": self.config_manager.get_hashing_algorithm(),
            "hashes": self.installer_hashes,
            "file_sizes": file_sizes,
            "primary_installer": self.primary_installer_combo.currentText(),
        }

        with open(base_dir / "entry.json", "w", encoding="utf-8") as f:
            json.dump(entry_data, f, indent=4)

        if self.cover_path:
            shutil.copy2(self.cover_path, base_dir / "cover.jpg")

        if self.icon_path:
            shutil.copy2(self.icon_path, base_dir / "icon.jpg")

        # Handle screenshots
        if self.screenshot_paths:
            gallery_dir = base_dir / "gallery"
            os.makedirs(gallery_dir, exist_ok=True)
            for idx, screenshot_path in enumerate(self.screenshot_paths, start=1):
                extension = screenshot_path.suffix
                dest = gallery_dir / f"Screenshot_{idx:03d}{extension}"
                logger.info(f"Copying screenshot {screenshot_path} to {dest}")
                shutil.copy2(screenshot_path, dest)

        # Handle installation files
        file_operation = self.config_manager.get_file_operation().lower()
        if self.installer_paths:
            for source_path in self.installer_paths:
                if source_path.exists():
                    dest = base_dir / "files" / source_path.name
                    if source_path.is_file():
                        if file_operation == "move":
                            logger.info(f"Moving {source_path} to {dest}")
                            shutil.move(source_path, dest)
                        else:
                            logger.info(f"Copying {source_path} to {dest}")
                            shutil.copy2(source_path, dest)
                    elif source_path.is_dir():
                        if file_operation == "move":
                            logger.info(f"Moving directory {source_path} to {dest}")
                            shutil.move(source_path, dest)
                        else:
                            logger.info(f"Copying directory {source_path} to {dest}")
                            shutil.copytree(source_path, dest, dirs_exist_ok=True)

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
        self.flattened_files = []
        self.installer_hashes = {}
        self.primary_installer_combo.clear()
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


class ImageLoaderWorker(QThread):
    # Emits QListWidgetItem and QImage (or None if failed)
    image_loaded = Signal(object, object)

    def __init__(self, loads: list, parent=None):
        """
        loads: list of tuples (QListWidgetItem, str path)
        """
        super().__init__(parent)
        self.loads = loads
        self._is_cancelled = False

    def run(self):
        for item, paths in self.loads:
            if self._is_cancelled:
                break

            loaded = False
            for path in paths:
                if Path(path).exists():
                    image = QImage(str(path))
                    if not image.isNull():
                        self.image_loaded.emit(item, image)
                        loaded = True
                        break

            if not loaded:
                self.image_loaded.emit(item, None)

    def cancel(self):
        self._is_cancelled = True


class BrowseWidget(QWidget):
    def __init__(
        self, config_manager: ConfigManager, metadata_manager: MetadataManager
    ):
        super().__init__()
        self.config_manager = config_manager
        self.metadata_manager = metadata_manager
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

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)

        controls_layout.addWidget(self.search_input)
        controls_layout.addWidget(self.category_filter)
        controls_layout.addWidget(self.view_mode_combo)
        controls_layout.addWidget(self.refresh_btn)

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

        # Action Buttons
        self.actions_layout = QVBoxLayout()
        self.btn_install = QPushButton("Install")
        self.btn_edit = QPushButton("Edit Entry")
        self.btn_open_dir = QPushButton("Open Installation Directory")
        self.btn_verify = QPushButton("Verify Files")
        self.btn_remove = QPushButton("Remove Entry")

        self.actions_layout.addWidget(self.btn_install)
        self.actions_layout.addWidget(self.btn_edit)
        self.actions_layout.addWidget(self.btn_open_dir)
        self.actions_layout.addWidget(self.btn_verify)
        self.actions_layout.addWidget(self.btn_remove)

        for btn in [
            self.btn_install,
            self.btn_edit,
            self.btn_open_dir,
            self.btn_verify,
            self.btn_remove,
        ]:
            btn.setEnabled(False)

        self.btn_install.clicked.connect(self._on_install)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_open_dir.clicked.connect(self._on_open_dir)
        self.btn_verify.clicked.connect(self._on_verify)
        self.btn_remove.clicked.connect(self._on_remove)

        self.right_layout.addWidget(self.detail_cover)
        self.right_layout.addWidget(self.detail_title)
        self.right_layout.addLayout(self.actions_layout)
        self.right_layout.addWidget(self.detail_meta)
        self.right_layout.addWidget(self.detail_desc)
        self.right_layout.addWidget(self.detail_notes)
        self.right_layout.addStretch()

        self.right_pane.setWidget(self.right_widget)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_pane)
        splitter.addWidget(self.right_pane)
        splitter.setSizes([600, 200])

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
                for type_dir in os_dir.iterdir():
                    if not type_dir.is_dir() or type_dir.name not in (
                        "Applications",
                        "Games",
                    ):
                        continue
                    for entry_dir in type_dir.iterdir():
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
        if hasattr(self, "_image_worker") and self._image_worker is not None:
            self._image_worker.cancel()
            self._image_worker.wait()
            self._image_worker = None

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
            item.setData(Qt.UserRole, data)
            self.list_widget.addItem(item)

        self._change_view_mode(self.view_mode_combo.currentText())

    def _filter_list(self, _):
        self._populate_list()

    def _change_view_mode(self, mode: str):
        if mode == "Grid":
            self.list_widget.setViewMode(QListWidget.IconMode)
            self.list_widget.setMovement(QListWidget.Static)
            self.list_widget.setIconSize(QSize(120, 180))
            self.list_widget.setGridSize(QSize(140, 220))
            self.list_widget.setResizeMode(QListWidget.Adjust)
            self.list_widget.setWordWrap(True)
            self.list_widget.setUniformItemSizes(True)
        else:
            self.list_widget.setViewMode(QListWidget.ListMode)
            self.list_widget.setMovement(QListWidget.Static)
            self.list_widget.setIconSize(QSize(48, 48))
            self.list_widget.setGridSize(QSize())  # Reset grid size
            self.list_widget.setResizeMode(QListWidget.Fixed)
            self.list_widget.setWordWrap(False)
            self.list_widget.setUniformItemSizes(False)

        if hasattr(self, "_image_worker") and self._image_worker is not None:
            self._image_worker.cancel()
            self._image_worker.wait()
            self._image_worker = None

        image_loads = []

        # Placeholder to ensure layout calculates correct bounds initially
        placeholder = QPixmap(120, 180)
        placeholder.fill(Qt.transparent)
        placeholder_icon = QIcon(placeholder)

        list_placeholder = QPixmap(48, 48)
        list_placeholder.fill(Qt.transparent)
        list_placeholder_icon = QIcon(list_placeholder)

        # Re-apply texts if mode changed without repopulating entirely
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.UserRole)

            if mode == "Grid":
                item.setIcon(placeholder_icon)
                item.setText(data.get("name", "Unknown"))
                cover_path = Path(data["_path"]) / "cover.jpg"
                icon_path = Path(data["_path"]) / "icon.jpg"
                image_loads.append((item, [str(cover_path), str(icon_path)]))
            else:
                item.setIcon(list_placeholder_icon)
                item.setText(
                    f"{data.get('name', 'Unknown')} {data.get('version', '')} ({data.get('type', 'Unknown')})"
                )
                icon_path = Path(data["_path"]) / "icon.jpg"
                image_loads.append((item, [str(icon_path)]))

        self._image_worker = ImageLoaderWorker(image_loads, parent=self)
        self._image_worker.image_loaded.connect(self._on_image_loaded)
        self._image_worker.start()

    def _on_image_loaded(self, item, image):
        if image is not None:
            item.setIcon(QIcon(QPixmap.fromImage(image)))

    def _on_item_selected(self, current: QListWidgetItem, previous):
        if not current:
            self.detail_title.setText("<h2>Select an entry</h2>")
            self.detail_cover.clear()
            self.detail_meta.clear()
            self.detail_desc.clear()
            self.detail_notes.clear()
            for btn in [
                self.btn_install,
                self.btn_edit,
                self.btn_open_dir,
                self.btn_verify,
                self.btn_remove,
            ]:
                btn.setEnabled(False)
            return

        data = current.data(Qt.UserRole)
        self.current_entry_data = data
        for btn in [
            self.btn_install,
            self.btn_edit,
            self.btn_open_dir,
            self.btn_verify,
            self.btn_remove,
        ]:
            btn.setEnabled(True)

        self.detail_title.setText(f"<h2>{data.get('name', 'Unknown')}</h2>")

        cover_path = Path(data["_path"]) / "cover.jpg"
        if cover_path.exists():
            self.detail_cover.setPixmap(
                QPixmap(str(cover_path)).scaled(240, 360, Qt.KeepAspectRatio)
            )
        else:
            self.detail_cover.clear()

        def format_size(size):
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} PB"

        file_sizes = data.get("file_sizes", {})
        total_size = sum(file_sizes.values()) if file_sizes else 0

        meta_text = (
            f"<b>Version:</b> {data.get('version', 'N/A')}<br>"
            f"<b>Author:</b> {data.get('author', 'N/A')}<br>"
            f"<b>OS:</b> {data.get('os', 'N/A')}<br>"
            f"<b>Type:</b> {data.get('type', 'N/A')}<br>"
            f"<b>Categories:</b> {', '.join(data.get('categories', []))}<br>"
            f"<b>Entry Version:</b> {data.get('entry_version', 'N/A')}<br>"
            f"<b>Primary Installer:</b> {data.get('primary_installer', 'N/A')}<br>"
            f"<b>Total Size:</b> {format_size(total_size)}"
        )
        self.detail_meta.setText(meta_text)

        desc = data.get("description", "")
        if desc:
            self.detail_desc.setTextFormat(Qt.MarkdownText)
            self.detail_desc.setText(f"### Description\n{desc}")
        else:
            self.detail_desc.setText("")

        notes = data.get("notes", "")
        if notes:
            self.detail_notes.setTextFormat(Qt.MarkdownText)
            self.detail_notes.setText(f"### Instructions/Notes\n{notes}")
        else:
            self.detail_notes.setText("")

    def _on_install(self):
        data = getattr(self, "current_entry_data", None)
        if not data:
            return
        installer = data.get("primary_installer")
        if not installer:
            QMessageBox.warning(
                self, "Install", "No primary installer selected for this entry."
            )
            return
        path = Path(data["_path"]) / "files" / installer
        if path.exists():
            os.startfile(str(path))
        else:
            QMessageBox.warning(self, "Error", f"Installer not found: {path}")

    def _on_edit(self):
        data = getattr(self, "current_entry_data", None)
        if not data:
            return

        dialog = EditEntryDialog(data, self.config_manager, self.metadata_manager, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_data()

    def _on_open_dir(self):
        data = getattr(self, "current_entry_data", None)
        if not data:
            return
        path = Path(data["_path"]) / "files"
        if path.exists():
            os.startfile(str(path))

    def _on_verify(self):
        data = getattr(self, "current_entry_data", None)
        if not data:
            return
        hashes = data.get("hashes", {})
        if not hashes:
            QMessageBox.information(self, "Verify", "No hashes found for this entry.")
            return

        dialog = VerifyDialog(data, self)
        dialog.exec()

    def _on_remove(self):
        data = getattr(self, "current_entry_data", None)
        if not data:
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Remove Entry")
        msg.setText(f"Are you sure you want to remove '{data.get('name')}'?")
        cb = QCheckBox("Remove installation media and files as well?")
        msg.setCheckBox(cb)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        if msg.exec() == QMessageBox.Yes:
            try:
                base_dir = Path(data["_path"])
                if cb.isChecked():
                    shutil.rmtree(base_dir)
                else:
                    json_file = base_dir / "entry.json"
                    if json_file.exists():
                        json_file.unlink()
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove: {e}")


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

        self.browse_widget = BrowseWidget(self.config_manager, self.metadata_manager)

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

        # Hashing Algorithm Setting
        hash_algo_layout = QHBoxLayout()
        hash_algo_layout.addWidget(QLabel("Hashing Algorithm:"))
        self.hash_algo_combo = QComboBox()
        self.hash_algo_combo.addItems(["BLAKE3", "SHA256", "MD5", "SHA1"])
        self.hash_algo_combo.setCurrentText(
            self.config_manager.get_hashing_algorithm().upper()
        )
        self.hash_algo_combo.currentTextChanged.connect(
            self.config_manager.set_hashing_algorithm
        )
        hash_algo_layout.addWidget(self.hash_algo_combo)
        hash_algo_layout.addStretch()
        settings_layout.addLayout(hash_algo_layout)

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

        # Initial population
        self.browse_widget.refresh_data()

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
