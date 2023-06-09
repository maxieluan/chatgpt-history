from typing import Union
from appdirs import user_data_dir
from markdown_it import MarkdownIt
import pygments
from pygments.formatters import HtmlFormatter
import configparser
import os.path, glob
import sys, ctypes
from crytpo import EncryptionWrapper, SecureString
from db import Database, Conversation, Tag, Group, Metadata
from PySide6.QtCore import Qt, QSortFilterProxyModel,QModelIndex, QPersistentModelIndex
from PySide6.QtGui import QStandardItem, QStandardItemModel, QAction, QColor, QFont,QMouseEvent, QShortcut, QTextCursor, QTextDocument, QPalette
from PySide6.QtWidgets import QApplication, QSplitter, QTreeView, QTextEdit, QMainWindow, QToolBar, QWidget, QVBoxLayout, QFileDialog, QDialog, QDialogButtonBox, QTabWidget, QPushButton, QHBoxLayout, QListWidget, QListWidgetItem, QLineEdit, QMessageBox, QToolButton, QSizePolicy, QInputDialog, QStyledItemDelegate,QStyle
from group import GroupSelectionDialog, AddGroupDialog, ChangeGroupDialog
from tag import ManageTagsDialog, AddTagsDialog


class TreeModel(QStandardItemModel):
    def __init__(self, header_labels, data, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(header_labels)
        self.update_data(data)

    def update_data(self, data):
        parent_item = self.invisibleRootItem()
        # remove everything
        database = Database.get_instance()
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
                        tag_ids = [tag.id for tag in conversation.tags]
       
                        conversation_item.setData(tag_ids, Qt.UserRole + 2)
                        break
                break
    
    def group_changed(self, old_group_id, new_group_id, conversation):
        for i in range(self.rowCount()):
            group_item = self.item(i)
            if int(group_item.data(Qt.UserRole)) == old_group_id:
                # loop through conversations
                for j in range(group_item.rowCount()):
                    conversation_item = group_item.child(j)
                    if conversation_item.data(Qt.UserRole) == conversation.id:
                        # remove the conversation from the group
                        group_item.removeRow(j)
                break
        # loop through tree items for group with id == new_group_id
        for i in range(self.rowCount()):
            group_item = self.item(i)
            if int(group_item.data(Qt.UserRole)) == new_group_id:
                # add the conversation to the group
                child_item = QStandardItem(conversation.title)
                child_item.setData(conversation.id, Qt.UserRole)
                child_item.setData("con", Qt.UserRole + 1)
                child_item.setData(conversation.tags, Qt.UserRole + 2)
                group_item.appendRow(child_item)
                break
        

    def conversation_added(self, conversation):
        database = Database.get_instance()
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
            return self.sourceModel().data(source_index, role)

        return super().data(index, role)
    
    def setFilter(self, filter: str) -> None:
        self.filter = filter
        self.invalidateFilter()
        window.tree_view.expandAll()
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex) -> bool:
        source_model = self.sourceModel()
        source_index = source_model.index(source_row, 0, source_parent)
        item_text = source_model.data(source_index, Qt.DisplayRole)

        if self.tag_id != None:
            if source_model.data(source_index, Qt.UserRole + 1) == "con":
                tags = source_model.data(source_index, Qt.UserRole + 2)
                if tags == None:
                    return False
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
    if item_type == "con":
        conversation_id = item_id
        database = Database.get_instance()
        cursor = database.get_cursor()
        conversation = Conversation.get_by_id(conversation_id, cursor)
        tags = Tag.get_by_conversation_id(conversation_id, cursor)
        conversation.tags = tags
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
        window.text_edit.setReadOnly(True)
        window.reset_edit()
        

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
    database = Database.get_instance()
    cursor = database.get_cursor()
    groups = Group.get_all(cursor)
    for group in groups:
        conversations = Conversation.get_by_group_id(group.id, cursor)
        data[f"{group.id}-{group.name}"] = [{"title": conversation.title, "id": conversation.id} for conversation in conversations]
    window.tree_model.update_data(data)
    window.refresh_tag_lists()

