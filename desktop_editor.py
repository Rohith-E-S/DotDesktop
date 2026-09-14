import sys
import os
import shutil
import configparser
import subprocess
import traceback
import shlex  # [SECURE] Added for safe command parsing
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QListWidget, QListWidgetItem, QLabel, 
                               QLineEdit, QPushButton, QFileDialog, QComboBox, 
                                QTextEdit, QMessageBox, QSplitter, QFrame, QGroupBox,
                                QStyledItemDelegate, QStyle, QPlainTextEdit,
                               QScrollArea, QCheckBox, QSizePolicy)
from PySide6.QtCore import Qt, QSize, QRect, QSettings
from PySide6.QtGui import (QIcon, QAction, QPainter, QColor, QFont, QBrush, QPen,
                           QPalette, QShortcut, QKeySequence)

# Extended paths to find Snap, Flatpak, and System apps
SEARCH_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    "/var/lib/snapd/desktop/applications",
    "/var/lib/flatpak/exports/share/applications",
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
]

# Changes always save here to override the system
USER_DIR = os.path.expanduser("~/.local/share/applications")

# --- CUSTOM DELEGATE FOR MODERN LIST ---
class AppListDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 60) 

    def paint(self, painter, option, index):
        path = index.data(Qt.UserRole)
        name = index.data(Qt.UserRole + 1)
        filename = index.data(Qt.UserRole + 2)
        is_override = index.data(Qt.UserRole + 3)
        icon_source = index.data(Qt.UserRole + 4) 
        
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        bg_rect = option.rect
        if option.state & QStyle.State_Selected:
            painter.fillRect(bg_rect, QColor("#ffffff"))
            text_color = QColor("black")
            subtext_color = QColor("#000000")
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(bg_rect, QColor("#1a1a1a"))
            text_color = QColor("white")
            subtext_color = QColor("#a3a3a3")
        else:
            text_color = QColor("white")
            subtext_color = QColor("#a3a3a3")

        icon_rect = QRect(bg_rect.left() + 10, bg_rect.top() + 10, 40, 40)
        
        if icon_source and os.path.isabs(icon_source) and os.path.exists(icon_source):
            icon = QIcon(icon_source)
        elif icon_source:
            icon = QIcon.fromTheme(icon_source, QIcon.fromTheme("application-x-executable"))
        else:
            icon = QIcon.fromTheme("application-x-executable")
            
        icon.paint(painter, icon_rect)

        text_rect = QRect(icon_rect.right() + 15, bg_rect.top() + 8, bg_rect.width() - 70, 20)
        subtext_rect = QRect(icon_rect.right() + 15, bg_rect.top() + 32, bg_rect.width() - 70, 18)

        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, name)

        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(subtext_color)
        
        sub_text = filename
        if is_override:
            # ponytail: monochrome badge, white on dark, black on white selected
            if option.state & QStyle.State_Selected:
                painter.setPen(QColor("#000000"))
            else:
                painter.setPen(QColor("#ffffff"))
            sub_text = f"OVERRIDE • {filename}"
            
        painter.drawText(subtext_rect, Qt.AlignLeft | Qt.AlignVCenter, sub_text)
        painter.restore()

class DesktopEntryEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DotDesktop - Secure Desktop Entry Editor")
        self.resize(1200, 850)
        self.setMinimumSize(320, 500)
        self.apply_modern_theme()
        
        self.current_file_path = None
        self.is_user_override = False
        self.config = None
        self._dirty = False
        self._loading = False
        self._original_exec = ""
        self._shortcuts = []
        self.settings = QSettings("DotDesktop", "DotDesktop")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        editor_tab = QWidget()
        editor_layout = QHBoxLayout(editor_tab)
        editor_layout.setContentsMargins(15, 15, 15, 15)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        self.splitter = splitter
        self._narrow_mode = None
        editor_layout.addWidget(splitter)
        
        # Left Panel
        left_panel = QWidget()
        left_panel.setMinimumWidth(0)
        left_panel.setSizePolicy(left_panel.sizePolicy().horizontalPolicy(), left_panel.sizePolicy().verticalPolicy())
        self.left_panel = left_panel
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search applications...  (Ctrl+F)")
        self.search_bar.setMinimumWidth(0)
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.setToolTip("Type to filter the list. Enter opens the first match, Esc clears.")
        self.search_bar.textChanged.connect(self.filter_list)
        self.search_bar.returnPressed.connect(self.activate_first_match)
        
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self.search_bar, 1)
        self.count_label = QLabel("")
        self.count_label.setFixedWidth(60)
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.count_label.setStyleSheet("color: #a3a3a3; font-family: 'JetBrains Mono', monospace; font-size: 9pt;")
        search_row.addWidget(self.count_label)
        left_layout.addLayout(search_row)
        
        self.app_list = QListWidget()
        self.app_list.setItemDelegate(AppListDelegate())
        self.app_list.setFrameShape(QFrame.NoFrame)
        self.app_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.app_list.setTextElideMode(Qt.ElideRight)
        self.app_list.setUniformItemSizes(True)
        self.app_list.setMinimumWidth(0)
        self.app_list.currentItemChanged.connect(self.load_selected_app)
        left_layout.addWidget(self.app_list, 1)
        
        refresh_row = QHBoxLayout()
        self.refresh_row = refresh_row
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.setToolTip("Rescan all application directories (F5)")
        refresh_btn.clicked.connect(self.scan_applications)
        refresh_row.addWidget(refresh_btn, 1)
        self.logs_toggle = QPushButton("Show Logs")
        self.logs_toggle.setToolTip("Show or hide the scan and launch log (Ctrl+L)")
        self.logs_toggle.setCheckable(True)
        self.logs_toggle.setChecked(False)
        self.logs_toggle.setFixedWidth(95)
        self.logs_toggle.toggled.connect(self.toggle_logs)
        refresh_row.addWidget(self.logs_toggle)
        left_layout.addLayout(refresh_row)
        
        splitter.addWidget(left_panel)
        
        # Right Panel
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setMinimumWidth(0)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.right_scroll = right_scroll
        right_scroll.setStyleSheet("QScrollArea { background: transparent; } QWidget#RightPanel { background: transparent; }")
        
        self.right_panel = QWidget()
        self.right_panel.setObjectName("RightPanel")
        self.right_panel.setMinimumWidth(0)
        self.right_panel.setSizePolicy(self.right_panel.sizePolicy().horizontalPolicy(), self.right_panel.sizePolicy().verticalPolicy())
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(10, 0, 15, 0)
        self.right_layout.setSpacing(20)
        self.right_panel.setEnabled(False) 
        
        right_scroll.setWidget(self.right_panel)
        
        self.info_label = QLabel("Select an application to edit")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #a3a3a3; margin-bottom: 5px;")
        self.right_layout.addWidget(self.info_label)
        
        # Core Info
        core_group = QGroupBox("Core Information")
        core_layout = QVBoxLayout()
        self.name_edit = self.create_field("Application Name:", core_layout)
        self.comment_edit = self.create_field("Tooltip / Comment:", core_layout)
        
        icon_layout = QHBoxLayout()
        self.icon_layout = icon_layout
        self.icon_edit = QLineEdit()
        self.icon_edit.setPlaceholderText("Icon name or path")
        self.icon_edit.setMinimumWidth(0)
        self.icon_edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        browse_icon_btn = QPushButton("Browse")
        browse_icon_btn.setFixedWidth(80)
        browse_icon_btn.clicked.connect(self.browse_icon)
        icon_layout.addWidget(self.icon_edit, 1)
        icon_layout.addWidget(browse_icon_btn)
        self.add_field_layout("Icon:", icon_layout, core_layout)
        core_group.setLayout(core_layout)
        self.right_layout.addWidget(core_group)
        
        # Execution
        exec_group = QGroupBox("Execution")
        exec_layout = QVBoxLayout()
        
        exec_lbl = QLabel("Exec Command:")
        exec_lbl.setStyleSheet("font-weight: bold; color: #d4d4d4;")
        exec_layout.addWidget(exec_lbl)
        
        exec_row = QHBoxLayout()
        self.exec_row = exec_row
        self.exec_edit = QPlainTextEdit()
        self.exec_edit.setFixedHeight(70) 
        self.exec_edit.setPlaceholderText("Command to execute...")
        self.exec_edit.setMinimumWidth(0)
        self.exec_edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        exec_row.addWidget(self.exec_edit, 1)
        
        test_run_btn = QPushButton("Test Run (Safe)")
        test_run_btn.setToolTip("Launch safely using direct process execution (No Shell)")
        test_run_btn.setIcon(QIcon.fromTheme("media-playback-start"))
        test_run_btn.setFixedWidth(120)
        test_run_btn.clicked.connect(self.test_run_app)
        exec_row.addWidget(test_run_btn)
        
        exec_layout.addLayout(exec_row)
        
        injector_group = QGroupBox("Overrides Presets")
        injector_layout = QVBoxLayout()
        self.detected_label = QLabel("Auto-detecting toolkit...")
        self.detected_label.setStyleSheet("color: #a3a3a3; font-style: italic; font-family: 'JetBrains Mono', monospace;")
        injector_layout.addWidget(self.detected_label)
        
        preset_layout = QHBoxLayout()
        self.preset_layout = preset_layout
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(0)
        self.preset_combo.setMinimumContentsLength(0)
        self.preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        presets = [
            ("Select a preset to apply...", ""),
            ("Force Wayland (Electron)", "--ozone-platform=wayland"),
            ("Force Wayland (GTK)", "GDK_BACKEND=wayland"),
            ("Force Wayland (Qt)", "QT_QPA_PLATFORM=wayland"),
            ("Force Wayland (Firefox)", "MOZ_ENABLE_WAYLAND=1"),
            ("Force X11 / Xorg (Generic)", "GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb"),
        ]
        self.preset_combo.addItems([label for label, _ in presets])
        for idx, (_, env) in enumerate(presets):
            self.preset_combo.setItemData(
                idx, env or "Pick a preset to inject into the Exec command", Qt.ToolTipRole)
        apply_preset_btn = QPushButton("Inject")
        apply_preset_btn.setToolTip("Add the selected environment override to the Exec command")
        apply_preset_btn.setFixedWidth(80)
        apply_preset_btn.clicked.connect(self.apply_preset)
        self.reset_exec_btn = QPushButton("Reset")
        self.reset_exec_btn.setToolTip("Undo preset edits: restore the Exec command as loaded from disk")
        self.reset_exec_btn.setFixedWidth(80)
        self.reset_exec_btn.clicked.connect(self.reset_exec)
        preset_layout.addWidget(self.preset_combo, 1)
        preset_layout.addWidget(apply_preset_btn)
        preset_layout.addWidget(self.reset_exec_btn)
        injector_layout.addLayout(preset_layout)
        injector_group.setLayout(injector_layout)
        exec_layout.addWidget(injector_group)
        
        self.terminal_check = QComboBox()
        self.terminal_check.addItems(["false", "true"])
        self.terminal_check.setMinimumWidth(0)
        self.terminal_check.setMinimumContentsLength(0)
        self.terminal_check.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.add_field_layout("Run in Terminal:", self.terminal_check, exec_layout)
        
        exec_group.setLayout(exec_layout)
        self.right_layout.addWidget(exec_group)

        # Meta
        meta_group = QGroupBox("System & Integration")
        meta_layout = QVBoxLayout()
        self.categories_edit = self.create_field("Categories (semicolon separated):", meta_layout)
        self.mime_edit = self.create_field("MimeTypes (File Associations):", meta_layout)
        
        check_layout = QHBoxLayout()
        self.check_layout = check_layout
        self.nodisplay_check = QCheckBox("Hide from App Menu (NoDisplay)")
        self.startup_check = QCheckBox("Show Launch Notification (StartupNotify)")
        check_layout.addWidget(self.nodisplay_check)
        check_layout.addWidget(self.startup_check)
        meta_layout.addLayout(check_layout)
        meta_group.setLayout(meta_layout)
        self.right_layout.addWidget(meta_group)

        # Actions
        action_layout = QHBoxLayout()
        self.action_layout = action_layout
        action_layout.setSpacing(10)
        
        self.restore_btn = QPushButton("Delete User Override")
        self.restore_btn.setToolTip("Delete the user override and fall back to the system entry")
        self.restore_btn.setStyleSheet("QPushButton { background-color: #000000; color: #d4d4d4; border: 1px solid #444444; padding: 10px; border-radius: 8px; } QPushButton:hover { background-color: #1c1c1c; color: white; border: 1px solid white; }")
        self.restore_btn.clicked.connect(self.delete_override)
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setToolTip("Write the user override and refresh the desktop database (Ctrl+S)")
        self.save_btn.setStyleSheet("QPushButton { background-color: #ffffff; color: black; border: 1px solid white; padding: 10px; border-radius: 8px; font-weight: bold; } QPushButton:hover { background-color: #e5e5e5; }")
        self.save_btn.clicked.connect(lambda: self.save_entry())
        
        action_layout.addWidget(self.restore_btn)
        action_layout.addWidget(self.save_btn)
        
        self.right_layout.addStretch()
        self.right_layout.addLayout(action_layout)
        
        splitter.addWidget(right_scroll)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 800])
        main_layout.addWidget(editor_tab, 1)
        
        # LOGS — bottom drawer, hidden by default, no tab bar
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(140)
        self.log_view.setVisible(False)
        self.log_view.setStyleSheet("background-color: #000000; color: #ffffff; font-family: 'JetBrains Mono', monospace; font-size: 12px; padding: 10px; border-top: 1px solid #333333; border-left: none; border-right: none; border-bottom: none;")
        main_layout.addWidget(self.log_view)
        
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setStyleSheet(
            "QStatusBar { background-color: #0d0d0d; color: #a3a3a3; border-top: 1px solid #262626; }"
            "QStatusBar::item { border: none; } QStatusBar QLabel { color: #a3a3a3; }")
        
        # ponytail: native QShortcut, no menu bar invented for five keys
        for seq, slot in (
            ("Ctrl+F", self.focus_search),
            ("Ctrl+S", lambda: self.save_entry()),
            ("F5", lambda: self.scan_applications()),
            ("Ctrl+L", self.logs_toggle.toggle),
            ("Escape", self.clear_search),
        ):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(slot)
            self._shortcuts.append(sc)
        
        self._wire_dirty()
        
        saved_geometry = self.settings.value("geometry")
        if saved_geometry:
            self.restoreGeometry(saved_geometry)
        saved_split = self.settings.value("splitter")
        if saved_split:
            self.splitter.restoreState(saved_split)
        self._apply_layout_mode(self.width(), force=True)
        
        self.scan_applications()

    def apply_modern_theme(self):
        # ponytail: High Contrast B&W from Stitch, no color accents
        self.setStyleSheet("""
            QMainWindow { background-color: #000000; }
            QWidget { color: #ffffff; font-family: 'Inter', 'Noto Sans', sans-serif; font-size: 10pt; }
            QLineEdit, QComboBox, QPlainTextEdit { background-color: #000000; border: 1px solid #333333; border-radius: 8px; padding: 8px; color: white; }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border: 1px solid #ffffff; background-color: #000000; }
            QListWidget { background-color: #080808; border: 1px solid #262626; border-radius: 8px; outline: none; }
            QListWidget::item { border-bottom: 1px solid #262626; border: 1px solid transparent; border-radius: 8px; margin: 2px; }
            QListWidget::item:selected { background-color: #141414; color: white; border: 2px solid #ffffff; }
            QListWidget::item:hover { background-color: #121212; border: 1px solid #333333; }
            QPushButton { background-color: #1c1c1c; border: 1px solid #3e3e3e; border-radius: 8px; padding: 6px 12px; color: white; }
            QPushButton:hover { background-color: #282828; border: 1px solid #ffffff; }
            QPushButton:pressed { background-color: #000000; }
            QGroupBox { border: 1px solid #333333; border-radius: 12px; margin-top: 10px; padding-top: 15px; background-color: #0d0d0d; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; color: #ffffff; font-weight: bold; left: 10px; text-transform: uppercase; font-size: 9pt; }
            QLabel { color: #d4d4d4; }
            QSplitter::handle { background-color: #262626; }
            QCheckBox { spacing: 8px; color: #d4d4d4; }
            QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #666666; border-radius: 4px; background-color: #000000; }
            QCheckBox::indicator:hover { border: 1px solid #ffffff; }
            QCheckBox::indicator:checked { background-color: #ffffff; border: 1px solid #ffffff; }
            QPushButton:focus { border: 2px solid #ffffff; }
            QToolTip { background-color: #ffffff; color: #000000; border: 1px solid #000000; padding: 4px; }
            QScrollBar:vertical { background: #000000; width: 5px; }
            QScrollBar::handle:vertical { background: #333333; border-radius: 2px; }
            QComboBox QAbstractItemView { background-color: #000000; color: #ffffff; border: 1px solid #444444; outline: none; }
            QComboBox QAbstractItemView::item { padding: 6px; }
            QComboBox QAbstractItemView::item:selected { background-color: #ffffff; color: #000000; }
            QComboBox QAbstractItemView::item:hover { background-color: #1c1c1c; color: #ffffff; }
        """)
        # ponytail: Fusion's default highlight is blue — force the B&W palette so
        # selections in popups and text fields stay monochrome too.
        app = QApplication.instance()
        if app is not None:
            palette = app.palette()
            palette.setColor(QPalette.Highlight, QColor("#ffffff"))
            palette.setColor(QPalette.HighlightedText, QColor("#000000"))
            palette.setColor(QPalette.PlaceholderText, QColor("#8a8a8a"))
            app.setPalette(palette)

    def toggle_logs(self, checked):
        self.log_view.setVisible(checked)
        self.logs_toggle.setText("Hide Logs" if checked else "Show Logs")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_layout_mode(self.width())

    @staticmethod
    def _layout_mode(width):
        # ponytail: one tier — rows stack under 1020px. The list is never hidden;
        # at <720px the panes just get narrower (hiding it made picking an app impossible).
        return (width < 1020,)

    def _apply_layout_mode(self, width, force=False):
        from PySide6.QtWidgets import QBoxLayout
        mode = self._layout_mode(width)
        if mode == self._narrow_mode and not force:
            return
        self._narrow_mode = mode
        (stack_rows,) = mode
        stack = QBoxLayout.TopToBottom if stack_rows else QBoxLayout.LeftToRight
        self.exec_row.setDirection(stack)
        self.preset_layout.setDirection(stack)
        self.icon_layout.setDirection(stack)
        self.check_layout.setDirection(stack)
        self.action_layout.setDirection(stack)
        if force:
            # keep restored/default splitter sizes until the width tier actually changes
            return
        if stack_rows:
            left = max(200, min(300, width // 3))
            self.splitter.setSizes([left, max(280, width - left)])
        else:
            self.splitter.setSizes([400, max(280, width - 400)])

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
        lbl.setStyleSheet("font-weight: bold; color: #d4d4d4;")
        lbl.setWordWrap(True)
        edit = QLineEdit()
        edit.setMinimumWidth(0)
        edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
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
        lbl.setStyleSheet("font-weight: bold; color: #d4d4d4;")
        layout.addWidget(lbl)
        if isinstance(widget, (QHBoxLayout, QVBoxLayout)):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
        parent_layout.addWidget(container)

    def scan_applications(self):
        if self._dirty:
            ret = QMessageBox.question(
                self, "Unsaved Changes",
                "Refreshing reloads the files from disk and discards unsaved changes.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
            self._dirty = False
            self._update_title()
        previous_path = self.current_file_path
        self._loading = True
        self.app_list.blockSignals(True)
        self.app_list.clear()
        self.desktop_files = {} 
        self.log_view.clear()
        self.log("--- STARTING SCAN ---")
        
        sandbox_detected = False
        
        for directory in SEARCH_DIRS:
            if not os.path.exists(directory): continue
            
            # [SECURE] Ensure we don't follow symlinks for directories unless explicitly desired, 
            # though here we just read. 
            self.log(f"[SCAN] Reading: {directory}")
            try:
                files = os.listdir(directory)
                count = 0
                for f in files:
                    if f.endswith(".desktop"):
                        full_path = os.path.join(directory, f)
                        # [SECURE] Validate that full_path is inside the directory (basic check)
                        if os.path.dirname(full_path) == directory:
                            self.desktop_files[f] = full_path
                            count += 1
                self.log(f"   -> Found {count} .desktop files.")
                
                if directory == "/usr/share/applications" and count < 10:
                    sandbox_detected = True

            except PermissionError:
                self.log(f"   -> [ERROR] Permission Denied: {directory}")
        
        # Scan User Directory
        if not os.path.exists(USER_DIR):
            os.makedirs(USER_DIR, mode=0o700) # [SECURE] Create with strict permissions
            
        try:
            files = os.listdir(USER_DIR)
            for f in files:
                if f.endswith(".desktop"):
                    self.desktop_files[f] = os.path.join(USER_DIR, f) 
        except Exception as e:
            self.log(f"   -> [ERROR] {str(e)}")
                
        # Populate List — sorted by display name, not by filename
        rows = [(self.get_app_name(path), filename, path)
                for filename, path in self.desktop_files.items()]
        rows.sort(key=lambda row: (row[0].lower(), row[1].lower()))
        for name, filename, path in rows:
            item = QListWidgetItem() 
            item.setData(Qt.UserRole, path)
            item.setData(Qt.UserRole + 1, name)
            item.setData(Qt.UserRole + 2, filename)
            is_override = path.startswith(USER_DIR)
            item.setData(Qt.UserRole + 3, is_override)
            item.setData(Qt.UserRole + 4, self.get_icon_name(path))
            item.setText(f"{name} {filename}") 
            self.app_list.addItem(item)
        
        self.app_list.blockSignals(False)
        self._loading = False
        self.filter_list(self.search_bar.text())
        if not (previous_path and self.select_path(previous_path)):
            self.current_file_path = None
            self.config = None
            self.is_user_override = False
            self._dirty = False
            self.right_panel.setEnabled(False)
            self.info_label.setText("Select an application to edit")
            self._update_title()
            
        if sandbox_detected:
            QMessageBox.warning(self, "Sandbox Detected", "Running inside a Sandbox. Some system paths are inaccessible.")

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
        try:
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read(path)
            if "Desktop Entry" in cfg:
                return cfg["Desktop Entry"].get("Icon", None)
        except Exception:
            pass
        return None

    def filter_list(self, text):
        query = text.strip().lower()
        visible = 0
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            match = not query or query in item.text().lower()
            item.setHidden(not match)
            visible += 1 if match else 0
        self._set_count(visible)
        if query and visible == 0:
            self.statusBar().showMessage(f'No applications match "{text.strip()}"', 4000)

    def _set_count(self, visible):
        total = self.app_list.count()
        self.count_label.setText(str(total) if visible == total else f"{visible}/{total}")
        self.count_label.setToolTip(f"{visible} of {total} applications shown")

    def focus_search(self):
        self.search_bar.setFocus()
        self.search_bar.selectAll()

    def clear_search(self):
        if self.search_bar.text():
            self.search_bar.clear()
        else:
            self.app_list.setFocus()

    def activate_first_match(self):
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            if not item.isHidden():
                self.app_list.setCurrentItem(item)
                self.app_list.scrollToItem(item)
                self.app_list.setFocus()
                return

    def guess_toolkit(self, entry):
        exec_cmd = entry.get("Exec", "").lower()
        categories = entry.get("Categories", "")
        
        if any(k in exec_cmd for k in ["electron", "discord", "slack", "obsidian", "vscode", "code"]):
            return 1, "Electron/Chromium"
        if any(k in exec_cmd for k in ["firefox", "librewolf", "thunderbird"]):
            return 4, "Firefox (Gecko)"
        if "Qt" in categories or "KDE" in categories:
            return 3, "Qt/KDE"
        if "GTK" in categories or "GNOME" in categories:
            return 2, "GTK/GNOME"
        return 0, "Unknown"

    def load_selected_app(self, current, previous):
        if previous is not None and self._dirty and not self._loading:
            answer = self._ask_unsaved()
            if answer == QMessageBox.Cancel:
                self.app_list.blockSignals(True)
                self.app_list.setCurrentItem(previous)
                self.app_list.blockSignals(False)
                return
            if answer == QMessageBox.Save:
                target = current.data(Qt.UserRole) if current else None
                self.save_entry(rescan=True)
                if target:
                    self.select_path(target)
                return
            self._dirty = False
            self._update_title()

        if not current:
            self.current_file_path = None
            self.config = None
            self.is_user_override = False
            self._dirty = False
            self.right_panel.setEnabled(False)
            self.info_label.setText("Select an application to edit")
            self.info_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #a3a3a3; margin-bottom: 5px;")
            self._update_title()
            return
            
        path = current.data(Qt.UserRole)
        self.current_file_path = path
        self.right_panel.setEnabled(True)
        self.is_user_override = path.startswith(USER_DIR)
        
        if self.is_user_override:
            self.info_label.setText(f"Editing: {os.path.basename(path)} (User Override)")
            self.info_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 14px; background: #000000; border: 1px solid #ffffff; border-radius: 12px; padding: 4px;")
            self.restore_btn.setVisible(True)
        else:
            self.info_label.setText(f"Editing: {os.path.basename(path)} (System Default)")
            self.info_label.setStyleSheet("color: #a3a3a3; font-weight: bold; font-size: 14px;")
            self.restore_btn.setVisible(False)

        self.config = configparser.ConfigParser(interpolation=None)
        self.config.optionxform = str 
        self._loading = True
        
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
            
            self.nodisplay_check.setChecked(entry.get("NoDisplay", "false").lower() == "true")
            self.startup_check.setChecked(entry.get("StartupNotify", "false").lower() == "true")
            
            term = entry.get("Terminal", "false").lower()
            idx = self.terminal_check.findText(term)
            if idx >= 0: self.terminal_check.setCurrentIndex(idx)
            
            preset_idx, toolkit = self.guess_toolkit(entry)
            self.preset_combo.setCurrentIndex(preset_idx)
            self.detected_label.setText(f"Auto-detected toolkit: {toolkit}" if preset_idx > 0 else "Toolkit not detected automatically.")
            
            self._original_exec = entry.get("Exec", "")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse desktop file:\n{str(e)}")
            self.statusBar().showMessage(f"Failed to load {os.path.basename(path)}", 5000)
        finally:
            self._loading = False
            self._dirty = False
            self._update_title()

    def browse_icon(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Icon", "/usr/share/icons", "Images (*.png *.svg *.xpm *.ico);;All Files (*)")
        if fname:
            self.icon_edit.setText(fname)

    def apply_preset(self):
        idx = self.preset_combo.currentIndex()
        if idx == 0: return
        
        current_exec = self.exec_edit.toPlainText().strip()
        new_exec = current_exec
        
        if idx == 1 and "--ozone-platform=wayland" not in new_exec:
            if "%" in new_exec:
                parts = new_exec.split("%", 1)
                new_exec = f"{parts[0].strip()} --ozone-platform=wayland %{parts[1]}"
            else:
                new_exec = f"{new_exec} --ozone-platform=wayland"
        elif idx == 2 and "GDK_BACKEND" not in new_exec:
            new_exec = f"env GDK_BACKEND=wayland {new_exec}"
        elif idx == 3 and "QT_QPA_PLATFORM" not in new_exec:
            new_exec = f"env QT_QPA_PLATFORM=wayland {new_exec}"
        elif idx == 4 and "MOZ_ENABLE_WAYLAND" not in new_exec:
            new_exec = f"env MOZ_ENABLE_WAYLAND=1 {new_exec}"
        elif idx == 5 and "xcb" not in new_exec:
            new_exec = f"env GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb {new_exec}"
        
        self.exec_edit.setPlainText(new_exec)
        if new_exec == current_exec:
            self.statusBar().showMessage("That preset is already applied.", 3000)
        else:
            self.statusBar().showMessage("Exec updated. Review it, then Save Changes (Ctrl+S).", 4000)

    def reset_exec(self):
        if not self.config: return
        self.exec_edit.setPlainText(self._original_exec)
        self.statusBar().showMessage("Exec reverted to the value loaded from disk.", 3000)

    def test_run_app(self):
        cmd = self.exec_edit.toPlainText().strip()
        if not cmd: return
        
        # [SECURE] Clean up XDG placeholders which cannot be processed without a shell/launcher
        clean_cmd = cmd.replace("%u", "").replace("%U", "").replace("%f", "").replace("%F", "") \
                       .replace("%i", "").replace("%c", "").replace("%k", "").strip()
        
        self.log(f"[TEST] Preparing to launch: {clean_cmd}")
        
        try:
            # [SECURE] Use shlex to parse command line correctly without using shell=True
            args = shlex.split(clean_cmd)
            if not args: return
            
            # [SECURE] Verify executable exists in path
            executable = shutil.which(args[0])
            if not executable:
                 QMessageBox.warning(self, "Security/Error", f"Executable not found in PATH: {args[0]}")
                 return
                 
            # [SECURE] Run without shell to prevent injection
            subprocess.Popen(args, shell=False)
            
            self.log(f"[TEST] Launched: {' '.join(args)}")
            self.logs_toggle.setChecked(True)
            self.statusBar().showMessage(f"Test launched: {args[0]}", 4000)
        except ValueError as ve:
             QMessageBox.critical(self, "Parse Error", f"Command parsing failed (unbalanced quotes?):\n{str(ve)}")
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", str(e))

    def update_desktop_db(self):
        # [SECURE] Use full path if possible or verify command exists
        if shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", USER_DIR], check=False)
        else:
            self.log("update-desktop-database not found in PATH.")

    def save_entry(self, rescan=True):
        if not self.config:
            self.statusBar().showMessage("Nothing to save: select an application first.", 4000)
            return
        
        # [SECURE] Basic Input Sanitization
        entry = self.config["Desktop Entry"]
        entry["Name"] = self.name_edit.text()
        entry["Comment"] = self.comment_edit.text()
        entry["Exec"] = self.exec_edit.toPlainText().replace("\n", " ").strip() 
        entry["Icon"] = self.icon_edit.text()
        entry["Categories"] = self.categories_edit.text()
        entry["MimeType"] = self.mime_edit.text()
        entry["Terminal"] = self.terminal_check.currentText()
        entry["NoDisplay"] = "true" if self.nodisplay_check.isChecked() else "false"
        entry["StartupNotify"] = "true" if self.startup_check.isChecked() else "false"
        
        if "DBusActivatable" in entry: entry["DBusActivatable"] = "false"
        
        filename = os.path.basename(self.current_file_path)
        
        # [SECURE] Path Traversal & Filename Validation
        # Ensure filename contains only safe characters and no directory separators
        if not filename or "/" in filename or "\\" in filename or filename in [".", ".."]:
            QMessageBox.critical(self, "Security Error", "Invalid filename detected.")
            return

        target_path = os.path.join(USER_DIR, filename)
        
        # [SECURE] Prevent Symlink Hijacking
        # Check if the target is already a symlink (attacker could place one there)
        if os.path.exists(target_path) and os.path.islink(target_path):
             QMessageBox.critical(self, "Security Error", 
                                  "Target file is a symbolic link.\n"
                                  "This is a security risk. Please delete it manually first.")
             return
        
        try:
            # [SECURE] Atomic Write Pattern
            # 1. Write to a temporary file
            temp_path = target_path + ".tmp"
            with open(temp_path, 'w') as configfile:
                self.config.write(configfile, space_around_delimiters=False)
            
            # 2. Set strict permissions (Read/Write for User, Read for others, No Execute)
            os.chmod(temp_path, 0o644)
            
            # 3. Rename atomically (overwrites target if it exists, but safely)
            os.replace(temp_path, target_path)
            
            self._dirty = False
            # select the override (not the system file) on the follow-up rescan
            self.current_file_path = target_path
            self.is_user_override = True
            self.update_desktop_db()
            if rescan:
                self.scan_applications()
            self.log(f"[SAVE] Wrote {target_path}")
            self._update_title()
            self.statusBar().showMessage(f"Saved to {target_path}", 5000)
            
        except Exception as e:
            # Clean up temp file if it exists
            if os.path.exists(target_path + ".tmp"):
                os.remove(target_path + ".tmp")
            QMessageBox.critical(self, "Save Error", str(e))

    def delete_override(self):
        if not self.is_user_override: return
        ret = QMessageBox.question(self, "Confirm Restore", 
                                   "Delete your custom override and fall back to the system entry?\n"
                                   "Any unsaved edits are lost.",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            try:
                # [SECURE] Path check again just to be safe
                if os.path.dirname(self.current_file_path) != USER_DIR:
                     raise ValueError("Cannot delete files outside user directory.")
                     
                os.remove(self.current_file_path)
                self._dirty = False
                self.update_desktop_db()
                self.scan_applications()
                self.statusBar().showMessage("User override deleted. System entry restored.", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # --- Interaction helpers: dirty tracking, selection, persistence ---
    def _wire_dirty(self):
        for widget in (self.name_edit, self.comment_edit, self.icon_edit,
                       self.categories_edit, self.mime_edit):
            widget.textChanged.connect(self.mark_dirty)
        self.exec_edit.textChanged.connect(self.mark_dirty)
        self.terminal_check.currentTextChanged.connect(self.mark_dirty)
        self.nodisplay_check.toggled.connect(self.mark_dirty)
        self.startup_check.toggled.connect(self.mark_dirty)

    def mark_dirty(self, *args):
        if self._loading or not self.config or self._dirty:
            return
        self._dirty = True
        self._update_title()

    def _update_title(self):
        name = os.path.basename(self.current_file_path) if self.current_file_path else ""
        dirty_mark = " *" if self._dirty else ""
        suffix = f" - {name}{dirty_mark}" if name else ""
        self.setWindowTitle(f"DotDesktop - Secure Desktop Entry Editor{suffix}")

    def _ask_unsaved(self):
        name = os.path.basename(self.current_file_path) if self.current_file_path else "this entry"
        return QMessageBox.question(
            self, "Unsaved Changes",
            f"Unsaved changes to {name}.\n\nSave them as a user override?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save)

    def select_path(self, path):
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            if item.data(Qt.UserRole) == path:
                self.app_list.setCurrentItem(item)
                self.app_list.scrollToItem(item)
                return True
        return False

    def closeEvent(self, event):
        if self._dirty:
            answer = self._ask_unsaved()
            if answer == QMessageBox.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.Save:
                self.save_entry(rescan=False)
                if self._dirty:  # save failed, keep the window open
                    event.ignore()
                    return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesktopEntryEditor()
    window.show()
    sys.exit(app.exec())