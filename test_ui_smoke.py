"""Smoke check for DotDesktop UI wiring. Runs headless:

    QT_QPA_PLATFORM=offscreen venv/bin/python test_ui_smoke.py [screenshot.png]

Checks shortcuts, name-sorted list, result counts, filter feedback, dirty
tracking, preset inject/undo and layout tiers. No files are written.
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication, QMessageBox

import desktop_editor

# headless: never block on a modal dialog
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Discard)


def visible_count(win):
    return sum(1 for i in range(win.app_list.count()) if not win.app_list.item(i).isHidden())


def main():
    app = QApplication([])
    win = desktop_editor.DesktopEntryEditor()
    win.resize(1200, 850)
    win.show()
    app.processEvents()

    assert sorted(s.key().toString() for s in win._shortcuts) == \
        ["Ctrl+F", "Ctrl+L", "Ctrl+S", "Esc", "F5"], "shortcuts missing"
    assert win.statusBar() is not None
    palette = app.palette()
    assert palette.highlight().color().name() == "#ffffff", "selection highlight is not monochrome"
    assert palette.highlightedText().color().name() == "#000000", "highlighted text contrast wrong"

    names = [win.app_list.item(i).data(desktop_editor.Qt.UserRole + 1)
             for i in range(win.app_list.count())]
    assert names == sorted(names, key=str.lower), "list not sorted by display name"
    assert win.count_label.text() == str(win.app_list.count()), "count label wrong"

    total = win.app_list.count()
    if total:
        first_name = names[0]
        win.search_bar.setText(first_name[:4])  # hit Ctrl+F helper directly too
        app.processEvents()
        shown = visible_count(win)
        assert 1 <= shown <= total, "filter kept everything hidden"
        assert win.count_label.text() == f"{shown}/{total}", win.count_label.text()
        win.clear_search()
        assert win.search_bar.text() == ""
        assert win.count_label.text() == str(total)

        win.app_list.setCurrentRow(0)
        app.processEvents()
        assert win.right_panel.isEnabled(), "right panel stayed disabled"
        assert not win._dirty, "freshly loaded entry marked dirty"
        title_before = win.windowTitle()
        win.name_edit.insert("x")
        assert win._dirty and win.windowTitle() != title_before, "dirty state not tracked"

        original_exec = win.exec_edit.toPlainText()
        win.preset_combo.setCurrentIndex(2)  # GDK_BACKEND=wayland
        win.apply_preset()
        assert "GDK_BACKEND=wayland" in win.exec_edit.toPlainText(), "preset not injected"
        win.reset_exec()
        assert win.exec_edit.toPlainText() == original_exec, "reset did not restore Exec"

        if total > 1:  # switching entries reloads and clears dirty
            win.app_list.setCurrentRow(1)
            app.processEvents()
            assert not win._dirty, "dirty flag survived a reload"
            assert " *" not in win.windowTitle()

    # width tiers must not crash and must keep the app list reachable at any size
    for width, height in ((760, 700), (600, 800), (380, 700), (1400, 900)):
        win.resize(width, height)
        app.processEvents()
        assert win._narrow_mode == (width < 1020,), (width, win._narrow_mode)
        left, right = win.splitter.sizes()
        assert left > 0 and right > 0, f"pane collapsed at {width}px: {win.splitter.sizes()}"
        assert win.left_panel.isVisibleTo(win), f"app list hidden at {width}px"
    win.resize(600, 800)  # narrow tier keeps a sane list width, not 0
    app.processEvents()
    assert win.splitter.sizes()[0] >= 190, win.splitter.sizes()

    win.logs_toggle.setChecked(True)
    assert win.log_view.isVisibleTo(win) and win.logs_toggle.text() == "Hide Logs"
    win.logs_toggle.setChecked(False)
    assert win.logs_toggle.text() == "Show Logs"

    if len(sys.argv) > 1:
        win.resize(1200, 850)
        app.processEvents()
        win.grab().save(sys.argv[1])

    win.close()
    assert win.settings.value("geometry") is not None, "geometry not persisted"
    print(f"OK: {total} entries, shortcuts/list/filter/dirty/preset/tiers all good")


if __name__ == "__main__":
    main()