def create_tree_view(parent):
    tree_view = QTreeView(parent)
    tree_view.setMinimumWidth(200)
    return tree_view


def create_text_edit(parent):
    text_edit = QTextEdit(parent)
    text_edit.setMinimumWidth(400)
    return text_edit


class BatchDeleteDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.current_tab = "group"

        self.setWindowTitle("Batch Delete")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter")
        self.filter_input.textChanged.connect(self.filter_changed)
        self.layout.addWidget(self.filter_input)

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

    def filter_changed(self):
        filter_text = self.filter_input.text()
        if self.current_tab == "group":
            for i in range(self.group_list.count()):
                item = self.group_list.item(i)
                if filter_text.lower() in item.text().lower():
                    item.setHidden(False)
                else:
                    item.setHidden(True)
        elif self.current_tab == "conversation":
            for i in range(self.conversation_list.count()):
                item = self.conversation_list.item(i)
                if filter_text.lower() in item.text().lower():
                    item.setHidden(False)
                else:
                    item.setHidden(True)
        elif self.current_tab == "tag":
            for i in range(self.tag_list.count()):
                item = self.tag_list.item(i)
                if filter_text.lower() in item.text().lower():
                    item.setHidden(False)
                else:
                    item.setHidden(True)
    
    def create_group_tab(self):
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_widget.setStyleSheet("background-color: white;")

        self.group_list = QListWidget()
        self.group_list.setSelectionMode(QListWidget.MultiSelection)

        database = Database.get_instance()
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

        database = Database.get_instance()
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

        database = Database.get_instance()
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
        
        self.filter_changed()

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
                database = Database.get_instance()
                cursor = database.get_cursor()
                Group.delete(group_id, cursor)
                database.conn.commit()
                self.group_list.takeItem(self.group_list.row(item))
        elif self.current_tab == "conversation":
            for item in self.conversation_list.selectedItems():
                conversation_id = item.data(Qt.UserRole)
                database = Database.get_instance()
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
                database = Database.get_instance()
                cursor = database.get_cursor()

                conversations = Conversation.get_by_tag_id(tag_id, cursor)
                for conversation in conversations:
                    Conversation.remove_tag(conversation.id, tag_id, cursor)

                Tag.delete(tag_id, cursor)
                database.conn.commit()
                self.tag_list.takeItem(self.tag_list.row(item))

