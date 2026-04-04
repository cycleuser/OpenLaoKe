"""Chat widget for displaying messages and input."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTextEdit, QPushButton, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QEvent


class MessageBubble(QFrame):
    """A single message bubble in the chat."""
    
    clicked = Signal()
    
    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self._role = role
        self._content = content
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        role_label = QLabel(self._role.capitalize())
        role_label.setStyleSheet("font-weight: bold; color: #888; font-size: 11px;")
        layout.addWidget(role_label)
        
        self._content_label = QLabel(self._content)
        self._content_label.setWordWrap(True)
        self._content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._content_label)
        
        if self._role == "user":
            self.setStyleSheet("""
                QFrame {
                    background-color: #2a2a3e;
                    border-radius: 8px;
                    margin: 4px 60px 4px 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e1e2e;
                    border-radius: 8px;
                    margin: 4px 8px 4px 60px;
                }
            """)
    
    def content(self) -> str:
        return self._content
    
    def set_content(self, content: str):
        self._content = content
        self._content_label.setText(content)


class ChatWidget(QWidget):
    """Chat widget for displaying messages and input."""
    
    message_sent = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages = []
        self._content_label = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #12121a;
            }
        """)
        
        self._container = QWidget()
        self._msg_layout = QVBoxLayout(self._container)
        self._msg_layout.setContentsMargins(8, 8, 8, 8)
        self._msg_layout.setSpacing(8)
        self._msg_layout.addStretch()
        
        scroll.setWidget(self._container)
        layout.addWidget(scroll, stretch=1)
        
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a24;
                border-top: 1px solid #333;
            }
        """)
        
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)
        
        self._input = QTextEdit()
        self._input.setPlaceholderText("Type a message... (Shift+Enter for new line)")
        self._input.setMaximumHeight(120)
        self._input.setStyleSheet("""
            QTextEdit {
                background-color: #252532;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 8px;
                color: #ddd;
            }
        """)
        self._input.installEventFilter(self)
        input_layout.addWidget(self._input, stretch=1)
        
        send_btn = QPushButton("Send")
        send_btn.setFixedWidth(80)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a82dd;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a92ed;
            }
        """)
        send_btn.clicked.connect(self._send)
        input_layout.addWidget(send_btn)
        
        layout.addWidget(input_frame)
    
    def eventFilter(self, obj, event):
        if obj == self._input:
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
                    self._send()
                    return True
        return super().eventFilter(obj, event)
    
    def _send(self):
        text = self._input.toPlainText().strip()
        if text:
            self.message_sent.emit(text)
            self._input.clear()
    
    def add_user_message(self, content: str):
        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background-color: #2a2a3e;
                border-radius: 8px;
                margin: 4px 60px 4px 8px;
            }
        """)
        
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(12, 8, 12, 8)
        
        role = QLabel("You")
        role.setStyleSheet("font-weight: bold; color: #888; font-size: 11px;")
        layout.addWidget(role)
        
        msg = QLabel(content)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(msg)
        
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        self._messages.append({"role": "user", "content": content})
    
    def add_assistant_message(self, content: str = ""):
        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border-radius: 8px;
                margin: 4px 8px 4px 60px;
            }
        """)
        
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(12, 8, 12, 8)
        
        role = QLabel("Assistant")
        role.setStyleSheet("font-weight: bold; color: #888; font-size: 11px;")
        layout.addWidget(role)
        
        self._content_label = QLabel(content)
        self._content_label.setWordWrap(True)
        self._content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._content_label)
        
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        self._messages.append({"role": "assistant", "content": content})
    
    def append_assistant_message(self, content: str):
        if self._content_label is not None and self._messages:
            current = self._messages[-1].get("content", "")
            self._messages[-1]["content"] = current + content
            self._content_label.setText(current + content)
        else:
            self.add_assistant_message(content)
    
    def add_tool_message(self, tool_name: str, tool_input: dict, result: str = ""):
        import json
        
        content = f"🔧 {tool_name}\n```json\n{json.dumps(tool_input, indent=2)}\n```"
        
        bubble = QFrame()
        bubble.setStyleSheet("""
            QFrame {
                background-color: #1a2820;
                border: 1px solid #2a4a3a;
                border-radius: 8px;
                margin: 4px 20px;
            }
        """)
        
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(12, 8, 12, 8)
        
        msg = QLabel(content)
        msg.setWordWrap(True)
        layout.addWidget(msg)
        
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        self._messages.append({"role": "tool", "name": tool_name, "input": tool_input})
    
    def clear_messages(self):
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._messages.clear()
    
    def get_messages(self):
        return self._messages.copy()