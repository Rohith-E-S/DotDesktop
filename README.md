# DotDesktop

A Qt-based desktop entry editor for Linux with support for Wayland/X11 environment overrides

---

## Overview

**DotDesktop** is a graphical tool for managing `.desktop` files on Linux systems.  
It provides an easy interface to edit application launchers, add Wayland/X11 overrides for per-app environments, and manage user vs. system entries.

---

## Features

- Browse & edit application launchers (`.desktop` files)
- One-click override of Wayland/X11 variables for Electron & GTK apps
- Scan user, system, Flatpak, and Snap entries (with override precedence)
- Safely inject environment variables (`Exec=env ...`)
- Restore to system defaults by deleting overrides

---

## Getting Started

### Option 1: AppImage (Recommended)

1. Download the latest `DotDesktop-x86_64.AppImage` from [Releases](https://github.com/yourusername/DotDesktop/releases)
2. Make it executable:
   ```bash
   chmod +x DotDesktop-x86_64.AppImage
   ```
3. Run it:
   ```bash
   ./DotDesktop-x86_64.AppImage
   ```

### Option 2: Manual Build (For Developers)

If you prefer to run from source or want to contribute:

```bash
# Clone the repository
git clone https://github.com/yourusername/DotDesktop.git
cd DotDesktop

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python3 desktop_editor.py
```

---

## Architecture

### Directory Scanning

The application scans the following directories in order of precedence:

1. `~/.local/share/flatpak/exports/share/applications`  (User Flatpak)
2. `/var/lib/flatpak/exports/share/applications`        (System Flatpak)
3. `/var/lib/snapd/desktop/applications`                (Snap)
4. `/usr/local/share/applications`                      (Local)
5. `/usr/share/applications`                            (System)

> **Note:** User overrides in `~/.local/share/applications/` take precedence over system files per the XDG specification.

### Toolkit Detection

Automatic detection for common application frameworks:

| Toolkit   | Detection Method             | Environment Variable   |
|-----------|-----------------------------|---------------------|
| Electron  | Looks for Electron runs      | `--ozone-platform`  |
| GTK       | GTK-specific class names     | `GDK_BACKEND`       |
| Qt        | Qt module imports/classes    | `QT_QPA_PLATFORM`   |

---

## Usage Example

1. **Select App** (e.g., VS Code, Discord)
2. Choose **"Force Wayland (Electron Apps)"** preset
3. Click **"Inject"** → **"Save Changes"**

#### Manual Equivalent in `.desktop` File

```ini
Exec=env --ozone-platform=wayland /usr/bin/code %F
```

---

## Override System Application

- Creates user override at:  
  `~/.local/share/applications/firefox.desktop`
- Original system file remains untouched at:  
  `/usr/share/applications/firefox.desktop`

---

## Restore to System Defaults

Use the **"Delete User Override"** button to remove custom configurations and revert to system defaults.

---

## Technical Specifications

- **Python:** 3.9+ (tested on 3.12)
- **PySide6:** for cross-platform Qt GUI
- **XDG Desktop Entry Spec:** Follows [freedesktop.org spec](https://specifications.freedesktop.org/desktop-entry-spec/latest/)
- **Wayland/X11:** Environment variable presets for common sandbox/Wayland settings

---

## Sandbox Detection

If running from a sandboxed IDE (Snap/Flatpak), the application may have limited access to system directories.  
Run directly from a terminal or use the AppImage for full functionality.

**Troubleshooting:**  
The application attempts this automatically but may require manual execution depending on your system configuration.

---

## Contributing

Contributions are welcome!  
Please ensure:
- Code follows [PEP 8](https://peps.python.org/pep-0008/) style guidelines
- Qt UI changes update `.ui` files as needed
- Pull Requests describe the change and testing

---

## License

[MIT License](LICENSE.txt)

---
