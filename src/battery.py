"""블루투스 장치 배터리 조회 모듈.

PowerShell/레지스트리 대신 SetupAPI를 ctypes로 직접 호출한다.
배터리 값은 드라이버가 동적으로 제공하므로 API를 통해야만 읽힌다.
프로세스 생성이 없어서 즉각 응답하고 리소스를 거의 안 씀.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass

_setupapi = ctypes.WinDLL('setupapi', use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', ctypes.c_uint32),
        ('Data2', ctypes.c_uint16),
        ('Data3', ctypes.c_uint16),
        ('Data4', ctypes.c_uint8 * 8),
    ]


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [('fmtid', GUID), ('pid', ctypes.c_uint32)]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ('cbSize',    ctypes.c_uint32),
        ('ClassGuid', GUID),
        ('DevInst',   ctypes.c_uint32),
        ('Reserved',  ctypes.c_void_p),
    ]


_DIGCF_PRESENT      = 0x00000002
_INVALID_HANDLE     = ctypes.c_void_p(-1).value
_SPDRP_FRIENDLYNAME = 0x0000000C

_BT_CLASS = GUID(
    0xE0CBF06C, 0xCD8B, 0x4647,
    (ctypes.c_uint8 * 8)(0xBB, 0x8A, 0x26, 0x3B, 0x43, 0xF0, 0xF9, 0x74),
)

_BATTERY_KEY = DEVPROPKEY(
    GUID(
        0x104EA319, 0x6EE2, 0x4701,
        (ctypes.c_uint8 * 8)(0xBD, 0x47, 0x8D, 0xDB, 0xF4, 0x25, 0xBB, 0xE5),
    ),
    2,
)

_GetClassDevs = _setupapi.SetupDiGetClassDevsW
_GetClassDevs.argtypes = [ctypes.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]
_GetClassDevs.restype  = ctypes.c_void_p

_EnumDeviceInfo = _setupapi.SetupDiEnumDeviceInfo
_EnumDeviceInfo.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
_EnumDeviceInfo.restype  = wt.BOOL

_GetDeviceProp = _setupapi.SetupDiGetDevicePropertyW
_GetDeviceProp.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(SP_DEVINFO_DATA),
    ctypes.POINTER(DEVPROPKEY),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint8),
    wt.DWORD,
    ctypes.POINTER(wt.DWORD),
    wt.DWORD,
]
_GetDeviceProp.restype = wt.BOOL

_GetRegProp = _setupapi.SetupDiGetDeviceRegistryPropertyW
_GetRegProp.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(SP_DEVINFO_DATA),
    wt.DWORD,
    ctypes.POINTER(wt.DWORD),
    ctypes.POINTER(ctypes.c_uint8),
    wt.DWORD,
    ctypes.POINTER(wt.DWORD),
]
_GetRegProp.restype = wt.BOOL

_DestroyList = _setupapi.SetupDiDestroyDeviceInfoList
_DestroyList.argtypes = [ctypes.c_void_p]
_DestroyList.restype  = wt.BOOL


@dataclass(frozen=True)
class Device:
    name: str
    battery: int  # 0-100


def fetch_devices() -> list[Device]:
    """현재 연결된 블루투스 장치 중 배터리가 보고되는 것만 반환."""
    hdevinfo = _GetClassDevs(ctypes.byref(_BT_CLASS), None, None, _DIGCF_PRESENT)
    if hdevinfo == _INVALID_HANDLE:
        return []

    devices: list[Device] = []
    idx = 0

    while True:
        devinfo = SP_DEVINFO_DATA()
        devinfo.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)

        if not _EnumDeviceInfo(hdevinfo, idx, ctypes.byref(devinfo)):
            break
        idx += 1

        prop_type = ctypes.c_uint32(0)
        bat_buf   = (ctypes.c_uint8 * 4)()
        req       = wt.DWORD(0)
        if not _GetDeviceProp(
            hdevinfo, ctypes.byref(devinfo), ctypes.byref(_BATTERY_KEY),
            ctypes.byref(prop_type), bat_buf, ctypes.sizeof(bat_buf),
            ctypes.byref(req), 0,
        ):
            continue

        battery = int(bat_buf[0])

        reg_type  = wt.DWORD(0)
        name_buf  = (ctypes.c_uint8 * 512)()
        req2      = wt.DWORD(0)
        if not _GetRegProp(
            hdevinfo, ctypes.byref(devinfo), _SPDRP_FRIENDLYNAME,
            ctypes.byref(reg_type), name_buf, ctypes.sizeof(name_buf),
            ctypes.byref(req2),
        ):
            continue

        name = bytes(name_buf).decode('utf-16-le').split('\x00')[0]
        if name:
            devices.append(Device(name=name, battery=battery))

    _DestroyList(hdevinfo)
    return devices


if __name__ == "__main__":
    results = fetch_devices()
    if not results:
        print("배터리 정보가 있는 블루투스 장치를 찾지 못했습니다.")
    for d in results:
        print(f"{d.name:<30} {d.battery:>3}%")