from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel


class TreeModel(QAbstractItemModel):
    def __init__(self, header_labels, data, parent=None):
        super().__init__(parent)
        self.header_labels = header_labels
        self.full_data = data
        self.filtered_data = data
        self.root_item = QStandardItem()
        self.refresh_filter()

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent()

        if parent_item == self.root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return parent_item.rowCount()

    def columnCount(self, parent=QModelIndex()):
        return len(self.header_labels)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.DisplayRole:
            return item.text()

        if role == Qt.UserRole or role == Qt.UserRole + 1:
            print (item)
            return item.data(role)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header_labels[section]

        return None

    def update_data(self, data):
        self.full_data = data
        self.filtered_data = data
        self.refresh_filter()

    def refresh_filter(self):
        self.root_item.removeRows(0, self.root_item.rowCount())

        for group_name, group_items in self.filtered_data.items():
            split = group_name.split("-")
            group_id = int(split[0])
            group_name = "-".join(split[1:])
            group_item = QStandardItem(group_name)
            group_item.setData(group_id, Qt.UserRole)
            self.root_item.appendRow(group_item)

            for item_name in group_items:
                child_item = QStandardItem(item_name["title"])
                child_item.setData(item_name["id"], Qt.UserRole)
                child_item.setData("con", Qt.UserRole + 1)
                group_item.appendRow(child_item)

        self.modelReset.emit()

    def conversation_added(self, conversation):
        group_id = conversation.group_id

        for i in range(self.root_item.rowCount()):
            group_item = self.root_item.child(i)
            if group_item.data(Qt.UserRole) == group_id:
                child_item = QStandardItem(conversation.title)
                child_item.setData(conversation.id, Qt.UserRole)
                child_item.setData("con", Qt.UserRole + 1)
                group_item.appendRow(child_item)
                self.dataChanged.emit(
                    self.index(i, 0),
                    self.index(i, self.columnCount() - 1),
                )
                return

        # Group not found, add new group and conversation
        group_item = QStandardItem(conversation.title)
        group_item.setData(group_id, Qt.UserRole)
        self.root_item.appendRow(group_item)
        self.dataChanged.emit(
            self.index(self.root_item.rowCount() - 1, 0),
            self.index(self.root_item.rowCount() - 1, self.columnCount() - 1),
        )

    def group_added(self, group):
        group_item = QStandardItem(group.name)
        group_item.setData(group.id, Qt.UserRole)
        self.root_item.appendRow(group_item)
        self.dataChanged.emit(
            self.index(self.root_item.rowCount() - 1, 0),
            self.index(self.root_item.rowCount() - 1, self.columnCount() - 1),
        )

    def set_filter_term(self, search_term):
        if search_term:
            self.filtered_data = {
                group_name: group_items
                for group_name, group_items in self.full_data.items()
                if any(search_term.lower() in item["title"].lower() for item in group_items)
            }
        else:
            self.filtered_data = self.full_data
        self.refresh_filter()
