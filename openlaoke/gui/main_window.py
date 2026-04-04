"""Main window for OpenLaoKe GUI."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QToolBar,
    QLabel, QMessageBox, QFileDialog, QApplication,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QUrl, QEvent
from PySide6.QtGui import QAction, QKeySequence, QFont

if TYPE_CHECKING:
    pass


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, app_state=None, config=None):
        super().__init__()
        self.app_state = app_state
        self.config = config
        self._sidebar = None
        self._chat = None
        self._files = None
        self._status = None
        self._cost = None
        self._setup()
    
    def _setup(self):
        """Setup the main window."""
        self.setWindowTitle("OpenLaoKe - AI Coding Assistant")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        from openlaoke.gui.components.sidebar import SidebarWidget
        self._sidebar = SidebarWidget(self.config)
        self._sidebar.setMaximumWidth(250)
        splitter.addWidget(self._sidebar)
        
        from openlaoke.gui.components.chat_widget import ChatWidget
        self._chat = ChatWidget()
        splitter.addWidget(self._chat)
        
        from openlaoke.gui.components.file_tree import FileTreeWidget
        self._files = FileTreeWidget()
        self._files.setMaximumWidth(280)
        splitter.addWidget(self._files)
        
        splitter.setSizes([220, 700, 280])
        
        status = QStatusBar()
        self.setStatusBar(status)
        self._status = QLabel("Ready")
        status.addWidget(self._status)
        self._cost = QLabel("Cost: $0.0000")
        status.addPermanentWidget(self._cost)
        
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New Session", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._new_session)
        file_menu.addAction(new_action)
        
        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        if self.config:
            prov = QLabel(f"Provider: {self.config.providers.active_provider}")
            prov.setStyleSheet("padding: 0 10px; color: #aaa;")
            toolbar.addWidget(prov)
            
            model = QLabel(f"Model: {self.config.providers.get_active_model()}")
            model.setStyleSheet("padding: 0 10px; color: #aaa;")
            toolbar.addWidget(model)
        
        self._chat.message_sent.connect(self._on_message)
        self._files.file_open_requested.connect(self._on_file_open)
        
        if self.app_state and self.app_state.get_cwd():
            self._files.set_root_path(self.app_state.get_cwd())
    
    def _new_session(self):
        """Create new session."""
        self._chat.clear_messages()
        self._status.setText("New session")
    
    def _open_project(self):
        """Open project directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Open Project", os.path.expanduser("~")
        )
        if directory:
            self._files.set_root_path(directory)
            if self.app_state:
                self.app_state.set_cwd(directory)
    
    def _on_message(self, text: str):
        """Handle user message."""
        self._status.setText("Processing...")
        # TODO: Implement API call
    
    def _on_file_open(self, path: str):
        """Handle file open."""
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))