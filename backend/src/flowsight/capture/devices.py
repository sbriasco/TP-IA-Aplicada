"""Named Windows cameras, using the same DirectShow order as OpenCV capture.

Enumeration reads monikers only; it does not open a stream. Native drivers run
in a bounded helper so a stuck/crashing COM call cannot hang the API process.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import threading
import uuid
from ctypes import wintypes

from flowsight.capture.contracts import CaptureError

_discovery_lock = threading.Lock()


def list_webcams() -> list[dict]:
    if sys.platform != "win32":
        raise CaptureError("device_enumeration_unsupported")
    if not _discovery_lock.acquire(timeout=3):
        raise CaptureError("device_enumeration_failed")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "flowsight.capture.devices"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
        if result.returncode != 0 or len(result.stdout) > 65536:
            raise ValueError("Invalid discovery response")
        names = json.loads(result.stdout)
        if (
            not isinstance(names, list)
            or len(names) > 33
            or any(
                not isinstance(name, str) or not name.strip() or len(name) > 200 for name in names
            )
        ):
            raise ValueError("Invalid discovery response")
        return [
            {"device_index": index, "label": name.strip(), "verified": False}
            for index, name in enumerate(names)
        ]
    except (OSError, subprocess.SubprocessError, ValueError):
        raise CaptureError("device_enumeration_failed") from None
    finally:
        _discovery_lock.release()


class GUID(ctypes.Structure):
    _fields_ = [
        ("data1", wintypes.DWORD),
        ("data2", wintypes.WORD),
        ("data3", wintypes.WORD),
        ("data4", ctypes.c_ubyte * 8),
    ]


class VariantValue(ctypes.Union):
    _fields_ = [
        ("bstr", ctypes.c_void_p),
        ("integer", ctypes.c_int64),
        ("record", ctypes.c_void_p * 2),
    ]


class Variant(ctypes.Structure):
    _fields_ = [("kind", wintypes.WORD), ("reserved", wintypes.WORD * 3), ("value", VariantValue)]


def _guid(value):
    return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def _method(pointer, index, *argument_types):
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argument_types)(vtable[index])


def _check(result):
    if result < 0:
        raise OSError("Windows camera enumeration failed")


def _release(pointer):
    if pointer:
        _method(pointer, 2)(pointer)


def _enumerate_windows_devices():
    ole32 = ctypes.WinDLL("ole32")
    oleaut32 = ctypes.WinDLL("oleaut32")
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(GUID),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = []
    oleaut32.VariantClear.argtypes = [ctypes.POINTER(Variant)]
    device_enum, monikers = ctypes.c_void_p(), ctypes.c_void_p()
    _check(ole32.CoInitializeEx(None, 2))
    try:
        _check(
            ole32.CoCreateInstance(
                ctypes.byref(_guid("62BE5D10-60EB-11D0-BD3B-00A0C911CE86")),
                None,
                1,
                ctypes.byref(_guid("29840822-5B84-11D0-BD3B-00A0C911CE86")),
                ctypes.byref(device_enum),
            )
        )
        result = _method(
            device_enum, 3, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD
        )(
            device_enum,
            ctypes.byref(_guid("860BB310-5D01-11D0-BD3B-00A0C911CE86")),
            ctypes.byref(monikers),
            0,
        )
        if result == 1:  # S_FALSE means the device category is empty.
            return []
        _check(result)
        names = []
        while len(names) < 33:
            moniker, bag = ctypes.c_void_p(), ctypes.c_void_p()
            fetched = wintypes.ULONG()
            result = _method(
                monikers,
                3,
                wintypes.ULONG,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(wintypes.ULONG),
            )(
                monikers,
                1,
                ctypes.byref(moniker),
                ctypes.byref(fetched),
            )
            if result == 1:
                break
            _check(result)
            if not moniker or fetched.value != 1:
                raise OSError("Invalid camera moniker")
            try:
                name = f"Cámara {len(names) + 1}"
                result = _method(
                    moniker,
                    9,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.POINTER(GUID),
                    ctypes.POINTER(ctypes.c_void_p),
                )(
                    moniker,
                    None,
                    None,
                    ctypes.byref(_guid("55272A00-42CB-11CE-8135-00AA004BB851")),
                    ctypes.byref(bag),
                )
                if result >= 0 and bag:
                    variant = Variant()
                    try:
                        result = _method(
                            bag, 3, ctypes.c_wchar_p, ctypes.POINTER(Variant), ctypes.c_void_p
                        )(
                            bag,
                            "FriendlyName",
                            ctypes.byref(variant),
                            None,
                        )
                        if result >= 0 and variant.kind == 8 and variant.value.bstr:
                            native_name = ctypes.wstring_at(variant.value.bstr).strip()
                            if native_name:
                                name = native_name[:200]
                    finally:
                        oleaut32.VariantClear(ctypes.byref(variant))
                # Keep every moniker in order, even when it lacks a friendly name.
                names.append(name)
            finally:
                _release(bag)
                _release(moniker)
        return names
    finally:
        _release(monikers)
        _release(device_enum)
        ole32.CoUninitialize()


if __name__ == "__main__":
    try:
        print(json.dumps(_enumerate_windows_devices()))
    except Exception:
        raise SystemExit(1) from None
