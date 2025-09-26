import sys
from typing import List, Optional, Union

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractProxyModel,
    QMimeData,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QMainWindow,
    QTreeView,
    QWidget,
)


class ColumnFilterProxy(QSortFilterProxyModel):
    def __init__(self, visible_columns: set[int], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.set_visible_columns(visible_columns)

    def set_visible_columns(self, cols: set[int]):
        self._visible_columns = cols
        self.invalidateFilter()

    def filterAcceptsColumn(
        self,
        source_column: int,
        source_parent: Union[QModelIndex, QPersistentModelIndex],
    ) -> bool:
        return source_column in self._visible_columns

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        col: int,
        parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        # Map proxy parent to source parent
        src_parent = self.mapToSource(parent)

        # Map proxy column to source column
        if col != -1:
            src_col = self.mapToSource(self.index(0, col)).column()
        else:
            src_col = -1

        return self.sourceModel().dropMimeData(data, action, row, src_col, src_parent)


class DragDropReorderProxy(QAbstractProxyModel):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._row_order: list[int] = []

    def setSourceModel(self, source_model: QAbstractItemModel) -> None:
        super().setSourceModel(source_model)
        # Connect signals so we update when the source changes
        source_model.modelReset.connect(self._reset_mapping)
        source_model.rowsInserted.connect(self._reset_mapping)
        source_model.rowsRemoved.connect(self._reset_mapping)
        self._reset_mapping()

    def _reset_mapping(self):
        # if self.sourceModel() is None:
        #     return
        self.beginResetModel()
        self._row_order = list(range(self.sourceModel().rowCount()))
        self.endResetModel()

    # Required abstract methods
    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        # if parent.isValid() or self.sourceModel() is None:
        #     return 0
        return len(self._row_order)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        # if self.sourceModel() is None:
        #     return 0
        return self.sourceModel().columnCount(parent)

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> QModelIndex:
        if parent.isValid():
            return QModelIndex()
        if 0 <= row < self.rowCount() and 0 <= column < self.columnCount():
            return self.createIndex(row, column)
        return QModelIndex()

    def parent(self, index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return QModelIndex()

    # Mapping
    def mapToSource(
        self, proxy_index: QModelIndex | QPersistentModelIndex
    ) -> QModelIndex:
        if not proxy_index.isValid():
            return QModelIndex()
        src_row = self._row_order[proxy_index.row()]
        return self.sourceModel().index(src_row, proxy_index.column())

    def mapFromSource(
        self, source_index: QModelIndex | QPersistentModelIndex
    ) -> QModelIndex:
        if not source_index.isValid():
            return QModelIndex()
        try:
            row = self._row_order.index(source_index.row())
        except ValueError:
            return QModelIndex()
        return self.index(row, source_index.column())

    # Drag/drop handling
    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        default = (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        return default | Qt.ItemFlag.ItemIsDropEnabled

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if action != Qt.DropAction.MoveAction:
            return False

        if row == -1 and parent.isValid():
            row = parent.row()
        elif row == -1:
            row = self.rowCount()

        if not hasattr(self, "_current_drag_row"):
            return False

        self.beginResetModel()
        sel = self._row_order.pop(self._current_drag_row)
        self._row_order.insert(min(row, len(self._row_order)), sel)
        self.endResetModel()

        return True

    def mimeTypes(self) -> List[str]:
        return ["application/x-qabstractitemmodeldatalist"]

    def mimeData(self, indexes: List[QModelIndex]) -> QMimeData:
        # Track the dragged row
        if indexes:
            self._current_drag_row = indexes[0].row()
        return super().mimeData(indexes)


class ItemModel(QStandardItemModel):
    def __init__(self, row_count: int, length: int) -> None:
        super().__init__(row_count, length)

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        # Only allow drops at the top level (no parent)
        # if parent.isValid():
        #     return False
        # return super().dropMimeData(data, action, row, 0, parent)

        if action == Qt.DropAction.IgnoreAction:
            return False
        if not data.hasFormat("application/x-qstandarditemmodeldatalist"):
            return False

        if row == -1:
            row = self.rowCount()

        # Decode into a temp model
        temp_model = QStandardItemModel()
        temp_model.dropMimeData(data, Qt.DropAction.CopyAction, 0, 0, QModelIndex())

        # Collect rows
        copied_rows: List[List[QStandardItem]] = []
        for r in range(temp_model.rowCount()):
            items: List[QStandardItem] = []
            for c in range(temp_model.columnCount()):
                src_item = temp_model.item(r, c)
                if src_item:
                    item = src_item.clone()  # important: clone to avoid shared pointers
                else:
                    item = QStandardItem()
                items.append(item)
            copied_rows.append(items)

        # Insert at target
        for i, items in enumerate(copied_rows):
            self.insertRow(row + i, items)

        return True


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        tree = QTreeView()
        model = ItemModel(0, 3)

        # Use ColumnFilterProxy to filter visible columns
        visible_columns = {1, 2}  # Example: show only columns 0 and 2

        col_proxy = ColumnFilterProxy(visible_columns)
        col_proxy.setSourceModel(model)

        reorder_proxy = DragDropReorderProxy()
        reorder_proxy.setSourceModel(col_proxy)

        tree.setModel(reorder_proxy)

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
            item.setEditable(False)
            items.append(item)

        model.appendRow(items[0:3])
        model.appendRow(items[3:6])


if __name__ == "__main__":
    app = QApplication([])

    widget = MainWindow()
    widget.show()
    widget.resize(800, 300)

    sys.exit(app.exec())
