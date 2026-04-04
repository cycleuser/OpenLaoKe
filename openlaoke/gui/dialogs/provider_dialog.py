"""Provider configuration dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QFormLayout,
    QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.utils.config import AppConfig


class ProviderConfigDialog(QDialog):
    """Dialog for configuring LLM providers."""
    
    def __init__(self, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self._current_provider: str | None = None
        self._setup_ui()
        self._load_providers()
    
    def _setup_ui(self):
        self.setWindowTitle("Configure Providers")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        layout = QHBoxLayout(self)
        
        left_panel = QVBoxLayout()
        
        label = QLabel("Providers")
        label.setStyleSheet("font-weight: bold; color: #888;")
        left_panel.addWidget(label)
        
        self._provider_list = QListWidget()
        self._provider_list.currentItemChanged.connect(self._on_provider_selected)
        left_panel.addWidget(self._provider_list)
        
        layout.addLayout(left_panel, stretch=1)
        
        right_panel = QVBoxLayout()
        
        self._config_group = QGroupBox("Provider Configuration")
        form_layout = QFormLayout(self._config_group)
        
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.Password)
        self._api_key_input.setPlaceholderText("Enter API key...")
        form_layout.addRow("API Key:", self._api_key_input)
        
        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("https://api.example.com/v1")
        form_layout.addRow("Base URL:", self._base_url_input)
        
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        form_layout.addRow("Model:", self._model_combo)
        
        right_panel.addWidget(self._config_group)
        
        button_layout = QHBoxLayout()
        
        self._set_active_btn = QPushButton("Set as Active")
        self._set_active_btn.clicked.connect(self._set_active_provider)
        button_layout.addWidget(self._set_active_btn)
        
        button_layout.addStretch()
        
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save_current_provider)
        button_layout.addWidget(self._save_btn)
        
        right_panel.addLayout(button_layout)
        right_panel.addStretch()
        
        layout.addLayout(right_panel, stretch=2)
        
        bottom_buttons = QHBoxLayout()
        bottom_buttons.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom_buttons.addWidget(cancel_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        bottom_buttons.addWidget(ok_btn)
        
        parent_layout = QVBoxLayout()
        parent_layout.addLayout(layout)
        parent_layout.addLayout(bottom_buttons)
        
        self.setLayout(parent_layout)
    
    def _load_providers(self):
        if not self.config:
            return
        
        for name, provider in self.config.providers.providers.items():
            item = QListWidgetItem(name)
            status = "✓" if provider.is_configured() else "○"
            if name == self.config.providers.active_provider:
                status = "★"
            item.setText(f"{status} {name}")
            item.setData(Qt.UserRole, name)
            self._provider_list.addItem(item)
    
    def _on_provider_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not current:
            return
        
        provider_name = current.data(Qt.UserRole)
        self._current_provider = provider_name
        
        if not self.config or provider_name not in self.config.providers.providers:
            return
        
        provider = self.config.providers.providers[provider_name]
        
        self._api_key_input.setText(provider.api_key)
        self._base_url_input.setText(provider.base_url)
        
        self._model_combo.clear()
        for model in provider.models:
            self._model_combo.addItem(model)
        self._model_combo.setCurrentText(provider.default_model)
    
    def _save_current_provider(self):
        if not self.config or not self._current_provider:
            return
        
        provider = self.config.providers.providers.get(self._current_provider)
        if not provider:
            return
        
        provider.api_key = self._api_key_input.text()
        provider.base_url = self._base_url_input.text()
        provider.default_model = self._model_combo.currentText()
    
    def _set_active_provider(self):
        if not self.config or not self._current_provider:
            return
        
        self._save_current_provider()
        self.config.providers.active_provider = self._current_provider
        
        QMessageBox.information(
            self,
            "Provider Changed",
            f"Active provider set to: {self._current_provider}"
        )