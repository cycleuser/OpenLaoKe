"""Settings dialog for OpenLaoKe configuration."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QPushButton,
    QTabWidget,
    QWidget,
    QFormLayout,
    QGroupBox,
    QComboBox,
)
from PySide6.QtCore import Qt

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.utils.config import AppConfig


class SettingsDialog(QDialog):
    """Settings configuration dialog."""
    
    def __init__(self, config: AppConfig | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "General")
        
        permissions_tab = self._create_permissions_tab()
        tabs.addTab(permissions_tab, "Permissions")
        
        display_tab = self._create_display_tab()
        tabs.addTab(display_tab, "Display")
        
        buttons = QHBoxLayout()
        buttons.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_settings)
        save_btn.setDefault(True)
        buttons.addWidget(save_btn)
        
        layout.addLayout(buttons)
    
    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(256, 32768)
        self._max_tokens.setValue(8192)
        layout.addRow("Max Tokens:", self._max_tokens)
        
        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.setValue(1.0)
        layout.addRow("Temperature:", self._temperature)
        
        self._thinking_budget = QSpinBox()
        self._thinking_budget.setRange(0, 10000)
        self._thinking_budget.setValue(0)
        layout.addRow("Thinking Budget:", self._thinking_budget)
        
        return widget
    
    def _create_permissions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        auto_approve_group = QGroupBox("Auto-Approve Settings")
        approve_layout = QFormLayout(auto_approve_group)
        
        self._auto_approve_all = QCheckBox()
        self._auto_approve_all.setChecked(True)
        self._auto_approve_all.setText("Enable Auto-Approve All Tools")
        approve_layout.addRow(self._auto_approve_all)
        
        layout.addWidget(auto_approve_group)
        
        self._permission_mode = QComboBox()
        self._permission_mode.addItems(["default", "auto", "bypass"])
        
        mode_group = QGroupBox("Permission Mode")
        mode_layout = QFormLayout(mode_group)
        mode_layout.addRow("Mode:", self._permission_mode)
        layout.addWidget(mode_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_display_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self._theme = QComboBox()
        self._theme.addItems(["dark", "light"])
        layout.addRow("Theme:", self._theme)
        
        self._show_tokens = QCheckBox()
        self._show_tokens.setChecked(True)
        layout.addRow("Show Token Budget:", self._show_tokens)
        
        self._show_cost = QCheckBox()
        self._show_cost.setChecked(True)
        layout.addRow("Show Cost:", self._show_cost)
        
        self._max_lines = QSpinBox()
        self._max_lines.setRange(100, 2000)
        self._max_lines.setValue(500)
        layout.addRow("Max Output Lines:", self._max_lines)
        
        return widget
    
    def _load_settings(self):
        if not self.config:
            return
        
        self._max_tokens.setValue(self.config.max_tokens)
        self._temperature.setValue(self.config.temperature)
        self._thinking_budget.setValue(self.config.thinking_budget)
        self._auto_approve_all.setChecked(self.config.auto_approve_all)
        self._permission_mode.setCurrentText(self.config.permission_mode)
        self._theme.setCurrentText(self.config.theme)
        self._show_tokens.setChecked(self.config.show_token_budget)
        self._show_cost.setChecked(self.config.show_cost)
        self._max_lines.setValue(self.config.max_output_lines)
    
    def _save_settings(self):
        if not self.config:
            self.accept()
            return
        
        self.config.max_tokens = self._max_tokens.value()
        self.config.temperature = self._temperature.value()
        self.config.thinking_budget = self._thinking_budget.value()
        self.config.auto_approve_all = self._auto_approve_all.isChecked()
        self.config.permission_mode = self._permission_mode.currentText()
        self.config.theme = self._theme.currentText()
        self.config.show_token_budget = self._show_tokens.isChecked()
        self.config.show_cost = self._show_cost.isChecked()
        self.config.max_output_lines = self._max_lines.value()
        
        self.accept()