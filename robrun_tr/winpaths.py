"""Windows known folders via SHGetKnownFolderPath (no PowerShell; handles OneDrive-redirected desktops)."""
import ctypes
from ctypes import wintypes
from pathlib import Path

KNOWN_FOLDERS = {"Desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
                 "Programs": "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}"}


class _GUID(ctypes.Structure):
    _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]


def special_folder(name: str) -> Path:
    guid = _GUID()
    ctypes.oledll.ole32.CLSIDFromString(KNOWN_FOLDERS[name], ctypes.byref(guid))
    out = ctypes.c_wchar_p()
    ctypes.oledll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out))
    try:
        return Path(out.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)
