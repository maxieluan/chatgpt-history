from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QWidget, QListWidget, QListWidgetItem, QPushButton, QDialogButtonBox, QLineEdit
from db import Database, Tag, Conversation
from PySide6.QtCore import Qt

class AddTagsDialog(QDialog):
    def __init__(self, window):        
        super().__init__()
        self.window = window
        self.setWindowTitle("Add Tags")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter")
        self.filter_input.textChanged.connect(self.filter_tags)
        self.layout.addWidget(self.filter_input)
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.MultiSelection)
        database = Database.get_instance()
        cursor = database.get_cursor()
        tags = Tag.get_all(cursor)
        acitve_tag_ids = [tag.id for tag in self.window.active_conversation.tags]
        for tag in tags:
            item = QListWidgetItem(tag.name)
            item.setData(Qt.UserRole, tag.id)
            self.tag_list.addItem(item)
        
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            if item.data(Qt.UserRole) in acitve_tag_ids:
                item.setSelected(True)

        self.layout.addWidget(self.tag_list)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.confirm_change)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

    def confirm_change(self):
        convesation = self.window.active_conversation
        if convesation == None:
            return

        convesation.tags = []
        tag_ids = []
        for item in self.tag_list.selectedItems():
            tag_name = item.text()
            tag_id = item.data(Qt.UserRole)
            tag = Tag(tag_id, tag_name)
            convesation.tags.append(tag)
            tag_ids.append(tag.id)
        database = Database.get_instance()
        cursor = database.get_cursor()
        Conversation.change_tag(convesation.id, tag_ids, cursor)
        database.conn.commit()
        self.window.update_active_conversation(convesation)
        self.window.tree_model.tag_changed(convesation)
        self.accept()
    
    def filter_tags(self):
        filter_text = self.filter_input.text()
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            if filter_text.lower() in item.text().lower():
                item.setHidden(False)
            else :
                item.setHidden(True)

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

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter")
        self.filter_input.textChanged.connect(self.filter_tags)
        self.left_column_layout.addWidget(self.filter_input)

        self.right_column = QWidget()
        self.right_column_layout = QVBoxLayout(self.right_column)
        self.right_column_layout.setContentsMargins(0, 0, 0, 0)
        self.right_column_layout.setSpacing(0)
        self.top_widget_layout.addWidget(self.right_column)
        
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.MultiSelection)

        database = Database.get_instance()
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

    def filter_tags(self):
        filter_text = self.filter_input.text()
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            if filter_text.lower() in item.text().lower():
                item.setHidden(False)
            else :
                item.setHidden(True)

    def add_tag(self):
        dialog = AddTagDialog()
        if dialog.tag != None:
            database = Database.get_instance()
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
            database = Database.get_instance()
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
        database = Database.get_instance()
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