class MainWindow(QMainWindow):
    def __init__(self, header_labels, data):
        super().__init__()
        self.active_conversation = None

        # Create the widgets
        self.tree_view = create_tree_view(self)
        self.text_edit = create_text_edit(self)
        pallette = self.text_edit.palette()
        pallette.setBrush(QPalette.Base, Qt.white)
        pallette.setBrush(QPalette.Text, Qt.black)
        pallette.setBrush(QPalette.Highlight, Qt.yellow)
        pallette.setBrush(QPalette.HighlightedText, Qt.black)
        self.text_edit.setPalette(pallette)

        self.toolbar = create_toolbar(self)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.find_input.setStyleSheet("background-color: white; border: 1px solid black; border-radius: 5px;")
        self.find_input.setMinimumWidth(200)
        self.find_input.setMaximumWidth(200)
        self.find_input.textChanged.connect(self.find_text)
        self.find_input.returnPressed.connect(self.find_next)


        # ctrl + return on find_input to find previous
        self.find_input.find_previous = QShortcut("Ctrl+Return", self.find_input)
        self.find_input.find_previous.activated.connect(self.find_previous)
        
        self.find_input.setClearButtonEnabled(True)
        self.find_input.setFocus()
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.find_input)

        self.find_shortcut = QShortcut("Ctrl+F", self)
        self.find_shortcut.activated.connect(self.find_input.setFocus)

        self.left_widget = QWidget()
        self.leftcolumn = QVBoxLayout(self.left_widget)
        self.leftcolumn.setContentsMargins(0, 0, 0, 0)

        self.right_widget = QWidget()
        self.rightcolumn = QVBoxLayout(self.right_widget)
        self.rightcolumn.setSpacing(0)
        self.rightcolumn.setContentsMargins(0, 0, 0, 0)

        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Filter")

        self.filter_shortcut = QShortcut("Ctrl+L", self)
        self.filter_shortcut.activated.connect(filter_input.setFocus)

        # esc to exit filter and find_input
        self.filter_shortcut = QShortcut("Esc", self)
        self.filter_shortcut.activated.connect(self.find_input.clearFocus)
        self.filter_shortcut.activated.connect(filter_input.clearFocus)

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

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_data)

        toggle_expand_action = QAction("Expand", self)
        toggle_expand_action.triggered.connect(self.tree_view.expandAll)

        toggle_collapse_action = QAction("Collapse", self)
        toggle_collapse_action.triggered.connect(self.tree_view.collapseAll)

        toolbar.addAction(add_group_action)
        toolbar.addAction(clear_tag_selection_action)
        toolbar.addAction(refresh_action)
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
        
        # handle when items displayed is editted
        self.tree_view.entered.connect(self.tree_view_editted)
        self.tree_view.clicked.connect(handle_item_clicked)
        self.tree_model.dataChanged.connect(self.tree_view_editted)

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
        self.setWindowTitle("ChatGPT History")
        self.setGeometry(100, 100, 640, 480)
        self.setMinimumSize(600, 400)
       

    def find_previous(self):
        # find the previous occurence of the text
        text = self.find_input.text()
        if text == "":
            return
        self.text_edit.find(text, QTextDocument.FindBackward)
    
    def find_text(self):
        # find the text, move the cursor to the next occurence
        # highlight the text in blue rect
        text = self.find_input.text()
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.Start)
        selections = []
        while cursor.position() < self.text_edit.document().characterCount():
            cursor = self.text_edit.document().find(text, cursor)
            if cursor.isNull():
                break
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("yellow"))
            selection.cursor = cursor
            selections.append(selection)
        self.text_edit.setExtraSelections(selections)


    def find_next(self):
        # find the next occurence of the text
        text = self.find_input.text()
        if text == "":
            return
        self.text_edit.find(text)
       

    def tree_view_editted(self):
        item = self.tree_view.currentIndex()
        if item.isValid():
            item_type = self.proxy_model.data(item, Qt.UserRole + 1)
            item_id = self.proxy_model.data(item, Qt.UserRole)
            if item_type == "con":
                database = Database.get_instance()
                cursor = database.get_cursor()
                title = self.proxy_model.data(item, Qt.DisplayRole)
                Conversation.update_title(item_id, title, cursor)
                database.conn.commit()
            else:
                database = Database.get_instance()
                cursor = database.get_cursor()
                title = self.proxy_model.data(item, Qt.DisplayRole)
                group = Group(item_id, title)
                Group.update(group, cursor)
                database.conn.commit()

        
    def refresh_data(self):
        database = Database.get_instance()
        cursor = database.get_cursor()
        data = {}
        groups = Group.get_all(cursor)
        for group in groups:
            conversations = Conversation.get_by_group_id(group.id, cursor)
            data[f"{group.id}-{group.name}"] = [{"title": conversation.title, "id": conversation.id} for conversation in conversations]
        self.tree_model.update_data(data)

    def update_active_conversation(self, conversation):
        self.active_conversation = conversation

    def clear_tag_selection(self):
        self.tag_list.clearSelection()
        self.proxy_model.tag_id = None
        self.proxy_model.invalidateFilter()

    def create_toolbar_under_text_edit(self):
        self.toolbar_textedit = QToolBar(self)
        self.toolbar_textedit.setMinimumHeight(10)
        self.toolbar_textedit.setStyleSheet("background-color: white; border: 1px solid black; border-top: 0px")
        
        add_tags_button = QToolButton()
        add_tags_button.setText("Add Tags")
        add_tags_button.clicked.connect(self.add_tags)
        self.toolbar_textedit.addWidget(add_tags_button)

        button_manage_tags = QToolButton()
        button_manage_tags.setText("Manage Tags")
        button_manage_tags.clicked.connect(self.show_manage_tags_dialog)
        self.toolbar_textedit.addWidget(button_manage_tags)

        button_change_group = QToolButton()
        button_change_group.setText("Change Group")
        button_change_group.clicked.connect(self.change_group)
        self.toolbar_textedit.addWidget(button_change_group)

        spacer_widget = QWidget()
        spacer_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar_textedit.addWidget(spacer_widget)

        self.save_button = QToolButton()
        self.save_button.setText("Save")
        self.save_button.clicked.connect(self.save)
        self.toolbar_textedit.addWidget(self.save_button)
        self.save_button.setDisabled(True)

        self.toggle_edit_button = QToolButton()
        self.toggle_edit_button.setText("Edit")
        self.toggle_edit_button.setCheckable(True)
        self.toggle_edit_button.clicked.connect(self.toggle_edit)
        self.toolbar_textedit.addWidget(self.toggle_edit_button)

        return self.toolbar_textedit
    
    def save(self):
        if self.active_conversation == None:
            return
        database = Database.get_instance()
        cursor = database.get_cursor()
        encryption_wrapper = EncryptionWrapper(str(secure_key), self.active_conversation.salt)
        encrypted_content = encryption_wrapper.encrypt(self.text_edit.toPlainText())
        self.active_conversation.data = encrypted_content
        Conversation.update_data(self.active_conversation.id, encrypted_content, cursor)
        database.conn.commit()
        self.save_button.setDisabled(True)
        self.reset_edit()
    
    def reset_edit(self):
        self.toggle_edit_button.setChecked(False)
        self.toggle_edit()

    def toggle_edit(self):
        if self.active_conversation == None:
            return
        if self.toggle_edit_button.isChecked():
            self.save_button.setDisabled(False)
            encryption_wrapper = EncryptionWrapper(str(secure_key), self.active_conversation.salt)
            decrypted_content = encryption_wrapper.decrypt(
                self.active_conversation.data)
            self.text_edit.setText(decrypted_content)
            self.text_edit.setReadOnly(False)
        else:
            self.save_button.setDisabled(True)
            encryption_wrapper = EncryptionWrapper(str(secure_key), self.active_conversation.salt)
            decrypted_content = encryption_wrapper.decrypt(
                self.active_conversation.data)
            md = MarkdownIt()
            formatter = HtmlFormatter(stylex="colorful")
            md.renderer.rules['code'] = lambda tokens, idx, options, env, slf: \
                '<div class="code-container">' \
                '<pre class="highlight"><code>' + pygments.highlight(tokens[idx]['content'], md.lexer, formatter) + '</code></pre><button class="copy-button" onclick="copyCode(this)">Copy</button></div>'

            html = md.render(decrypted_content)
            self.text_edit.setHtml(html)
            self.text_edit.setReadOnly(True)


    def add_tags(self):
        if self.active_conversation == None:
            return
        dialog = AddTagsDialog(self)
        dialog.exec()
        self.refresh_tag_lists()
        
    
    def change_group(self):
        dialog = ChangeGroupDialog(self)
        dialog.exec()

    
    def show_manage_tags_dialog(self):
        dialog = ManageTagsDialog()
        dialog.exec()
        self.refresh_tag_lists()

    def refresh_tag_lists(self):
        self.tag_list.clear()
        database = Database.get_instance()
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
        item = self.tag_list.selectedItems()[0]
        tag_id = item.data(Qt.UserRole)
        self.proxy_model.tag_id = tag_id
        self.proxy_model.invalidateFilter()
        window.tree_view.expandAll()
    
    def handle_tag_selected(self, action):
        if self.active_conversation == None:
            return
        
        tag_id = action.data()
        if action.isChecked():
            database = Database.get_instance()
            cursor = database.get_cursor()
            
            Conversation.add_tag(self.active_conversation.id, tag_id, cursor)
            database.conn.commit()

        else:
            database = Database.get_instance()
            cursor = database.get_cursor()
            
            Conversation.remove_tag(self.active_conversation.id, tag_id, cursor)
            database.conn.commit()
        tags = Tag.get_by_conversation_id(self.active_conversation.id, cursor)
        self.active_conversation.tags = tags
        self.tree_model.tag_changed(self.active_conversation)
        self.refresh_tag_lists()

    def add_group(self):
        dialog = AddGroupDialog()
        if dialog.group != None:
            database = Database.get_instance()
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
                    database = Database.get_instance()
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
                    self.text_edit.setReadOnly(True)

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

class CustomDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        item = index.data(Qt.DisplayRole)
        text_lines = item.split('\n')

        # if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("lightblue"))
            painter.setPen(option.palette.highlightedText().color())
        
        # if hovers
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, option.palette.alternateBase())
            painter.setPen(option.palette.highlightedText().color())
            
        # Draw the first line with default color
        default_color = option.palette.text().color()
        default_font = QFont()
        default_font.setBold(True)
        default_font.setPointSize(10)
        painter.setFont(default_font)
        painter.setPen(default_color)
        painter.drawText(option.rect, Qt.TextSingleLine, text_lines[0])

        # Draw the second line with a different color
        second_line_rect = option.rect.translated(0, option.fontMetrics.height())
        second_line_font = QFont()
        second_line_font.setPointSize(8)
        second_line_color = QColor("Gray")  # Change the color as desired
        painter.setPen(second_line_color)
        painter.setFont(second_line_font)
        painter.drawText(second_line_rect, Qt.TextSingleLine, text_lines[1])

    def sizeHint(self, option, index):
        return super().sizeHint(option, index)
    

class DbListWidget(QListWidget):
    def mousePressEvent(self, event: QMouseEvent) -> None:  
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            self.setCurrentIndex(index)
        super().mousePressEvent(event)      

class DbManager(QDialog):
    def __init__(self, data_dir):
        super().__init__()
        self.data_dir = data_dir
        self.setWindowTitle("Database Manager")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        delegate = CustomDelegate()

        self.db_list = DbListWidget()
        self.db_list.setItemDelegate(delegate)
        self.db_list.setSelectionMode(QListWidget.SingleSelection)

        button_row = QHBoxLayout()

        button_new = QPushButton("New")
        button_new.clicked.connect(self.new_db)
        button_row.addWidget(button_new)

        button_import = QPushButton("Import")
        button_import.clicked.connect(self.import_db)
        button_row.addWidget(button_import)

        self.layout.addLayout(button_row)

        self.layout.addWidget(self.db_list)

        config_file = "config.ini"
        config_path = os.path.join(data_dir, config_file)
        config = configparser.ConfigParser()

        config.read(config_path)

        ## read section db_list, as a list of key value pairs
        db_list = config.items("db_list")
        for db in db_list:
            # each item has two lines, first line is name, second line is path
            item = QListWidgetItem(db[0]+"\n"+db[1])
            item.setData(Qt.UserRole, db[1])
            self.db_list.addItem(item)

            
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

        if self.exec() == QDialog.Accepted:
            if self.db_list.selectedItems():
                self.selected_db = self.db_list.selectedItems()[0].data(Qt.UserRole)
            else:
                self.selected_db = db_list[0][1]
        else :
            self.selected_db = None
    
    def import_db(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("Database files (*.chdb)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)

        if file_dialog.exec():
            file_name = file_dialog.selectedFiles()[0]
            file_path = os.path.abspath(file_name)
            file_name = os.path.basename(file_path)
            
            config_file = "config.ini"
            config_path = os.path.join(self.data_dir, config_file)
            config = configparser.ConfigParser()
            config.read(config_path)
            db_list = config.items("db_list")
            for db in db_list:
                if db[1] == file_path:
                    message_box = QMessageBox()
                    message_box.setText(f"Database {file_name} already exists.")
                    message_box.exec()
                    return
            
            db_name, ok = QInputDialog.getText(self, "Import Database", "Enter database name:")
            if ok:
                config["db_list"][db_name] = file_path
                with open(config_path, "w") as f:
                    config.write(f)
                item = QListWidgetItem(db_name + "\n" + file_path)
                item.setData(Qt.UserRole, file_path)
                self.db_list.addItem(item)
                self.db_list.setCurrentItem(item)
                self.selected_db = file_path
                return
            

    def new_db(self):
        ## open file dialog, select folder to create new db
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.Directory)
        if file_dialog.exec():
            dir_path = file_dialog.selectedFiles()[0]
            ## prompt for db name
            db_name, ok = QInputDialog.getText(self, "New Database", "Enter database name:")
            if ok:
                db_path = os.path.join(dir_path, db_name + ".chdb")
                db_path = os.path.abspath(db_path)
                if os.path.exists(db_path):
                    message_box = QMessageBox()
                    message_box.setText(f"Database {db_name} already exists.")
                    message_box.exec()
                    return
                Database.initialize(db_path)
                database = Database.get_instance()
                database.init()

                create_password_dialog = PasswordDialog()
                if create_password_dialog.password != None:
                    password = create_password_dialog.password
                    salt = EncryptionWrapper.generate_salt()
                    key = EncryptionWrapper.generate_strong_key()
                    encryption_wrapper = EncryptionWrapper(password, salt)
                    encrypted_key = encryption_wrapper.encrypt(key)
                    database = Database.get_instance()
                    cursor = database.get_cursor()
                    blob = Metadata(None, "blob", encrypted_key)
                    Metadata.add(blob, cursor)
                    salt = Metadata(None, "salt", salt)
                    Metadata.add(salt, cursor)
                    database.conn.commit()
                else:
                    sys.exit(0)

                config_file = "config.ini"
                config_path = os.path.join(self.data_dir, config_file)
                config = configparser.ConfigParser()
                config.read(config_path)
                config["db_list"][db_name] = db_path
                with open(config_path, "w") as f:
                    config.write(f)
                item = QListWidgetItem(db_name + "\n" + db_path)
                item.setData(Qt.UserRole, db_path)
                self.db_list.addItem(item)
                self.db_list.setCurrentItem(item)
                self.selected_db = db_path
                return


if __name__ == "__main__":
    secure_key = None

    app = QApplication([])

    check_c_libraries()

    if "--dev" in sys.argv:
        # data_dir is current directory
        data_dir = os.getcwd()
    
    else:
        data_dir = user_data_dir(appname="chatgpt-history", appauthor="maxieluan")
        os.makedirs(data_dir, exist_ok=True)

    config_file = "config.ini"
    config_path = os.path.join(data_dir, config_file)
    if not os.path.exists(config_path):
        config = configparser.ConfigParser()
        config["app"] = {"initialized": "False"}
        config["db_list"] = {}
        with open(config_path, "w") as f:
            config.write(f)

    db_manager = DbManager(data_dir)
    if db_manager.selected_db != None:
        db_path = db_manager.selected_db
    else:
        sys.exit(0)
    
    input_password_dialog = InputPasswordDialog()
    if input_password_dialog.password != None:
        password = input_password_dialog.password
        try :
            Database.initialize(db_path)
        except:
            pass
        database = Database.get_instance()
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
    
    database = Database.get_instance()
    cursor = database.get_cursor()
    groups = Group.get_all(cursor)
    
    # populate group in to data
    data = {}
    for group in groups:
        conversations = Conversation.get_by_group_id(group.id, cursor)
        data[f"{group.id}-{group.name}"] = [{"title": conversation.title, "id": conversation.id} for conversation in conversations]

    header_labels = ["Groups"]
    window = MainWindow(header_labels, data)
    window.show()
    app.exec()
