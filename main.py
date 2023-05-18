from typing import Any, Union
from markdown_it import MarkdownIt
import pygments
from pygments.formatters import HtmlFormatter
import configparser
import os.path
import sys, ctypes
from crytpo import EncryptionWrapper, SecureString
from db import Database, Conversation, Tag, Group, Action, Metadata
from PySide6.QtCore import Qt, QSortFilterProxyModel,QModelIndex, QPersistentModelIndex
from PySide6.QtGui import QStandardItem, QStandardItemModel, QAction
from PySide6.QtWidgets import QApplication, QSplitter, QTreeView, QTextEdit, QMainWindow, QToolBar, QWidget, QVBoxLayout, QFileDialog, QDialog, QDialogButtonBox, QButtonGroup, QRadioButton, QScrollArea, QTabWidget, QPushButton, QHBoxLayout, QListWidget, QListWidgetItem, QLineEdit, QMessageBox, QToolButton, QMenu, QCheckBox


class TreeModel(QStandardItemModel):
    def __init__(self, header_labels, data, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(header_labels)
        self.update_data(data)

    def update_data(self, data):
        parent_item = self.invisibleRootItem()
        # remove everything
        database = Database()
        cursor = database.get_cursor()
        tags_by_c = Tag.get_all_tags_grouped_by_conversation(cursor)

        parent_item.removeRows(0, parent_item.rowCount())
        for group_name, group_items in data.items():
            # split group_name into id and name
            split = group_name.split("-")
            group_id = int(split[0])
            group_name = "-".join(split[1:])
            group_item = QStandardItem(group_name)
            group_item.setData(group_id, Qt.UserRole)
            print(type(group_item.data(Qt.UserRole)))
            parent_item.appendRow(group_item)
            for item_name in group_items:
                child_item = QStandardItem(item_name["title"])
                child_item.setData(item_name["id"], Qt.UserRole)
                child_item.setData("con", Qt.UserRole + 1)
                if item_name["id"] in tags_by_c:
                    child_item.setData(tags_by_c[item_name["id"]], Qt.UserRole + 2)
                group_item.appendRow(child_item)
    
    def tag_changed(self, conversation):
        # loop through tree items for group with id == conversation.group_id
        for i in range(self.rowCount()):
            group_item = self.item(i)
            if int(group_item.data(Qt.UserRole)) == conversation.group_id:
                # loop through conversations
                for j in range(group_item.rowCount()):
                    conversation_item = group_item.child(j)
                    if conversation_item.data(Qt.UserRole) == conversation.id:
                        tags = Tag.get_by_conversation_id(conversation.id, cursor)
                        conversation_item.setData(tags, Qt.UserRole + 2)
                        break
                break

    def conversation_added(self, conversation):
        database = Database()
        cursor = database.get_cursor()
        tags = Tag.get_by_conversation_id(conversation.id, cursor)
        # loop through tree items for group with id == conversation.group_id
        for i in range(self.rowCount()):
            group_item = self.item(i)
            if int(group_item.data(Qt.UserRole)) == conversation.group_id:
                # add the conversation to the group
                child_item = QStandardItem(conversation.title)
                child_item.setData(conversation.id, Qt.UserRole)
                child_item.setData("con", Qt.UserRole + 1)
                child_item.setData(tags, Qt.UserRole + 2)
                group_item.appendRow(child_item)
                break

    def group_added(self, group):
        # add the group to the tree
        group_item = QStandardItem(group.name)
        group_item.setData(group.id, Qt.UserRole)
        self.appendRow(group_item)

class FilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(0)
        self.filter = ""
        self.tag_id = None

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return super().data(index, Qt.DisplayRole)
        
        if role == Qt.UserRole or role == Qt.UserRole + 1:
            source_index = self.mapToSource(index)

            print(source_index)
            return self.sourceModel().data(source_index, role)

        return super().data(index, role)
    
    def setFilter(self, filter: str) -> None:
        self.filter = filter
        self.invalidateFilter()
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex) -> bool:


        source_model = self.sourceModel()
        source_index = source_model.index(source_row, 0, source_parent)
        item_text = source_model.data(source_index, Qt.DisplayRole)

        if self.tag_id != None:
            if source_model.data(source_index, Qt.UserRole + 1) == "con":
                tags = source_model.data(source_index, Qt.UserRole + 2)
                if self.tag_id not in tags:
                    return False
        
        if not self.filter:
            return True

        if self.filter.lower() in item_text.lower():
            return True

        # Check nested rows (conversations)
        if source_model.hasChildren(source_index):
            for row in range(source_model.rowCount(source_index)):
                if self.filterAcceptsRow(row, source_index):
                    return True

        return False

