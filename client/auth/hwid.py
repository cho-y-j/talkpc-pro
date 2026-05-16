"""HWID 수집 — 라이선스 디바이스 묶기용.

Windows 머신 고유 식별자 (MachineGuid + 마더보드 시리얼) 해시.
재설치/재부팅에도 동일 값 (재포맷 시는 바뀜).
"""
import hashlib
import platform
import socket
import subprocess


def _read_machine_guid() -> str:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        try:
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(val)
        finally:
            winreg.CloseKey(key)
    except Exception:
        return ""


def _read_baseboard_serial() -> str:
    try:
        out = subprocess.check_output(
            ["wmic", "baseboard", "get", "serialnumber"],
            stderr=subprocess.DEVNULL, timeout=5,
        ).decode(errors="ignore")
        lines = [s.strip() for s in out.splitlines() if s.strip()]
        return lines[1] if len(lines) > 1 else ""
    except Exception:
        return ""


def get_hwid() -> str:
    """SHA-256(MachineGuid + 마더보드 시리얼 + 호스트명)[:32]"""
    parts = [
        _read_machine_guid(),
        _read_baseboard_serial(),
        socket.gethostname(),
        platform.machine(),
    ]
    raw = "|".join(parts).encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def get_hostname() -> str:
    return socket.gethostname()
