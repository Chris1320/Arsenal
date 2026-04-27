from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QLineEdit,
    QLabel,
    QMessageBox,
    QInputDialog,
    QTreeWidget,
    QTreeWidgetItem,
)
from arsenal.metadata import MetadataManager


class CategoryManagerWidget(QWidget):
    def __init__(self, metadata_manager: MetadataManager):
        super().__init__()
        self.metadata_manager = metadata_manager
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # OS Manager
        self.os_list_widget = self._create_list_manager(
            "Operating Systems",
            self.metadata_manager.get_os_list,
            self.metadata_manager.set_os_list,
        )
        layout.addLayout(self.os_list_widget)

        # App Categories Manager
        self.categories_tree_widget = self._create_tree_manager(
            "App Categories",
            self.metadata_manager.get_categories,
            self.metadata_manager.set_categories,
        )
        layout.addLayout(self.categories_tree_widget)

        # Game Genres Manager
        self.genres_tree_widget = self._create_tree_manager(
            "Game Genres",
            self.metadata_manager.get_genres,
            self.metadata_manager.set_genres,
        )
        layout.addLayout(self.genres_tree_widget)

    def _create_list_manager(self, title, getter_func, setter_func):
        vbox = QVBoxLayout()
        vbox.addWidget(QLabel(title))

        list_widget = QListWidget()
        list_widget.addItems(getter_func())

        btn_add = QPushButton("Add")
        btn_remove = QPushButton("Remove")
        btn_rename = QPushButton("Rename")

        btn_add.clicked.connect(
            lambda: self._list_add_item(list_widget, getter_func, setter_func)
        )
        btn_remove.clicked.connect(
            lambda: self._list_remove_item(list_widget, getter_func, setter_func)
        )
        btn_rename.clicked.connect(
            lambda: self._list_rename_item(list_widget, getter_func, setter_func)
        )

        hbox = QHBoxLayout()
        hbox.addWidget(btn_add)
        hbox.addWidget(btn_remove)
        hbox.addWidget(btn_rename)

        vbox.addWidget(list_widget)
        vbox.addLayout(hbox)
        return vbox

    def _list_add_item(self, list_widget, getter_func, setter_func):
        text, ok = QInputDialog.getText(self, "Add Item", "Enter new name:")
        if ok and text:
            items = getter_func()
            if text not in items:
                items.append(text)
                setter_func(items)
                list_widget.clear()
                list_widget.addItems(items)

    def _list_remove_item(self, list_widget, getter_func, setter_func):
        current_item = list_widget.currentItem()
        if current_item:
            text = current_item.text()
            reply = QMessageBox.question(
                self,
                "Remove Item",
                f"Are you sure you want to remove '{text}'?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                items = getter_func()
                if text in items:
                    items.remove(text)
                    setter_func(items)
                    list_widget.clear()
                    list_widget.addItems(items)

    def _list_rename_item(self, list_widget, getter_func, setter_func):
        current_item = list_widget.currentItem()
        if current_item:
            old_text = current_item.text()
            new_text, ok = QInputDialog.getText(
                self, "Rename Item", "Enter new name:", QLineEdit.Normal, old_text
            )
            if ok and new_text and new_text != old_text:
                items = getter_func()
                if new_text not in items:
                    index = items.index(old_text)
                    items[index] = new_text
                    setter_func(items)
                    list_widget.clear()
                    list_widget.addItems(items)

    def _create_tree_manager(self, title, getter_func, setter_func):
        vbox = QVBoxLayout()
        vbox.addWidget(QLabel(title))

        tree_widget = QTreeWidget()
        tree_widget.setHeaderHidden(True)
        self._populate_tree(tree_widget, getter_func())

        btn_add_main = QPushButton("Add Main")
        btn_add_sub = QPushButton("Add Sub")
        btn_remove = QPushButton("Remove")
        btn_rename = QPushButton("Rename")

        btn_add_main.clicked.connect(
            lambda: self._tree_add_main(tree_widget, getter_func, setter_func)
        )
        btn_add_sub.clicked.connect(
            lambda: self._tree_add_sub(tree_widget, getter_func, setter_func)
        )
        btn_remove.clicked.connect(
            lambda: self._tree_remove_item(tree_widget, getter_func, setter_func)
        )
        btn_rename.clicked.connect(
            lambda: self._tree_rename_item(tree_widget, getter_func, setter_func)
        )

        hbox1 = QHBoxLayout()
        hbox1.addWidget(btn_add_main)
        hbox1.addWidget(btn_add_sub)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(btn_remove)
        hbox2.addWidget(btn_rename)

        vbox.addWidget(tree_widget)
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        return vbox

    def _populate_tree(self, tree_widget, data_dict):
        tree_widget.clear()
        for main_cat, sub_cats in data_dict.items():
            parent = QTreeWidgetItem(tree_widget)
            parent.setText(0, main_cat)
            for sub_cat in sub_cats:
                child = QTreeWidgetItem(parent)
                child.setText(0, sub_cat)
        tree_widget.expandAll()

    def _tree_add_main(self, tree_widget, getter_func, setter_func):
        text, ok = QInputDialog.getText(self, "Add Main Category", "Enter name:")
        if ok and text:
            data = getter_func()
            if text not in data:
                data[text] = []
                setter_func(data)
                self._populate_tree(tree_widget, data)

    def _tree_add_sub(self, tree_widget, getter_func, setter_func):
        current_item = tree_widget.currentItem()
        if not current_item:
            QMessageBox.warning(
                self,
                "Warning",
                "Please select a main category to add a sub-category to.",
            )
            return

        parent_text = (
            current_item.text(0)
            if not current_item.parent()
            else current_item.parent().text(0)
        )
        text, ok = QInputDialog.getText(
            self, f"Add Sub-Category to '{parent_text}'", "Enter name:"
        )
        if ok and text:
            data = getter_func()
            if text not in data[parent_text]:
                data[parent_text].append(text)
                setter_func(data)
                self._populate_tree(tree_widget, data)

    def _tree_remove_item(self, tree_widget, getter_func, setter_func):
        current_item = tree_widget.currentItem()
        if current_item:
            text = current_item.text(0)
            reply = QMessageBox.question(
                self,
                "Remove Item",
                f"Are you sure you want to remove '{text}'?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                data = getter_func()
                if current_item.parent():
                    parent_text = current_item.parent().text(0)
                    data[parent_text].remove(text)
                else:
                    del data[text]
                setter_func(data)
                self._populate_tree(tree_widget, data)

    def _tree_rename_item(self, tree_widget, getter_func, setter_func):
        current_item = tree_widget.currentItem()
        if current_item:
            old_text = current_item.text(0)
            new_text, ok = QInputDialog.getText(
                self, "Rename Item", "Enter new name:", QLineEdit.Normal, old_text
            )
            if ok and new_text and new_text != old_text:
                data = getter_func()
                if current_item.parent():
                    parent_text = current_item.parent().text(0)
                    index = data[parent_text].index(old_text)
                    data[parent_text][index] = new_text
                else:
                    data[new_text] = data.pop(old_text)
                setter_func(data)
                self._populate_tree(tree_widget, data)
