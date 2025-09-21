import sys
from typing import List

from PySide6.QtCore import Qt, QModelIndex, QMimeData, QPersistentModelIndex
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QApplication, QMainWindow, QTreeView


class ItemModel(QStandardItemModel):
    def __init__(self, row_count: int, length: int) -> None:
        super().__init__(row_count, length)

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        col: int,
        parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        # Only allow drops at the top level (no parent)
        if parent.isValid():
            return False
        return super().dropMimeData(data, action, row, 0, parent)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        tree = QTreeView()
        model = ItemModel(0, 3)

        tree.setModel(model)

        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        tree.setDragDropOverwriteMode(False)
        # tree.setItemsExpandable(True)

        self.setCentralWidget(tree)

        items: List[QStandardItem] = []

        for i in range(6):
            item = QStandardItem(str(i))
            item.setDropEnabled(False)
            items.append(item)

        model.appendRow(items[0:3])
        model.appendRow(items[3:6])


if __name__ == "__main__":
    app = QApplication([])

    widget = MainWindow()
    widget.show()

    sys.exit(app.exec())