def handle_item_clicked(index):
    tree_model = window.proxy_model
    item_type = tree_model.data(index, Qt.UserRole + 1)
    item_id = tree_model.data(index, Qt.UserRole)
    print(item_type, item_id)
    if item_type == "con":
        conversation_id = item_id
        database = Database()
        cursor = database.get_cursor()
        conversation = Conversation.get_by_id(conversation_id, cursor)
        encryption_wrapper = EncryptionWrapper(str(secure_key), conversation.salt)
        decrypted_content = encryption_wrapper.decrypt(
            conversation.data)

        md = MarkdownIt()
        formatter = HtmlFormatter(stylex="colorful")
        md.renderer.rules['code'] = lambda tokens, idx, options, env, slf: \
            '<div class="code-container">' \
            '<pre class="highlight"><code>' + pygments.highlight(tokens[idx]['content'], md.lexer, formatter) + '</code></pre><button class="copy-button" onclick="copyCode(this)">Copy</button></div>'

        window.update_active_conversation(conversation)
        html = md.render(decrypted_content)
        window.text_edit.setHtml(html)
        

def create_toolbar(parent):
    toolbar = QToolBar(parent)
    toolbar.setMinimumHeight(30)

    import_action = QAction("Import", parent)
    import_action.setShortcut("Ctrl+I")
    import_action.triggered.connect(parent.import_history)

    delete_action = QAction("Batch Delete", parent)
    delete_action.setShortcut("Ctrl+D")
    delete_action.triggered.connect(show_delete_dialog)

    toolbar.addAction(import_action)
    toolbar.addAction(delete_action)

    return toolbar

def show_delete_dialog():
    dialog = BatchDeleteDialog()
    dialog.exec()
    data = {}
    for group in groups:
        conversations = Conversation.get_by_group_id(group.id, cursor)
        data[f"{group.id}-{group.name}"] = [{"title": conversation.title, "id": conversation.id} for conversation in conversations]
    window.tree_model.update_data(data)
    window.refresh_tag_lists()
    window.refresh_tags()

def create_tree_view(parent):
    tree_view = QTreeView(parent)
    tree_view.setMinimumWidth(200)
    return tree_view


def create_text_edit(parent):
    text_edit = QTextEdit(parent)
    text_edit.setMinimumWidth(400)
    return text_edit


class ManageTagsDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Manage Tags")
        self.setMinimumSize(300, 200)
        
        self.layout = QVBoxLayout()
        self.top_widget = QWidget()
        self.top_widget_layout = QHBoxLayout(self.top_widget)
        self.layout.addWidget(self.top_widget)

        ## two columns
        ## left column: list of tags
        ## right column: add, delete, edit buttons
        self.setLayout(self.layout)

        self.left_column = QWidget()
        self.left_column_layout = QVBoxLayout(self.left_column)
        self.left_column_layout.setContentsMargins(0, 0, 0, 0)
        self.left_column_layout.setSpacing(0)
        self.left_column.setStyleSheet("background-color: white;")
        self.top_widget_layout.addWidget(self.left_column)

        self.right_column = QWidget()
        self.right_column_layout = QVBoxLayout(self.right_column)
        self.right_column_layout.setContentsMargins(0, 0, 0, 0)
        self.right_column_layout.setSpacing(0)
        self.right_column.setStyleSheet("background-color: white;")
        self.top_widget_layout.addWidget(self.right_column)
        
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.MultiSelection)

        database = Database()
        cursor = database.get_cursor()
        tags = Tag.get_all(cursor)
        for tag in tags:
            item = QListWidgetItem(tag.name)
            item.setData(Qt.UserRole, tag.id)
            self.tag_list.addItem(item)

        self.left_column_layout.addWidget(self.tag_list)

        self.button_add = QPushButton("Add")
        self.button_add.clicked.connect(self.add_tag)
        self.right_column_layout.addWidget(self.button_add)

        self.button_delete = QPushButton("Delete")
        self.button_delete.clicked.connect(self.delete_tag)
        self.right_column_layout.addWidget(self.button_delete)

        self.button_edit = QPushButton("Edit")
        self.button_edit.clicked.connect(self.edit_tag)
        self.right_column_layout.addWidget(self.button_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

    def add_tag(self):
        dialog = AddTagDialog()
        if dialog.tag != None:
            database = Database()
            cursor = database.get_cursor()
            tag = Tag(None, dialog.tag)
            tag_id = Tag.add(tag, cursor)
            tag.id = tag_id
            database.conn.commit()

            item = QListWidgetItem(tag.name)
            item.setData(Qt.UserRole, tag.id)
            self.tag_list.addItem(item)
    
    def delete_tag(self):
        for item in self.tag_list.selectedItems():
            tag_id = item.data(Qt.UserRole)
            database = Database()
            cursor = database.get_cursor()

            conversations = Conversation.get_by_tag_id(tag_id, cursor)
            for conversation in conversations:
                Conversation.remove_tag(conversation.id, tag_id, cursor)

            Tag.delete(tag_id, cursor)
            database.conn.commit()
            self.tag_list.takeItem(self.tag_list.row(item))

    def edit_tag(self):
        if len(self.tag_list.selectedItems()) == 0:
            return
        item = self.tag_list.selectedItems()[0]
        tag_id = item.data(Qt.UserRole)
        database = Database()
        cursor = database.get_cursor()
        tag = Tag.get_by_id(tag_id, cursor)
        dialog = AddTagDialog(False)
        if dialog.tag != None:
            tag.name = dialog.tag
            Tag.update(tag, cursor)
            database.conn.commit()
            item.setText(tag.name)

class AddTagDialog(QDialog):
    def __init__(self, add=True):
        super().__init__()
        if add:
            self.setWindowTitle("Add Tag")
        else:
            self.setWindowTitle("Edit Tag")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.tag_name_input = QLineEdit()
        self.tag_name_input.setPlaceholderText("Tag Name")
        self.layout.addWidget(self.tag_name_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

        if self.exec() == QDialog.Accepted:
            self.tag = self.tag_name_input.text()
        else :
            self.tag = None

    def deleteLater(self) -> None:
        return super().deleteLater()

class BatchDeleteDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.current_tab = "group"

        self.setWindowTitle("Batch Delete")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_group_tab(), "Groups")
        self.tab_widget.addTab(self.create_conversation_tab(), "Conversations")
        self.tab_widget.addTab(self.create_tag_tab(), "Tags")
        self.layout.addWidget(self.tab_widget)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setDisabled(True)
        self.delete_button.clicked.connect(self.delete_selected_items)
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(QPushButton("Cancel", clicked=self.reject))
        self.layout.addLayout(button_layout)

        self.tab_widget.currentChanged.connect(self.update_current_tab)

        self.setLayout(self.layout)
        self.adjustSize()
    
    def create_group_tab(self):
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_widget.setStyleSheet("background-color: white;")

        self.group_list = QListWidget()
        self.group_list.setSelectionMode(QListWidget.MultiSelection)

        database = Database()
        cursor = database.get_cursor()
        groups = Group.get_all(cursor)
        for group in groups:
            if group.id == 1:
                continue
            item = QListWidgetItem(group.name)
            item.setData(Qt.UserRole, group.id)
            self.group_list.addItem(item)
        
        container_layout.addWidget(self.group_list)
        self.group_list.itemSelectionChanged.connect(self.update_delete_button)
        
        return container_widget
    
    def create_conversation_tab(self):
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_widget.setStyleSheet("background-color: white;")

        self.conversation_list = QListWidget()
        self.conversation_list.setSelectionMode(QListWidget.MultiSelection)

        database = Database()
        cursor = database.get_cursor()
        conversations = Conversation.get_all(cursor)
        for conversation in conversations:
            item = QListWidgetItem(conversation.title)
            item.setData(Qt.UserRole, conversation.id)
            self.conversation_list.addItem(item)
        
        container_layout.addWidget(self.conversation_list)
        self.conversation_list.itemSelectionChanged.connect(self.update_delete_button)
        
        return container_widget

    def create_tag_tab(self):
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_widget.setStyleSheet("background-color: white;")

        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.MultiSelection)

        database = Database()
        cursor = database.get_cursor()
        tags = Tag.get_all(cursor)
        for tag in tags:
            item = QListWidgetItem(tag.name)
            item.setData(Qt.UserRole, tag.id)
            self.tag_list.addItem(item)
        
        container_layout.addWidget(self.tag_list)
        self.tag_list.itemSelectionChanged.connect(self.update_delete_button)
        
        return container_widget
    
    def update_current_tab(self, index):
        if index == 0:
            self.current_tab = "group"
        elif index == 1:
            self.current_tab = "conversation"
        elif index == 2:
            self.current_tab = "tag"

    def update_delete_button(self):
        num_of_selected_items = 0
        if self.current_tab == "group":
            num_of_selected_items = len(self.group_list.selectedItems())
        elif self.current_tab == "conversation":
            num_of_selected_items = len(self.conversation_list.selectedItems())
        elif self.current_tab == "tag":
            num_of_selected_items = len(self.tag_list.selectedItems())
        
        if num_of_selected_items > 0:
            self.delete_button.setDisabled(False)

    def delete_selected_items(self):
        if self.current_tab == "group":
            for item in self.group_list.selectedItems():
                group_id = item.data(Qt.UserRole)
                database = Database()
                cursor = database.get_cursor()
                Group.delete(group_id, cursor)
                database.conn.commit()
                self.group_list.takeItem(self.group_list.row(item))
        elif self.current_tab == "conversation":
            for item in self.conversation_list.selectedItems():
                conversation_id = item.data(Qt.UserRole)
                database = Database()
                cursor = database.get_cursor()
                
                tags = Tag.get_by_conversation_id(conversation_id, cursor)
                for tag in tags:
                    Conversation.remove_tag(conversation_id, tag.id, cursor)

                Conversation.delete(conversation_id, cursor)
                database.conn.commit()
                self.conversation_list.takeItem(self.conversation_list.row(item))
        elif self.current_tab == "tag":
            for item in self.tag_list.selectedItems():
                tag_id = item.data(Qt.UserRole)
                database = Database()
                cursor = database.get_cursor()

                conversations = Conversation.get_by_tag_id(tag_id, cursor)
                for conversation in conversations:
                    Conversation.remove_tag(conversation.id, tag_id, cursor)

                Tag.delete(tag_id, cursor)
                database.conn.commit()
                self.tag_list.takeItem(self.tag_list.row(item))

class GroupSelectionDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Select Group")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        scrollarea = QScrollArea()
        scrollarea.setWidgetResizable(True)
        scrollarea.setMinimumWidth(300)

        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_widget.setStyleSheet("background-color: white;")

        self.group_button_group = QButtonGroup()

        database = Database()
        cursor = database.get_cursor()
        groups = Group.get_all(cursor)
        for group in groups:
            radio_button = QRadioButton(group.name)
            self.group_button_group.addButton(radio_button, group.id)
            container_layout.addWidget(radio_button)

        scrollarea.setWidget(container_widget)
        self.layout.addWidget(scrollarea)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

        if self.exec() == QDialog.Accepted:
            self.selected_group_id = self.group_button_group.checkedId()
        else :
            self.selected_group_id = None

    def deleteLater(self) -> None:
        return super().deleteLater()

class AddGroupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add Group")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.group_name_input = QLineEdit()
        self.group_name_input.setPlaceholderText("Group Name")
        self.layout.addWidget(self.group_name_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

        if self.exec() == QDialog.Accepted:
            self.group = self.group_name_input.text()
        else :
            self.group = None

    def deleteLater(self) -> None:
        return super().deleteLater()

class MainWindow(QMainWindow):
    def __init__(self, header_labels, data):
        super().__init__()
        self.active_conversation = None

        # Create the widgets
        self.tree_view = create_tree_view(self)
        self.text_edit = create_text_edit(self)
        self.toolbar = create_toolbar(self)

        self.left_widget = QWidget()
        self.leftcolumn = QVBoxLayout(self.left_widget)
        self.leftcolumn.setContentsMargins(0, 0, 0, 0)

        self.right_widget = QWidget()
        self.rightcolumn = QVBoxLayout(self.right_widget)
        self.rightcolumn.setSpacing(0)
        self.rightcolumn.setContentsMargins(0, 0, 0, 0)

        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Filter")

        self.leftcolumn.addWidget(filter_input)

        ## list of tags
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SingleSelection)
        self.tag_list.setMaximumHeight(100)
        self.leftcolumn.addWidget(self.tag_list)
        self.tag_list.itemSelectionChanged.connect(self.tag_selected)
        self.refresh_tag_lists()

        toolbar = QToolBar()
        toolbar.setMinimumHeight(30)
        add_group_action = QAction("Add Group", self)
        add_group_action.triggered.connect(self.add_group)
        
        clear_tag_selection_action = QAction("Clear Tag", self)
        clear_tag_selection_action.triggered.connect(self.clear_tag_selection)

        toggle_expand_action = QAction("Expand", self)
        toggle_expand_action.triggered.connect(self.tree_view.expandAll)

        toggle_collapse_action = QAction("Collapse", self)
        toggle_collapse_action.triggered.connect(self.tree_view.collapseAll)

        toolbar.addAction(add_group_action)
        toolbar.addAction(clear_tag_selection_action)
        toolbar.addAction(toggle_expand_action)
        toolbar.addAction(toggle_collapse_action)
        self.leftcolumn.addWidget(toolbar)
        
        self.leftcolumn.addWidget(self.tree_view)
        # Create a splitter to handle resizing
        self.rightcolumn.addWidget(self.text_edit)
        
        toolbar_under_textedit = self.create_toolbar_under_text_edit()

        self.rightcolumn.addWidget(toolbar_under_textedit)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self.left_widget)
        splitter.addWidget(self.right_widget)
        splitter.setChildrenCollapsible(False)

        # Set up the tree model
        self.tree_model = TreeModel(header_labels, data)
        self.proxy_model = FilterProxyModel()
        self.proxy_model.setSourceModel(self.tree_model)

        # Set the model on the tree view
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.clicked.connect(handle_item_clicked)

        filter_input.textChanged.connect(self.proxy_model.setFilter)

        # Set up the layout for the toolbar and splitter
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(splitter)

        # Create a central widget to hold the layout
        central_widget = QWidget(self)
        central_widget.setLayout(layout)

        # Set the central widget and window properties
        self.setCentralWidget(central_widget)
        self.setWindowTitle("Tree View Demo")
        self.setGeometry(100, 100, 640, 480)
        self.setMinimumSize(600, 400)

    def update_active_conversation(self, conversation):
        self.active_conversation = conversation
        window.refresh_tags()

    def clear_tag_selection(self):
        self.tag_list.clearSelection()
        self.proxy_model.tag_id = None
        self.proxy_model.invalidateFilter()

    def create_toolbar_under_text_edit(self):
        self.toolbar_textedit = QToolBar(self)
        self.toolbar_textedit.setMinimumHeight(10)
        self.toolbar_textedit.setStyleSheet("background-color: white; border: 1px solid black; border-top: 0px")
        button = QToolButton()
        button.setText("Tags  ")
        self.toolbar_textedit.addWidget(button)

        # Create the menu
        self.menu = QMenu(button)
        self.menu.setStyleSheet(
                """
                QMenu {
                    background-color: white;
                    color: black;
                }
                QMenu::item:selected {
                    background-color: lightgray;
                    color: black;
                }
                """
            )

        self.refresh_tags()

        # Set the menu on the tool button
        button.setMenu(self.menu)
        button.setPopupMode(QToolButton.MenuButtonPopup)

        button_manage_tags = QToolButton()
        button_manage_tags.setText("Manage Tags")
        button_manage_tags.clicked.connect(self.show_manage_tags_dialog)
        self.toolbar_textedit.addWidget(button_manage_tags)

        return self.toolbar_textedit
    
        
    def show_manage_tags_dialog(self):
        dialog = ManageTagsDialog()
        dialog.exec()
        self.refresh_tags()
        self.refresh_tag_lists()

    def refresh_tag_lists(self):
        self.tag_list.clear()
        database = Database()
        cursor = database.get_cursor()
        tags = Tag.get_all(cursor)
        for tag in tags:
            item = QListWidgetItem(tag.name + "(" + str(tag.count) + ")")
            item.setData(Qt.UserRole, tag.id)
            self.tag_list.addItem(item)

    def tag_selected(self):
        if len(self.tag_list.selectedItems()) == 0:
            self.proxy_model.tag_id = None
            self.proxy_model.invalidateFilter()
            return
        print(self.tag_list.selectedItems())
        item = self.tag_list.selectedItems()[0]
        tag_id = item.data(Qt.UserRole)
        self.proxy_model.tag_id = tag_id
        self.proxy_model.invalidateFilter()
        
    
    def refresh_tags(self):
        menu = self.menu
        menu.clear()
        database = Database()
        cursor = database.get_cursor()
        tags = Tag.get_all(cursor)    

        print(self.active_conversation)
        
        if self.active_conversation != None:
            tags_of_conversation = Tag.get_by_conversation_id(self.active_conversation.id, cursor)

        for tag in tags:
            action = menu.addAction(tag.name)
            action.setData(tag.id)

            if self.active_conversation != None:
                action.setCheckable(True)
            else:
                action.setCheckable(False)

            if self.active_conversation != None:
                for tag_of_conversation in tags_of_conversation:
                    if tag_of_conversation.id == tag.id:
                        action.setChecked(True)
                        break
            
            action.triggered.connect(lambda checked = None, action = action: self.handle_tag_selected(action))
            menu.addAction(action)
        
        print(menu.actions())
    
    def handle_tag_selected(self, action):
        if self.active_conversation == None:
            return

        print(action)
        tag_id = action.data()
        if action.isChecked():
            database = Database()
            cursor = database.get_cursor()
            
            Conversation.add_tag(self.active_conversation.id, tag_id, cursor)
            database.conn.commit()

        else:
            database = Database()
            cursor = database.get_cursor()
            
            Conversation.remove_tag(self.active_conversation.id, tag_id, cursor)
            database.conn.commit()
        self.tree_model.tag_changed(self.active_conversation)
        self.refresh_tag_lists()

    def add_group(self):
        dialog = AddGroupDialog()
        if dialog.group != None:
            database = Database()
            cursor = database.get_cursor()
            group = Group(None, dialog.group)
            group_id = Group.add(group, cursor)
            group.id = group_id
            database.conn.commit()

            self.tree_model.group_added(group)

    def import_history(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("Markdown files (*.md)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)

        if file_dialog.exec():
            file_name = file_dialog.selectedFiles()[0]
            with open(file_name, "r", encoding="utf-8") as f:
                content = f.read()

                lines = content.split("\n")
                if lines:
                    title = lines[0].lstrip('#').strip()  # Extract the title
                    # Store the remaining content
                    remaining_content = '\n'.join(lines[1:])

                    group_dialog = GroupSelectionDialog()

                    # check if group_dialog.selected_group_id exists
                    if group_dialog.selected_group_id == None:
                        return

                    group_id = group_dialog.selected_group_id 

                    salt = EncryptionWrapper.generate_salt()
                    encryption_wrapper = EncryptionWrapper(str(secure_key), salt)
                    encrypted_content = encryption_wrapper.encrypt(
                        remaining_content)
                    database = Database()
                    cursor = database.get_cursor()
                    conversation = Conversation(
                        None, title, group_id, encrypted_content, None, salt)
                    conversation_id = Conversation.add(conversation, cursor)
                    database.conn.commit()
                    conversation.id = conversation_id
                    self.tree_model.conversation_added(conversation)

                    retrieved_conversation = Conversation.get_by_id(
                        conversation_id, cursor)
                    new_encryption_wrapper = EncryptionWrapper(
                        str(secure_key), retrieved_conversation.salt)
                    decrypted_content = new_encryption_wrapper.decrypt(
                        retrieved_conversation.data)


                    md = MarkdownIt()
                    formatter = HtmlFormatter(stylex="colorful")
                    md.renderer.rules['code'] = lambda tokens, idx, options, env, slf: \
                        '<div class="code-container">' \
                        '<pre class="highlight"><code>' + pygments.highlight(tokens[idx]['content'], md.lexer, formatter) + '</code></pre><button class="copy-button" onclick="copyCode(this)">Copy</button></div>'
                    
                    window.update_active_conversation(retrieved_conversation)

                    html = md.render(decrypted_content)
                    self.text_edit.setHtml(html)                   

class PasswordDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Create a password.")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.layout.addWidget(self.password_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

        if self.exec() == QDialog.Accepted:
            self.password = self.password_input.text()
        else :
            self.password = None

class InputPasswordDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Input password.")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.layout.addWidget(self.password_input)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

        if self.exec() == QDialog.Accepted:
            self.password = self.password_input.text()
        else :
            self.password = None

def check_c_libraries():
    if sys.platform == 'win32':
        libc = 'msvcrt'
    elif sys.platform == 'darwin':
        libc = 'libSystem.dylib'
    else:
        libc = 'libc.so.6'

    try:
        ctypes.cdll.LoadLibrary(libc)
    except OSError:
        message_box = QMessageBox()
        message_box.setText(f"Could not load {libc}.")
        message_box.exec()
        sys.exit(1)

if __name__ == "__main__":
    secure_key = None

    app = QApplication([])

    check_c_libraries()

    config_file = "config.ini"

    if not os.path.exists(config_file):
        config = configparser.ConfigParser()
        config["app"] = {"initialized": "False"}
        with open(config_file, "w") as f:
            config.write(f)

    config = configparser.ConfigParser()
    config.read(config_file)

    # Check if the app has been initialized
    if config["app"]["initialized"] == "False":
        # backup db.sqlite
        if os.path.exists("db.sqlite"):
            os.rename("db.sqlite", "db.sqlite.bak")

        database = Database("db.sqlite")
        database.initialize()

        create_password_dialog = PasswordDialog()
        if create_password_dialog.password != None:
            password = create_password_dialog.password
            salt = EncryptionWrapper.generate_salt()
            key = EncryptionWrapper.generate_strong_key()
            encryption_wrapper = EncryptionWrapper(password, salt)
            encrypted_key = encryption_wrapper.encrypt(key)
            database = Database()
            cursor = database.get_cursor()
            blob = Metadata(None, "blob", encrypted_key)
            Metadata.add(blob, cursor)
            salt = Metadata(None, "salt", salt)
            Metadata.add(salt, cursor)
            database.conn.commit()

        config["app"]["initialized"] = "True"
        with open(config_file, "w") as f:
            config.write(f)
    
    input_password_dialog = InputPasswordDialog()
    if input_password_dialog.password != None:
        password = input_password_dialog.password
        database = Database()
        cursor = database.get_cursor()
        encrypted_key = Metadata.get_by_key("blob", cursor).value
        salt = Metadata.get_by_key("salt", cursor).value
        encryption_wrapper = EncryptionWrapper(password, salt)
        try:
            secure_key = SecureString(encryption_wrapper.decrypt(encrypted_key))
        except:
            message_box = QMessageBox()
            message_box.setText("Incorrect password.")
            message_box.exec()
            sys.exit(0)
    else:
        sys.exit(0)

    
    database = Database("db.sqlite")
    cursor = database.get_cursor()
    groups = Group.get_all(cursor)
    
    # populate group in to data
    data = {}
    for group in groups:
        conversations = Conversation.get_by_group_id(group.id, cursor)
        data[f"{group.id}-{group.name}"] = [{"title": conversation.title, "id": conversation.id} for conversation in conversations]

    header_labels = [""]
    window = MainWindow(header_labels, data)
    window.show()
    app.exec()
