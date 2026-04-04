"""Sidebar widget for navigation."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon


class SidebarWidget(QWidget):
    """Sidebar for project and session navigation."""
    
    project_selected = Signal(str)
    session_selected = Signal(str)
    new_project_clicked = Signal()
    
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("background-color: #1a1a24;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QWidget()
        header.setStyleSheet("border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 8, 8)
        
        label = QLabel("OpenLaoKe")
        label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2a82dd;")
        header_layout.addWidget(label)
        
        layout.addWidget(header)
        
        projects_section = QWidget()
        projects_layout = QVBoxLayout(projects_section)
        projects_layout.setContentsMargins(8, 8, 8, 8)
        
        projects_label = QLabel("Recent Projects")
        projects_label.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        projects_layout.addWidget(projects_label)
        
        self._projects_list = QListWidget()
        self._projects_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: #ddd;
            }
            QListWidget::item:selected {
                background-color: #252532;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #202028;
                border-radius: 4px;
            }
        """)
        self._projects_list.itemClicked.connect(self._on_project_clicked)
        projects_layout.addWidget(self._projects_list)
        
        layout.addWidget(projects_section)
        
        sessions_section = QWidget()
        sessions_layout = QVBoxLayout(sessions_section)
        sessions_layout.setContentsMargins(8, 8, 8, 8)
        
        sessions_label = QLabel("Sessions")
        sessions_label.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        sessions_layout.addWidget(sessions_label)
        
        self._sessions_list = QListWidget()
        self._sessions_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: #ddd;
            }
            QListWidget::item:selected {
                background-color: #252532;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #202028;
                border-radius: 4px;
            }
        """)
        self._sessions_list.itemClicked.connect(self._on_session_clicked)
        sessions_layout.addWidget(self._sessions_list)
        
        layout.addWidget(sessions_section)
        
        layout.addStretch()
        
        self._add_sample_data()
    
    def _add_sample_data(self):
        self._projects_list.addItem("OpenLaoKe")
        self._projects_list.addItem("opencode")
        
        self._sessions_list.addItem("Session 1")
        self._sessions_list.addItem("Session 2")
    
    def _on_project_clicked(self, item: QListWidgetItem):
        self.project_selected.emit(item.text())
    
    def _on_session_clicked(self, item: QListWidgetItem):
        self.session_selected.emit(item.text())
    
    def add_project(self, name: str, path: str):
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, path)
        self._projects_list.insertItem(0, item)
    
    def add_session(self, session_id: str, name: str = ""):
        item = QListWidgetItem(name or session_id)
        item.setData(Qt.UserRole, session_id)
        self._sessions_list.insertItem(0, item)