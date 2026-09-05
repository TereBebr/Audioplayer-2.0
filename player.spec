# -*- mode: python ; coding: utf-8 -*-
# Сборка onedir: .exe стартует за секунды, ничего не распаковывая при запуске.
import os
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
d, b, h = collect_all("flet")
datas += d
binaries += b
hiddenimports += h

# flet_desktop нужен как python-модуль; сам клиент Flet кладётся рядом с .exe
# в папку flet_client (см. build.ps1) и подключается через FLET_VIEW_PATH.
hiddenimports += ["flet_desktop", "vlc", "app_env", "database", "utils", "ui_utils", "gui2"]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # веб-клиент Flet (~67 МБ) — десктопной версии не нужен
        "flet_web", "flet.fastapi", "flet_cli",
        # тянутся транзитивно, плееру не нужны
        "IPython", "jedi", "parso", "matplotlib", "numpy", "scipy", "pandas",
        "PyQt5", "PyQt6", "PySide2", "PySide6", "customtkinter",
        "test", "unittest", "pydoc_data",
    ],
    noarchive=False,
    optimize=0,
)

# Официальный hook-flet.py копирует весь клиент Flet (~96 МБ) в _internal/flet_desktop/app,
# но flet 0.85 всё равно его оттуда не находит и лезет качать с GitHub. Выбрасываем дубль —
# рабочая копия клиента лежит рядом с .exe в flet_client.
_CLIENT_MARKERS = (os.path.join(".flet", "client"), "flet_desktop" + os.sep + "app")


def _drop_bundled_client(toc):
    return [e for e in toc if not any(m in e[1] or m in e[0] for m in _CLIENT_MARKERS)]


a.datas = _drop_bundled_client(a.datas)
a.binaries = _drop_bundled_client(a.binaries)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Player",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX замедляет старт и ловит ложные срабатывания антивирусов
    console=False,      # без чёрного окна консоли
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Player",
)
