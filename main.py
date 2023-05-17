from markdown_it import MarkdownIt
import pygments
from pygments.formatters import HtmlFormatter
import configparser
import os.path
from crytpo import EncryptionWrapper
from db import Database, Conversation, Tag, Group, Action
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel, QAction
from PySide6.QtWidgets import QApplication, QSplitter, QTreeView, QTextEdit, QMainWindow, QToolBar, QWidget, QVBoxLayout, QFileDialog, QDialog, QDialogButtonBox, QButtonGroup, QRadioButton, QScrollArea, QTabWidget, QPushButton, QHBoxLayout, QListWidget, QListWidgetItem, QLineEdit


class TreeModel(QStandardItemModel):
    def __init__(self, header_labels, data, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(header_labels)
        self.update_data(data)

    def update_data(self, data):
        parent_item = self.invisibleRootItem()
        # remove everything
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
                group_item.appendRow(child_item)
    
    def conversation_added(self, conversation):
        # loop through tree items for group with id == conversation.group_id
        for i in range(self.rowCount()):
            group_item = self.item(i)
            if int(group_item.data(Qt.UserRole)) == conversation.group_id:
                # add the conversation to the group
                child_item = QStandardItem(conversation.title)
                child_item.setData(conversation.id, Qt.UserRole)
                child_item.setData("con", Qt.UserRole + 1)
                group_item.appendRow(child_item)
                break
                

    def group_added(self, group):
        # add the group to the tree
        group_item = QStandardItem(group.name)
        group_item.setData(group.id, Qt.UserRole)
        self.appendRow(group_item)

def handle_item_clicked(index):
    tree_model = index.model()
    item = tree_model.itemFromIndex(index)
    if item.data(Qt.UserRole + 1) == "con":
        conversation_id = item.data(Qt.UserRole)
        database = Database()
        cursor = database.get_cursor()
        conversation = Conversation.get_by_id(conversation_id, cursor)
        password = "password"
        encryption_wrapper = EncryptionWrapper(password, conversation.salt)
        decrypted_content = encryption_wrapper.decrypt(
            conversation.data)

        md = MarkdownIt()
        formatter = HtmlFormatter(stylex="colorful")
        md.renderer.rules['code'] = lambda tokens, idx, options, env, slf: \
            '<div class="code-container">' \
            '<pre class="highlight"><code>' + pygments.highlight(tokens[idx]['content'], md.lexer, formatter) + '</code></pre><button class="copy-button" onclick="copyCode(this)">Copy</button></div>'

        html = md.render(decrypted_content)
        window.text_edit.setHtml(html)
        with open("output.html", "w", encoding="utf-8") as f:
            f.write(html)

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

        # Create the widgets
        self.tree_view = create_tree_view(self)
        self.text_edit = create_text_edit(self)
        self.toolbar = create_toolbar(self)

        self.left_widget = QWidget()
        self.leftcolumn = QVBoxLayout(self.left_widget)
        self.leftcolumn.setContentsMargins(0, 0, 0, 0)

        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Filter")
        self.leftcolumn.addWidget(filter_input)

        toolbar = QToolBar()
        toolbar.setMinimumHeight(30)
        add_group_action = QAction("Add Group", self)
        add_group_action.triggered.connect(self.add_group)
        toolbar.addAction(add_group_action)
        self.leftcolumn.addWidget(toolbar)
        
        self.leftcolumn.addWidget(self.tree_view)
        # Create a splitter to handle resizing
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self.left_widget)
        splitter.addWidget(self.text_edit)
        splitter.setChildrenCollapsible(False)

        # Set up the tree model
        self.tree_model = TreeModel(header_labels, data)

        # Set the model on the tree view
        self.tree_view.setModel(self.tree_model)
        self.tree_view.clicked.connect(handle_item_clicked)

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
                    password = "password"
                    encryption_wrapper = EncryptionWrapper(password, salt)
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
                        password, retrieved_conversation.salt)
                    decrypted_content = new_encryption_wrapper.decrypt(
                        retrieved_conversation.data)


                    md = MarkdownIt()
                    formatter = HtmlFormatter(stylex="colorful")
                    md.renderer.rules['code'] = lambda tokens, idx, options, env, slf: \
                        '<div class="code-container">' \
                        '<pre class="highlight"><code>' + pygments.highlight(tokens[idx]['content'], md.lexer, formatter) + '</code></pre><button class="copy-button" onclick="copyCode(this)">Copy</button></div>'

                    html = md.render(decrypted_content)
                    self.text_edit.setHtml(html)                   


if __name__ == "__main__":
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
        database = Database("db.sqlite")
        database.initialize()

        config["app"]["initialized"] = "True"
        with open(config_file, "w") as f:
            config.write(f)
    
    database = Database("db.sqlite")
    cursor = database.get_cursor()
    groups = Group.get_all(cursor)
    
    # populate group in to data
    data = {}
    for group in groups:
        conversations = Conversation.get_by_group_id(group.id, cursor)
        data[f"{group.id}-{group.name}"] = [{"title": conversation.title, "id": conversation.id} for conversation in conversations]

    header_labels = ["Groups"]
    app = QApplication([])
    window = MainWindow(header_labels, data)
    window.show()
    app.exec()
