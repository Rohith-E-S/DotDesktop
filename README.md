DotDesktopA Qt-based desktop entry editor for Linux with support for Wayland/X11 environment overridesOverviewDotDesktop is a graphical tool for managing .desktop files on Linux systems. It provides a modern interface for editing application launchers without directly modifying system files, using the XDG Desktop Entry specification's override mechanism.Features🎨 Modern dark-themed UI built with PySide6🔍 Real-time search and filtering across all installed applications📦 Multi-source scanning (system, Snap, Flatpak)🛡️ Non-destructive editing via user overrides (~/.local/share/applications/)🚀 Built-in toolkit detection (Electron, GTK, Qt, Gecko)⚡ Quick presets for Wayland/X11 environment variables🧪 Test-run functionality before committing changes🎯 Custom delegate rendering with icon supportInstallationOption 1: AppImage (Recommended)The easiest way to run DotDesktop is using the standalone AppImage. No installation or dependencies required.Download the latest DotDesktop-x86_64.AppImage from the [suspicious link removed].Make it executable:chmod +x DotDesktop-x86_64.AppImage
Run it:./DotDesktop-x86_64.AppImage
Option 2: Manual Build (For Developers)If you prefer to run from source or want to contribute:# Clone the repository
git clone [https://github.com/yourusername/DotDesktop.git](https://github.com/yourusername/DotDesktop.git)
cd DotDesktop

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python3 desktop_editor.py
ArchitectureDirectory ScanningThe application scans the following directories in order of precedence:~/.local/share/flatpak/exports/share/applications  (User Flatpak)
/var/lib/flatpak/exports/share/applications        (System Flatpak)
/var/lib/snapd/desktop/applications                (Snap)
/usr/local/share/applications                      (Local)
/usr/share/applications                            (System)
User overrides in ~/.local/share/applications/ take precedence over system files per XDG specification.Toolkit DetectionAutomatic detection for common application frameworks:ToolkitDetection MethodEnvironment VariablesElectron/ChromiumBinary name matching--ozone-platform=waylandGTK/GNOMECategories + exec patternsGDK_BACKEND=waylandQt/KDECategories + exec patternsQT_QPA_PLATFORM=waylandGecko (Firefox)Binary name matchingMOZ_ENABLE_WAYLAND=1Usage ExamplesForce Wayland for Electron Apps# Via GUI:
# 1. Select app (e.g., VS Code, Discord)
# 2. Choose "Force Wayland (Electron Apps)" preset
# 3. Click "Inject" → "Save Changes"

# Manual equivalent in .desktop file:
Exec=env --ozone-platform=wayland /usr/bin/code %F
Override System Application# Creates user override at:
# ~/.local/share/applications/firefox.desktop

# Original system file remains untouched at:
# /usr/share/applications/firefox.desktop
Restore to System DefaultsUse the "Delete User Override" button to remove custom configurations and revert to system defaults.Technical SpecificationsDependenciesPython: 3.9+ (tested on 3.12)PySide6: Qt 6 bindings for PythonSystem: Linux with XDG-compliant desktop environmentFile FormatFollows the Desktop Entry Specification (freedesktop.org).Supported FieldsFieldTypeDescriptionNamestringApplication display nameCommentstringTooltip textExecstringCommand to executeIconstringIcon name or absolute pathTerminalbooleanRun in terminal emulatorCategoriesstring listMenu categories (semicolon-separated)MimeTypestring listAssociated file typesNoDisplaybooleanHide from application menuStartupNotifybooleanShow launch feedbackTroubleshootingAppImage Not RunningIf the AppImage fails to start on older systems, ensure you have FUSE support enabled. On newer systems (Ubuntu 22.04+), you may need to install libfuse2:sudo apt install libfuse2
Sandbox DetectionIf running from a sandboxed IDE (Snap/Flatpak), the application may have limited access to system directories. Run directly from a terminal or use the AppImage for full functionality.Changes Not AppearingAfter saving, run:update-desktop-database ~/.local/share/applications
The application attempts this automatically but may require manual execution depending on system configuration.ContributingContributions are welcome. Please ensure:Code follows PEP 8 style guidelinesQt signals/slots are properly connectedUser overrides never modify system files directlyLicenseMIT License - see LICENSE file for detailsAcknowledgmentsBuilt with PySide6 (Qt for Python) and inspired by the need for better Wayland application configuration on modern Linux desktops.
