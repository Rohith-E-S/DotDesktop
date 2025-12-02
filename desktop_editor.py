import sys
import os
import shutil
import configparser
import subprocess
import traceback
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QListWidget, QListWidgetItem, QLabel, 
                               QLineEdit, QPushButton, QFileDialog, QComboBox, 
                               QTextEdit, QMessageBox, QSplitter, QFrame, QGroupBox, 
                               QTabWidget, QStyledItemDelegate, QStyle, QPlainTextEdit,
                               QScrollArea, QCheckBox)
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QIcon, QAction, QPainter, QColor, QFont, QBrush, QPen, QPalette

# Extended paths to find Snap, Flatpak, and System apps
SEARCH_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    "/var/lib/snapd/desktop/applications",  # Snap Apps
    "/var/lib/flatpak/exports/share/applications",  # Flatpak System
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),  # Flatpak User
]

# Changes always save here to override the system
USER_DIR = os.path.expanduser("~/.local/share/applications")

# --- CUSTOM DELEGATE FOR MODERN LIST ---
class AppListDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 60) # Taller rows for readability

    def paint(self, painter, option, index):
        path = index.data(Qt.UserRole)
        name = index.data(Qt.UserRole + 1)
        filename = index.data(Qt.UserRole + 2)
        is_override = index.data(Qt.UserRole + 3)
        icon_source = index.data(Qt.UserRole + 4) # Icon name or path
        
        # Setup painter
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background color for selection or hover
        bg_rect = option.rect
        if option.state & QStyle.State_Selected:
            painter.fillRect(bg_rect, QColor("#3584e4")) # GNOME Blue
            text_color = QColor("white")
            subtext_color = QColor("#e0e0e0")
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(bg_rect, QColor("#3a3a3a"))
            text_color = QColor("white")
            subtext_color = QColor("#aaaaaa")
        else:
            text_color = QColor("white")
            subtext_color = QColor("#888888")

        # Icon area (left)
        icon_rect = QRect(bg_rect.left() + 10, bg_rect.top() + 10, 40, 40)
        
        # Resolve Icon
        if icon_source and os.path.isabs(icon_source) and os.path.exists(icon_source):
            # It is a direct path to an image file
            icon = QIcon(icon_source)
        elif icon_source:
            # It is a theme name (e.g., 'firefox')
            icon = QIcon.fromTheme(icon_source, QIcon.fromTheme("application-x-executable"))
        else:
            # Fallback
            icon = QIcon.fromTheme("application-x-executable")
            
        icon.paint(painter, icon_rect)

        # Text area
        text_rect = QRect(icon_rect.right() + 15, bg_rect.top() + 8, bg_rect.width() - 70, 20)
        subtext_rect = QRect(icon_rect.right() + 15, bg_rect.top() + 32, bg_rect.width() - 70, 18)

        # Draw Name (Bold)
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, name)

        # Draw Filename (Smaller)
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(subtext_color)
        
        sub_text = filename
        if is_override:
            painter.setPen(QColor("#57e389")) # Greenish for override text
            sub_text = f"USER OVERRIDE • {filename}"
            
        painter.drawText(subtext_rect, Qt.AlignLeft | Qt.AlignVCenter, sub_text)

        painter.restore()

class DesktopEntryEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DotDesktop - GUI Desktop Entry Editor")
        self.resize(1200, 850)
        
        self.apply_modern_theme()
        
        # Data storage
        self.current_file_path = None
        self.is_user_override = False
        self.config = None
        
        # Main Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Tabs for Editor vs Logs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- TAB 1: EDITOR ---
        editor_tab = QWidget()
        editor_layout = QHBoxLayout(editor_tab)
        editor_layout.setContentsMargins(15, 15, 15, 15)
        editor_layout.setSpacing(15)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        editor_layout.addWidget(splitter)
        
        # Left Panel (List)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 5, 0)
        left_layout.setSpacing(10)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search applications...")
        self.search_bar.textChanged.connect(self.filter_list)
        left_layout.addWidget(self.search_bar)
        
        self.app_list = QListWidget()
        self.app_list.setItemDelegate(AppListDelegate()) # Use modern delegate
        self.app_list.setFrameShape(QFrame.NoFrame)
        self.app_list.currentItemChanged.connect(self.load_selected_app)
        self.app_list.setAlternatingRowColors(False)
        left_layout.addWidget(self.app_list)
        
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.scan_applications)
        left_layout.addWidget(refresh_btn)
        
        splitter.addWidget(left_panel)
        
        # --- Right Panel (Fields) inside Scroll Area ---
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setStyleSheet("QScrollArea { background: transparent; } QWidget#RightPanel { background: transparent; }")
        
        self.right_panel = QWidget()
        self.right_panel.setObjectName("RightPanel")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(10, 0, 15, 0)
        self.right_layout.setSpacing(20)
        self.right_panel.setEnabled(False) 
        
        right_scroll.setWidget(self.right_panel)
        
        # 1. Info Header
        self.info_label = QLabel("Select an application to edit")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #888; margin-bottom: 5px;")
        self.right_layout.addWidget(self.info_label)
        
        # 2. GROUP: Core Info
        core_group = QGroupBox("Core Information")
        core_layout = QVBoxLayout()
        
        self.name_edit = self.create_field("Application Name:", core_layout)
        self.comment_edit = self.create_field("Tooltip / Comment:", core_layout)
        
        icon_layout = QHBoxLayout()
        self.icon_edit = QLineEdit()
        self.icon_edit.setPlaceholderText("Icon name or path")
        browse_icon_btn = QPushButton("Browse")
        browse_icon_btn.setFixedWidth(80)
        browse_icon_btn.clicked.connect(self.browse_icon)
        icon_layout.addWidget(self.icon_edit)
        icon_layout.addWidget(browse_icon_btn)
        self.add_field_layout("Icon:", icon_layout, core_layout)
        
        core_group.setLayout(core_layout)
        self.right_layout.addWidget(core_group)
        
        # 3. GROUP: Execution
        exec_group = QGroupBox("Execution")
        exec_layout = QVBoxLayout()
        
        exec_lbl = QLabel("Exec Command:")
        exec_lbl.setStyleSheet("font-weight: bold; color: #ccc;")
        exec_layout.addWidget(exec_lbl)
        
        exec_row = QHBoxLayout()
        self.exec_edit = QPlainTextEdit()
        self.exec_edit.setFixedHeight(70) 
        self.exec_edit.setPlaceholderText("Command to execute...")
        exec_row.addWidget(self.exec_edit)
        
        test_run_btn = QPushButton("Test Run")
        test_run_btn.setToolTip("Launch the app with these flags immediately")
        test_run_btn.setIcon(QIcon.fromTheme("media-playback-start"))
        test_run_btn.setFixedWidth(100)
        test_run_btn.clicked.connect(self.test_run_app)
        exec_row.addWidget(test_run_btn)
        
        exec_layout.addLayout(exec_row)
        
        # Injector
        injector_group = QGroupBox("Overrides Presets")
        injector_layout = QVBoxLayout()
        self.detected_label = QLabel("Auto-detecting toolkit...")
        self.detected_label.setStyleSheet("color: #888; font-style: italic;")
        injector_layout.addWidget(self.detected_label)
        
        preset_layout = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Select a preset to apply...",                          
            "Force Wayland (Electron Apps) -> --ozone-platform=wayland", 
            "Force Wayland (GTK Apps) -> env GDK_BACKEND=wayland",       
            "Force Wayland (Qt Apps) -> env QT_QPA_PLATFORM=wayland",     
            "Force Wayland (Firefox) -> env MOZ_ENABLE_WAYLAND=1",        
            "Force X11/Xorg (Generic) -> env GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb" 
        ])
        apply_preset_btn = QPushButton("Inject")
        apply_preset_btn.setFixedWidth(80)
        apply_preset_btn.clicked.connect(self.apply_preset)
        preset_layout.addWidget(self.preset_combo, 1)
        preset_layout.addWidget(apply_preset_btn)
        injector_layout.addLayout(preset_layout)
        injector_group.setLayout(injector_layout)
        exec_layout.addWidget(injector_group)
        
        self.terminal_check = QComboBox()
        self.terminal_check.addItems(["false", "true"])
        self.add_field_layout("Run in Terminal:", self.terminal_check, exec_layout)
        
        exec_group.setLayout(exec_layout)
        self.right_layout.addWidget(exec_group)

        # 4. GROUP: System & Metadata (NEW)
        meta_group = QGroupBox("System & Integration")
        meta_layout = QVBoxLayout()
        
        self.categories_edit = self.create_field("Categories (semicolon separated):", meta_layout)
        self.mime_edit = self.create_field("MimeTypes (File Associations):", meta_layout)
        
        # Checkboxes
        check_layout = QHBoxLayout()
        self.nodisplay_check = QCheckBox("Hide from App Menu (NoDisplay)")
        self.startup_check = QCheckBox("Show Launch Notification (StartupNotify)")
        check_layout.addWidget(self.nodisplay_check)
        check_layout.addWidget(self.startup_check)
        meta_layout.addLayout(check_layout)
        
        meta_group.setLayout(meta_layout)
        self.right_layout.addWidget(meta_group)

        # Action Buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        self.restore_btn = QPushButton("Delete User Override")
        self.restore_btn.setStyleSheet("""
            QPushButton { background-color: #c0392b; color: white; border: none; padding: 10px; border-radius: 6px; }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:pressed { background-color: #a93226; }
        """)
        self.restore_btn.clicked.connect(self.delete_override)
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; border: none; padding: 10px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #219150; }
        """)
        self.save_btn.clicked.connect(self.save_entry)
        
        action_layout.addWidget(self.restore_btn)
        action_layout.addWidget(self.save_btn)
        
        self.right_layout.addStretch()
        self.right_layout.addLayout(action_layout)
        
        splitter.addWidget(right_scroll)
        splitter.setSizes([400, 800])
        
        self.tabs.addTab(editor_tab, "Editor")
        
        # --- TAB 2: LOGS ---
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: monospace; padding: 10px;")
        self.tabs.addTab(self.log_view, "Scan Logs (Debug)")
        
        # Initial Scan
        self.scan_applications()

    def apply_modern_theme(self):
        # Dark Theme Styling (GNOME-like)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #242424;
            }
            QWidget {
                color: #ffffff;
                font-family: 'Segoe UI', 'Noto Sans', sans-serif;
                font-size: 10pt;
            }
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                background: #2d2d2d;
            }
            QTabBar::tab {
                background: #1e1e1e;
                color: #888;
                padding: 10px 20px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #2d2d2d;
                color: #fff;
                border-bottom: 2px solid #3584e4;
            }
            QLineEdit, QComboBox, QPlainTextEdit {
                background-color: #383838;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 8px;
                color: white;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
                border: 1px solid #3584e4;
                background-color: #404040;
            }
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #383838;
            }
            QListWidget::item:selected {
                background-color: #3584e4;
                color: white;
            }
            QPushButton {
                background-color: #444;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:pressed {
                background-color: #333;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #3584e4;
                font-weight: bold;
                left: 10px;
            }
            QLabel {
                color: #e0e0e0;
            }
            QSplitter::handle {
                background-color: #3d3d3d;
            }
            QCheckBox {
                spacing: 8px;
                color: #ddd;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background: #383838;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background: #3584e4;
                border: 1px solid #3584e4;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjIwIDYgOSAxNyA0IDEyIj48L3BvbHlsaW5lPjwvc3ZnPg==);
            }
        """)

    def log(self, message):
        self.log_view.append(message)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def create_field(self, label_text, parent_layout):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-weight: bold; color: #ccc;")
        edit = QLineEdit()
        layout.addWidget(lbl)
        layout.addWidget(edit)
        parent_layout.addWidget(container)
        return edit

    def add_field_layout(self, label_text, widget, parent_layout):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-weight: bold; color: #ccc;")
        layout.addWidget(lbl)
        if isinstance(widget, (QHBoxLayout, QVBoxLayout)):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
        parent_layout.addWidget(container)

    def scan_applications(self):
        self.app_list.clear()
        self.desktop_files = {} 
        self.log_view.clear()
        self.log("--- STARTING SCAN ---")
        
        sandbox_detected = False
        
        # 1. Scan Search Directories
        for directory in SEARCH_DIRS:
            if not os.path.exists(directory):
                self.log(f"[SKIP] Directory not found: {directory}")
                continue
            
            self.log(f"[SCAN] Reading: {directory}")
            try:
                files = os.listdir(directory)
                count = 0
                for f in files:
                    if f.endswith(".desktop"):
                        full_path = os.path.join(directory, f)
                        self.desktop_files[f] = full_path
                        count += 1
                self.log(f"   -> Found {count} .desktop files.")
                
                if directory == "/usr/share/applications" and count < 10:
                    sandbox_detected = True
                    self.log("   -> [WARNING] suspiciously low file count. Sandbox suspected.")

            except PermissionError:
                self.log(f"   -> [ERROR] Permission Denied!")
            except Exception as e:
                self.log(f"   -> [ERROR] {str(e)}")
        
        # 2. Scan User Directory
        self.log(f"[SCAN] Checking User Overrides: {USER_DIR}")
        if not os.path.exists(USER_DIR):
            os.makedirs(USER_DIR)
            
        try:
            files = os.listdir(USER_DIR)
            count = 0
            for f in files:
                if f.endswith(".desktop"):
                    self.desktop_files[f] = os.path.join(USER_DIR, f) 
                    count += 1
            self.log(f"   -> Found {count} override files.")
        except Exception as e:
            self.log(f"   -> [ERROR] {str(e)}")
                
        # Populate List
        self.log(f"--- POPULATING LIST ({len(self.desktop_files)} total apps) ---")
        for filename, path in sorted(self.desktop_files.items()):
            name = self.get_app_name(path)
            
            # Create item
            item = QListWidgetItem() 
            
            # Store all necessary data for the delegate to paint
            item.setData(Qt.UserRole, path)
            item.setData(Qt.UserRole + 1, name)      # Name
            item.setData(Qt.UserRole + 2, filename)  # Filename
            is_override = path.startswith(USER_DIR)
            item.setData(Qt.UserRole + 3, is_override) # Override flag
            
            # --- PARSE ICON ---
            icon_name = self.get_icon_name(path)
            item.setData(Qt.UserRole + 4, icon_name) # Icon
            
            # For searching/filtering
            item.setText(f"{name} {filename}") 
            
            self.app_list.addItem(item)
        self.log("--- SCAN COMPLETE ---")
        
        if sandbox_detected:
            QMessageBox.warning(self, "Sandbox Detected", 
                                "It looks like you are running this inside a Sandboxed IDE (Snap/Flatpak).\n\n"
                                "Please run this script from your system terminal instead.")

    def get_app_name(self, path):
        try:
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read(path)
            if "Desktop Entry" in cfg:
                return cfg["Desktop Entry"].get("Name", os.path.basename(path))
        except Exception:
            pass
        return os.path.basename(path)

    def get_icon_name(self, path):
        """Helper to safely extract Icon field"""
        try:
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read(path)
            if "Desktop Entry" in cfg:
                return cfg["Desktop Entry"].get("Icon", None)
        except Exception:
            pass
        return None

    def filter_list(self, text):
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            # Match against the hidden text we set earlier
            item.setHidden(text.lower() not in item.text().lower())

    def guess_toolkit(self, entry):
        exec_cmd = entry.get("Exec", "").lower()
        categories = entry.get("Categories", "")
        
        electron_keywords = [
            "electron", "code", "discord", "slack", "obsidian", 
            "vscodium", "vscode", "spotify", "typora", "mattermost", 
            "signal", "whatsapp", "teams", "chromium", "brave", "google-chrome"
        ]
        if any(k in exec_cmd for k in electron_keywords):
            return 1, "Electron/Chromium"
            
        firefox_keywords = ["firefox", "librewolf", "waterfox", "thunderbird", "seamonkey", "floorp"]
        if any(k in exec_cmd for k in firefox_keywords):
            return 4, "Firefox (Gecko)"
            
        if "Qt" in categories or "KDE" in categories or any(k in exec_cmd for k in ["dolphin", "kate", "kcalc", "okular", "kdenlive"]):
            return 3, "Qt/KDE"

        if "GTK" in categories or "GNOME" in categories or any(k in exec_cmd for k in ["gnome-", "gedit", "nautilus", "totem", "evince"]):
            return 2, "GTK/GNOME"

        return 0, "Unknown / Generic"

    def load_selected_app(self, current, previous):
        if not current:
            self.right_panel.setEnabled(False)
            return
            
        path = current.data(Qt.UserRole)
        self.current_file_path = path
        self.right_panel.setEnabled(True)
        
        self.is_user_override = path.startswith(USER_DIR)
        
        if self.is_user_override:
            self.info_label.setText(f"Editing: {os.path.basename(path)} (User Override)")
            self.info_label.setStyleSheet("color: #57e389; font-weight: bold; font-size: 14px;")
            self.restore_btn.setVisible(True)
        else:
            self.info_label.setText(f"Editing: {os.path.basename(path)} (System Default)")
            self.info_label.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 14px;")
            self.restore_btn.setVisible(False)

        self.config = configparser.ConfigParser(interpolation=None)
        self.config.optionxform = str 
        
        try:
            self.config.read(path)
            if "Desktop Entry" not in self.config:
                self.config["Desktop Entry"] = {}
                
            entry = self.config["Desktop Entry"]
            
            self.name_edit.setText(entry.get("Name", ""))
            self.comment_edit.setText(entry.get("Comment", ""))
            self.exec_edit.setPlainText(entry.get("Exec", ""))
            self.icon_edit.setText(entry.get("Icon", ""))
            self.categories_edit.setText(entry.get("Categories", ""))
            self.mime_edit.setText(entry.get("MimeType", ""))
            
            # Checkboxes
            no_display = entry.get("NoDisplay", "false").lower() == "true"
            self.nodisplay_check.setChecked(no_display)
            
            startup = entry.get("StartupNotify", "false").lower() == "true"
            self.startup_check.setChecked(startup)
            
            term = entry.get("Terminal", "false").lower()
            idx = self.terminal_check.findText(term)
            if idx >= 0: self.terminal_check.setCurrentIndex(idx)
            
            preset_idx, toolkit_name = self.guess_toolkit(entry)
            if preset_idx > 0:
                self.preset_combo.setCurrentIndex(preset_idx)
                self.detected_label.setText(f"Auto-detected toolkit: {toolkit_name}")
                self.detected_label.setStyleSheet("color: #2e8b57; font-weight: bold; margin-bottom: 5px;")
            else:
                self.preset_combo.setCurrentIndex(0)
                self.detected_label.setText("Toolkit not detected automatically.")
                self.detected_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 5px;")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse desktop file:\n{str(e)}")

    def browse_icon(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Icon", "/usr/share/icons", "Images (*.png *.svg *.xpm *.ico);;All Files (*)")
        if fname:
            self.icon_edit.setText(fname)

    def apply_preset(self):
        idx = self.preset_combo.currentIndex()
        if idx == 0: return
        
        current_exec = self.exec_edit.toPlainText().strip()
        new_exec = current_exec
        
        if idx == 1: 
            flag = "--ozone-platform=wayland"
            if flag not in new_exec:
                if "%" in new_exec:
                    parts = new_exec.split("%", 1)
                    new_exec = f"{parts[0].strip()} {flag} %{parts[1]}"
                else:
                    new_exec = f"{new_exec} {flag}"
        elif idx == 2:
            env = "env GDK_BACKEND=wayland"
            if "GDK_BACKEND" not in new_exec:
                new_exec = f"{env} {new_exec}"
        elif idx == 3:
            env = "env QT_QPA_PLATFORM=wayland"
            if "QT_QPA_PLATFORM" not in new_exec:
                new_exec = f"{env} {new_exec}"
        elif idx == 4:
            env = "env MOZ_ENABLE_WAYLAND=1"
            if "MOZ_ENABLE_WAYLAND" not in new_exec:
                new_exec = f"{env} {new_exec}"
        elif idx == 5:
            env = "env GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb"
            if "xcb" not in new_exec:
                new_exec = f"{env} {new_exec}"
        
        self.exec_edit.setPlainText(new_exec)
        QMessageBox.information(self, "Updated", "Exec command updated. Review it before saving!")

    def test_run_app(self):
        cmd = self.exec_edit.toPlainText()
        if not cmd: return
        clean_cmd = cmd.replace("%u", "").replace("%U", "").replace("%f", "").replace("%F", "").replace("%i", "").replace("%c", "").replace("%k", "")
        clean_cmd = clean_cmd.strip()
        self.log(f"[TEST] Launching: {clean_cmd}")
        try:
            subprocess.Popen(clean_cmd, shell=True)
            QMessageBox.information(self, "Test Run", f"Launching:\n{clean_cmd}\n\nCheck your taskbar!")
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", str(e))

    def update_desktop_db(self):
        try:
            subprocess.run(["update-desktop-database", USER_DIR], check=False)
        except FileNotFoundError:
            self.log("update-desktop-database command not found")

    def save_entry(self):
        if not self.config: return
        entry = self.config["Desktop Entry"]
        entry["Name"] = self.name_edit.text()
        entry["Comment"] = self.comment_edit.text()
        # Clean newlines from QPlainTextEdit to ensure valid desktop file format
        entry["Exec"] = self.exec_edit.toPlainText().replace("\n", " ").strip() 
        entry["Icon"] = self.icon_edit.text()
        entry["Categories"] = self.categories_edit.text()
        entry["MimeType"] = self.mime_edit.text()
        entry["Terminal"] = self.terminal_check.currentText()
        
        entry["NoDisplay"] = "true" if self.nodisplay_check.isChecked() else "false"
        entry["StartupNotify"] = "true" if self.startup_check.isChecked() else "false"
        
        if "DBusActivatable" in entry: entry["DBusActivatable"] = "false"
        
        filename = os.path.basename(self.current_file_path)
        target_path = os.path.join(USER_DIR, filename)
        
        try:
            with open(target_path, 'w') as configfile:
                self.config.write(configfile, space_around_delimiters=False)
            os.chmod(target_path, 0o755)
            self.update_desktop_db()
            self.scan_applications()
            QMessageBox.information(self, "Saved", f"Configuration saved to:\n{target_path}\n\nMenu updated!")
            items = self.app_list.findItems(f"{self.name_edit.text()} {filename}", Qt.MatchContains)
            if items: self.app_list.setCurrentItem(items[0])
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def delete_override(self):
        if not self.is_user_override: return
        ret = QMessageBox.question(self, "Confirm Restore", 
                                   "Are you sure you want to delete your custom override?\nThis will revert the app to system defaults.",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            try:
                os.remove(self.current_file_path)
                self.update_desktop_db()
                self.scan_applications()
                QMessageBox.information(self, "Restored", "User override deleted. System default restored.")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesktopEntryEditor()
    window.show()
    sys.exit(app.exec())