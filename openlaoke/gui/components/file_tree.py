"""File tree widget for browsing project files."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal, QDir, QModelIndex


class FileTreeWidget(QWidget):
    """File tree browser widget."""
    
    file_selected = Signal(str)
    file_open_requested = Signal(str)
    directory_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path: str | None = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QWidget()
        header.setStyleSheet("background-color: #1a1a24; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        
        label = QLabel("Files")
        label.setStyleSheet("font-weight: bold; color: #888;")
        header_layout.addWidget(label)
        
        layout.addWidget(header)
        
        self._model = QFileSystemModel()
        self._model.setRootPath(QDir.rootPath())
        self._model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs)
        
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setHeaderHidden(True)
        self._tree.setColumnHidden(1, True)
        self._tree.setColumnHidden(2, True)
        self._tree.setColumnHidden(3, True)
        self._tree.setStyleSheet("""
            QTreeView {
                background-color: #12121a;
                color: #ddd;
                border: none;
            }
            QTreeView::item:selected {
                background-color: #2a82dd;
            }
            QTreeView::item:hover {
                background-color: #252532;
            }
        """)
        self._tree.clicked.connect(self._on_item_clicked)
        self._tree.doubleClicked.connect(self._on_item_double_clicked)
        
        layout.addWidget(self._tree)
    
    def set_root_path(self, path: str):
        self._root_path = path
        index = self._model.index(path)
        self._tree.setRootIndex(index)
        self._tree.expand(index)
        self.directory_changed.emit(path)
    
    def _on_item_clicked(self, index: QModelIndex):
        path = self._model.filePath(index)
        if os.path.isfile(path):
            self.file_selected.emit(path)
    
    def _on_item_double_clicked(self, index: QModelIndex):
        path = self._model.filePath(index)
        if os.path.isfile(path):
            self.file_open_requested.emit(path)