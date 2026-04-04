"""Code viewer widget for displaying and editing code."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTabBar,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QKeySequence


class CodeViewerWidget(QWidget):
    """Widget for viewing and editing code files."""
    
    file_saved = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file: str | None = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QWidget()
        header.setStyleSheet("background-color: #1a1a24; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 4)
        
        self._file_label = QLabel("No file open")
        self._file_label.setStyleSheet("color: #888;")
        header_layout.addWidget(self._file_label)
        
        header_layout.addStretch()
        
        self._save_button = QPushButton("Save")
        self._save_button.setShortcut(QKeySequence.Save)
        self._save_button.clicked.connect(self._save_file)
        self._save_button.setVisible(False)
        header_layout.addWidget(self._save_button)
        
        layout.addWidget(header)
        
        from PySide6.QtWidgets import QPlainTextEdit
        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("SF Mono", 11))
        self._editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #12121a;
                color: #ddd;
                border: none;
                padding: 8px;
            }
        """)
        self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(self._editor)
    
    def load_file(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._editor.setPlainText(content)
            self._current_file = path
            self._file_label.setText(path)
            self._save_button.setVisible(True)
        except Exception as e:
            self._editor.setPlainText(f"Error loading file: {e}")
            self._file_label.setText(f"Error: {path}")
    
    def set_code(self, code: str, language: str = ""):
        self._editor.setPlainText(code)
        self._file_label.setText(language or "Code")
        self._current_file = None
        self._save_button.setVisible(False)
    
    def _save_file(self):
        if self._current_file:
            try:
                with open(self._current_file, 'w', encoding='utf-8') as f:
                    f.write(self._editor.toPlainText())
                self.file_saved.emit(self._current_file, self._editor.toPlainText())
            except Exception as e:
                print(f"Error saving file: {e}")