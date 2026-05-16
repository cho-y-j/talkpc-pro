"""
Image Clipboard - 크로스플랫폼 이미지 클립보드 복사
Mac: osascript, Windows: PowerShell
"""

import platform
import subprocess
from pathlib import Path


def copy_image_to_clipboard(image_path: str) -> bool:
    """
    이미지 파일을 시스템 클립보드에 복사

    Args:
        image_path: 이미지 파일 경로 (PNG, JPG, BMP)

    Returns:
        성공 여부
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"이미지 파일 없음: {image_path}")

    suffix = path.suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"):
        raise ValueError(f"지원하지 않는 이미지 형식: {suffix}")

    system = platform.system()

    if system == "Darwin":
        return _copy_mac(str(path.resolve()))
    elif system == "Windows":
        return _copy_windows(str(path.resolve()))
    else:
        raise OSError(f"지원하지 않는 OS: {system}")


def _copy_mac(abs_path: str) -> bool:
    """macOS: osascript로 클립보드에 이미지 설정"""
    script = f'''
    set theFile to POSIX file "{abs_path}"
    set theImage to (read theFile as TIFF picture)
    set the clipboard to theImage
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        timeout=10, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"osascript 실패: {result.stderr.strip()}")
    return True


def _copy_windows(abs_path: str) -> bool:
    """Windows: PowerShell로 클립보드에 이미지 설정"""
    # PowerShell 경로 이스케이프
    escaped = abs_path.replace("'", "''")
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        f"$img = [System.Drawing.Image]::FromFile('{escaped}'); "
        "[System.Windows.Forms.Clipboard]::SetImage($img); "
        "$img.Dispose()"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        timeout=15, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell 실패: {result.stderr.strip()}")
    return True
