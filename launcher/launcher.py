"""
AuraNexus Launcher - Main entry point
Handles startup, updates, and service management
"""

import sys
import os
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QProgressBar, QPushButton, QMessageBox, QSystemTrayIcon, QMenu
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QPixmap, QAction

# Handle imports for both script and PyInstaller frozen mode
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    from launcher.updater import UpdateChecker
    from launcher.docker_manager import DockerManager
    from launcher.config import LauncherConfig
else:
    # Running as script
    launcher_dir = Path(__file__).parent
    sys.path.insert(0, str(launcher_dir))
    from updater import UpdateChecker
    from docker_manager import DockerManager
    from config import LauncherConfig


class LauncherWindow(QMainWindow):
    """Main launcher window with splash screen and progress"""
    
    def __init__(self):
        super().__init__()
        self.config = LauncherConfig()
        self.docker_manager = DockerManager()
        self.tray_icon = None
        self.services_started = False  # Track if services are running
        
        self.setup_ui()
        
        # Start update check after UI is shown
        QTimer.singleShot(500, self.start_update_check)
    
    def setup_ui(self):
        """Setup the launcher window UI"""
        self.setWindowTitle("AuraNexus Launcher")
        self.setFixedSize(500, 350)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
        # Main widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        # Logo/Title
        title = QLabel("🌟 AuraNexus")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #4A90E2;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Status message
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4A90E2;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Details label
        self.details_label = QLabel("")
        self.details_label.setAlignment(Qt.AlignCenter)
        self.details_label.setStyleSheet("font-size: 11px; color: #999;")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        
        # Buttons (initially hidden)
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        self.launch_button = QPushButton("Open AuraNexus")
        self.launch_button.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        self.launch_button.clicked.connect(self.open_web_ui)
        self.launch_button.hide()
        button_layout.addWidget(self.launch_button)
        
        self.retry_button = QPushButton("Retry")
        self.retry_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.retry_button.clicked.connect(self.start_update_check)
        self.retry_button.hide()
        button_layout.addWidget(self.retry_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
    
    def start_update_check(self):
        """Start the update checking process"""
        self.retry_button.hide()
        self.launch_button.hide()
        self.progress_bar.setValue(0)
        
        # Create and start update checker thread
        self.update_checker = UpdateChecker(self.config, self.docker_manager)
        self.update_checker.progress.connect(self.update_progress)
        self.update_checker.finished.connect(self.on_update_finished)
        self.update_checker.error.connect(self.on_update_error)
        self.update_checker.start()
    
    def update_progress(self, message: str, percentage: int, details: str = ""):
        """Update progress UI"""
        self.status_label.setText(message)
        self.progress_bar.setValue(percentage)
        self.details_label.setText(details)
    
    def on_update_finished(self, success: bool):
        """Handle update check completion"""
        if success:
            self.services_started = True  # Mark services as started
            self.status_label.setText("✓ Ready to launch!")
            self.progress_bar.setValue(100)
            self.details_label.setText("All services are running")
            
            # Show launch button
            self.launch_button.show()
            
            # Auto-launch if configured
            if self.config.get('auto_launch_ui', True):
                QTimer.singleShot(1000, self.open_web_ui)
        else:
            self.status_label.setText("❌ Startup failed")
            # Don't overwrite error details if they're already set
            if not self.details_label.text().startswith("Error:"):
                self.details_label.setText("Check Docker Desktop is running and docker-compose.yml exists")
            self.retry_button.show()
    
    def on_update_error(self, error_message: str):
        """Handle error during update"""
        self.details_label.setText(f"Error: {error_message}")
    
    def open_web_ui(self):
        """Open the web UI and minimize to tray"""
        webbrowser.open('http://localhost:8000')
        
        # Create system tray icon
        self.create_tray_icon()
        
        # Hide main window
        self.hide()
    
    def create_tray_icon(self):
        """Create system tray icon with menu"""
        if self.tray_icon:
            return
        
        # Create icon (using a simple colored circle as placeholder)
        icon = QIcon()
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        # TODO: Load actual icon from assets/icon.png
        icon.addPixmap(pixmap)
        
        self.tray_icon = QSystemTrayIcon(icon, self)
        
        # Create menu
        menu = QMenu()
        
        # Status
        status_action = QAction("✓ Running", self)
        status_action.setEnabled(False)
        menu.addAction(status_action)
        menu.addSeparator()
        
        # Open UI
        open_action = QAction("Open Web UI", self)
        open_action.triggered.connect(lambda: webbrowser.open('http://localhost:8000'))
        menu.addAction(open_action)
        
        # View logs
        logs_action = QAction("View Logs", self)
        logs_action.triggered.connect(self.view_logs)
        menu.addAction(logs_action)
        
        # Check for updates
        update_action = QAction("Check for Updates", self)
        update_action.triggered.connect(self.manual_update_check)
        menu.addAction(update_action)
        
        menu.addSeparator()
        
        # Restart
        restart_action = QAction("Restart Services", self)
        restart_action.triggered.connect(self.restart_services)
        menu.addAction(restart_action)
        
        # Stop
        stop_action = QAction("Stop Services", self)
        stop_action.triggered.connect(self.stop_services)
        menu.addAction(stop_action)
        
        menu.addSeparator()
        
        # Settings
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        
        # About
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        menu.addAction(about_action)
        
        # Quit
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()
        
        # Handle tray icon click
        self.tray_icon.activated.connect(self.tray_icon_activated)
    
    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            webbrowser.open('http://localhost:8000')
    
    def view_logs(self):
        """Open logs in browser or text editor"""
        webbrowser.open('http://localhost:8000/logs')
    
    def manual_update_check(self):
        """Manually trigger update check"""
        self.show()
        self.start_update_check()
    
    def restart_services(self):
        """Restart Docker services"""
        reply = QMessageBox.question(
            self,
            "Restart Services",
            "Are you sure you want to restart all services?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.show()
            self.status_label.setText("Restarting services...")
            self.progress_bar.setValue(0)
            
            # Restart in background
            self.docker_manager.restart_services()
            
            QTimer.singleShot(3000, lambda: self.update_progress(
                "✓ Services restarted", 100, "All services are running"
            ))
    
    def stop_services(self):
        """Stop Docker services"""
        reply = QMessageBox.question(
            self,
            "Stop Services",
            "Stop all AuraNexus services?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.docker_manager.stop_services()
            QMessageBox.information(self, "Services Stopped", "All services have been stopped.")
    
    def show_settings(self):
        """Show settings dialog"""
        # TODO: Implement settings dialog
        QMessageBox.information(self, "Settings", "Settings dialog coming soon!")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About AuraNexus",
            "<h3>AuraNexus Launcher v1.0.0</h3>"
            "<p>Multi-agent AI companion system</p>"
            "<p>© 2026 AuraNexus Project</p>"
            "<p><a href='https://github.com/yourusername/auranexus'>GitHub</a></p>"
        )
    
    def quit_application(self):
        """Quit the application"""
        reply = QMessageBox.question(
            self,
            "Quit AuraNexus",
            "Stop all services and quit?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.docker_manager.stop_services()
            QApplication.quit()
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.services_started and self.tray_icon:
            # Services are running - minimize to tray
            event.ignore()
            self.hide()
            
            if not self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    "AuraNexus",
                    "Application minimized to system tray",
                    QSystemTrayIcon.Information,
                    2000
                )
        else:
            # Services not started yet - allow quit
            event.accept()
            QApplication.quit()


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("AuraNexus Launcher")
    app.setOrganizationName("AuraNexus")
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show launcher
    launcher = LauncherWindow()
    launcher.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
