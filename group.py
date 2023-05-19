from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QRadioButton, QDialogButtonBox, QButtonGroup, QListWidget, QLineEdit, QListWidgetItem
from db import Database, Group, Conversation, Tag
from PySide6.QtCore import Qt

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

class ChangeGroupDialog(QDialog):
    def __init__(self, window):
        super().__init__()
        self.window = window

        self.setWindowTitle("Change Group")
        self.setMinimumSize(300, 200)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.group_name_filter = QLineEdit()
        self.group_name_filter.setPlaceholderText("Filter")
        self.layout.addWidget(self.group_name_filter)
        self.group_name_filter.textChanged.connect(self.filter_group_list)

        self.group_list = QListWidget()
        self.layout.addWidget(self.group_list)

        database = Database()
        cursor = database.get_cursor()
        groups = Group.get_all(cursor)
        for group in groups:
            item = QListWidgetItem(group.name)
            item.setData(Qt.UserRole, group.id)
            self.group_list.addItem(item)
        
        self.group_list.setSelectionMode(QListWidget.SingleSelection)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.change_confirm)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

    def filter_group_list(self):
        filter_text = self.group_name_filter.text()
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            if filter_text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def change_confirm(self):
        if len(self.group_list.selectedItems()) == 0:
            return
        
        conversation = self.window.active_conversation
        if conversation == None:
            return
        
        item = self.group_list.selectedItems()[0]
        group_id = item.data(Qt.UserRole)
        database = Database()
        cursor = database.get_cursor()
        Conversation.change_group(conversation.id, group_id, cursor)
        database.conn.commit()
        old_group_id = conversation.group_id
        conversation = Conversation.get_by_id(conversation.id, cursor)
        tags = Tag.get_by_conversation_id(conversation.id, cursor)
        conversation.tags = tags
        new_group_id = conversation.group_id
        self.window.update_active_conversation(conversation)
        self.window.tree_model.group_changed(old_group_id, new_group_id, self.window.active_conversation)
        self.accept()

    def deleteLater(self) -> None:
        return super().deleteLater()