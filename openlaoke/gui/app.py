"""Main application class for OpenLaoKe GUI."""

from __future__ import annotations

import sys


class OpenLaoKeApp:
    """Main application wrapper for OpenLaoKe GUI."""
    
    def __init__(self, app_state=None, config=None):
        self.app_state = app_state
        self.config = config
        self._app = None
        self._window = None
    
    def run(self) -> int:
        """Run the GUI application."""
        # Import Qt only when needed
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QPalette, QColor
        
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("OpenLaoKe")
        self._app.setApplicationVersion("0.1.2")
        self._app.setStyle("Fusion")
        
        # Setup dark theme
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
        palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
        palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
        palette.setColor(QPalette.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
        palette.setColor(QPalette.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        self._app.setPalette(palette)
        
        # Setup font
        font = QFont("Menlo", 11)
        if not font.exactMatch():
            font = QFont("Monaco", 11)
        if not font.exactMatch():
            font = QFont("Courier New", 11)
        font.setStyleHint(QFont.Monospace)
        self._app.setFont(font)
        
        # Import and create main window
        from openlaoke.gui.main_window import MainWindow
        self._window = MainWindow(app_state=self.app_state, config=self.config)
        self._window.show()
        
        return self._app.exec()
    
    def quit(self):
        """Quit the application."""
        if self._app:
            self._app.quit()