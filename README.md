# DotDesktop

> A Qt-based desktop entry editor for Linux with support for Wayland/X11 environment overrides

## Overview

DotDesktop is a graphical tool for managing `.desktop` files on Linux systems. It provides a modern interface for editing application launchers without directly modifying system files, using the XDG Desktop Entry specification's override mechanism.

## Features

- 🎨 Modern dark-themed UI built with PySide6
- 🔍 Real-time search and filtering across all installed applications
- 📦 Multi-source scanning (system, Snap, Flatpak)
- 🛡️ Non-destructive editing via user overrides (`~/.local/share/applications/`)
- 🚀 Built-in toolkit detection (Electron, GTK, Qt, Gecko)
- ⚡ Quick presets for Wayland/X11 environment variables
- 🧪 Test-run functionality before committing changes
- 🎯 Custom delegate rendering with icon support

##Installation

Option 1: AppImage (Recommended)

The easiest way to run DotDesktop is using the standalone AppImage. No installation or dependencies required.

Download the latest DotDesktop-x86_64.AppImage from the [suspicious link removed].

Make it executable:

chmod +x DotDesktop-x86_64.AppImage


Run it:

./DotDesktop-x86_64.AppImage


Option 2: Manual Build (For Developers)

If you prefer to run from source or want to contribute:

# Clone the repository
git clone [https://github.com/yourusername/DotDesktop.git](https://github.com/yourusername/DotDesktop.git)
cd DotDesktop

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python3 desktop_editor.py




## Architecture

### Directory Scanning

The application scans the following directories in order of precedence:

```
~/.local/share/flatpak/exports/share/applications  (User Flatpak)
/var/lib/flatpak/exports/share/applications        (System Flatpak)
/var/lib/snapd/desktop/applications                (Snap)
/usr/local/share/applications                      (Local)
/usr/share/applications                            (System)
```

User overrides in `~/.local/share/applications/` take precedence over system files per XDG specification.

### Toolkit Detection

Automatic detection for common application frameworks:

| Toolkit | Detection Method | Environment Variables |
|---------|-----------------|----------------------|
| Electron/Chromium | Binary name matching | `--ozone-platform=wayland` |
| GTK/GNOME | Categories + exec patterns | `GDK_BACKEND=wayland` |
| Qt/KDE | Categories + exec patterns | `QT_QPA_PLATFORM=wayland` |
| Gecko (Firefox) | Binary name matching | `MOZ_ENABLE_WAYLAND=1` |

## Usage Examples

### Force Wayland for Electron Apps

```bash
# Via GUI:
# 1. Select app (e.g., VS Code, Discord)
# 2. Choose "Force Wayland (Electron Apps)" preset
# 3. Click "Inject" → "Save Changes"

# Manual equivalent in .desktop file:
Exec=env --ozone-platform=wayland /usr/bin/code %F
```

### Override System Application

```bash
# Creates user override at:
# ~/.local/share/applications/firefox.desktop

# Original system file remains untouched at:
# /usr/share/applications/firefox.desktop
```

### Restore to System Defaults

Use the "Delete User Override" button to remove custom configurations and revert to system defaults.

## Technical Specifications

### Dependencies

- **Python**: 3.9+ (tested on 3.12)
- **PySide6**: Qt 6 bindings for Python
- **System**: Linux with XDG-compliant desktop environment

### File Format

Follows the [Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry-spec/latest/) (freedesktop.org).

### Supported Fields

| Field | Type | Description |
|-------|------|-------------|
| `Name` | string | Application display name |
| `Comment` | string | Tooltip text |
| `Exec` | string | Command to execute |
| `Icon` | string | Icon name or absolute path |
| `Terminal` | boolean | Run in terminal emulator |
| `Categories` | string list | Menu categories (semicolon-separated) |
| `MimeType` | string list | Associated file types |
| `NoDisplay` | boolean | Hide from application menu |
| `StartupNotify` | boolean | Show launch feedback |

## Development

### Project Structure

```
DotDesktop/
├── desktop_editor.py      # Main application
├── requirements.txt       # Python dependencies
└── README.md             # Documentation
```

### Custom Components

- **AppListDelegate**: Custom `QStyledItemDelegate` for rich list rendering
- **Preset System**: Configurable environment variable injection
- **Icon Resolution**: Supports both theme names and absolute paths

## Troubleshooting

### Sandbox Detection

If running from a sandboxed IDE (Snap/Flatpak), the application may have limited access to system directories. Run directly from a terminal for full functionality:

```bash
python3 desktop_editor.py
```

### Changes Not Appearing

After saving, run:

```bash
update-desktop-database ~/.local/share/applications
```

The application attempts this automatically but may require manual execution depending on system configuration.

## Contributing

Contributions are welcome. Please ensure:

- Code follows PEP 8 style guidelines
- Qt signals/slots are properly connected
- User overrides never modify system files directly

## License

MIT License - see LICENSE file for details

## Acknowledgments

Built with PySide6 (Qt for Python) and inspired by the need for better Wayland application configuration on modern Linux desktops.
