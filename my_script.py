#!/usr/bin/env python3
"""
Лабораторная работа 1: сбор информации об операционной системе.

Скрипт:
  1. определяет, в какой ОС он запущен (Linux / macOS / Windows);
  2. собирает параметры текущей ОС и железа;
  3. сохраняет результат в JSON-файл.

Используются только стандартные модули Python. Внешние утилиты ОС
(uname, systeminfo, wmic, sysctl, lscpu и т.п.) НЕ вызываются:
данные берутся из модулей platform/os/socket, системных файлов (/proc)
и системных библиотек через ctypes / реестр Windows через winreg.

Запуск:
    python my_script.py                 # результат в os_info.json
    python my_script.py -o result.json  # свой путь к файлу
"""

import argparse
import ctypes
import ctypes.util
import datetime
import getpass
import json
import locale
import os
import platform
import shutil
import socket
import sys
import time

SCRIPT_VERSION = "1.0"


# ---------------------------------------------------------------------------
# 1. Определение ОС
# ---------------------------------------------------------------------------
def detect_os():
    """Возвращает 'Linux', 'macOS', 'Windows' или исходное имя системы."""
    system = platform.system()
    if system == "Linux":
        return "Linux"
    if system == "Darwin":
        return "macOS"
    if system == "Windows":
        return "Windows"
    return system or "Unknown"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
def safe(func, default=None):
    """Выполняет func(); при любой ошибке возвращает default.
    Нужна, чтобы отсутствие одного параметра не ломало весь сбор."""
    try:
        return func()
    except Exception:
        return default


def bytes_to_gb(value):
    return round(value / 1024 ** 3, 2) if value is not None else None


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


# --- macOS: sysctlbyname из libc через ctypes (не утилита sysctl) ----------
def _mac_libc():
    return ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


def mac_sysctl_str(name):
    libc = _mac_libc()
    size = ctypes.c_size_t(0)
    if libc.sysctlbyname(name.encode(), None, ctypes.byref(size), None, 0) != 0:
        return None
    buf = ctypes.create_string_buffer(size.value)
    if libc.sysctlbyname(name.encode(), buf, ctypes.byref(size), None, 0) != 0:
        return None
    return buf.value.decode(errors="replace")


def mac_sysctl_int(name):
    libc = _mac_libc()
    value = ctypes.c_uint64(0)
    size = ctypes.c_size_t(ctypes.sizeof(value))
    if libc.sysctlbyname(name.encode(), ctypes.byref(value), ctypes.byref(size), None, 0) != 0:
        return None
    return value.value


def mac_boot_time():
    class Timeval(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]

    libc = _mac_libc()
    tv = Timeval()
    size = ctypes.c_size_t(ctypes.sizeof(tv))
    if libc.sysctlbyname(b"kern.boottime", ctypes.byref(tv), ctypes.byref(size), None, 0) != 0:
        return None
    return float(tv.tv_sec)


# --- Windows: WinAPI через ctypes и реестр через winreg --------------------
def win_memory():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return stat.ullTotalPhys, stat.ullAvailPhys


def win_uptime_seconds():
    kernel32 = ctypes.windll.kernel32
    kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    return kernel32.GetTickCount64() / 1000.0


def win_registry_value(path, name):
    import winreg  # есть только в Windows
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
        return winreg.QueryValueEx(key, name)[0]


# ---------------------------------------------------------------------------
# 2. Сбор параметров
# ---------------------------------------------------------------------------
def collect_os_info(os_family):
    info = {
        "family": os_family,
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "pretty_name": None,
    }

    if os_family == "Linux":
        release = safe(platform.freedesktop_os_release)  # Python 3.10+
        if release is None:  # запасной вариант: читаем файл сами
            release = {}
            text = safe(lambda: read_text("/etc/os-release"), "")
            for line in text.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    release[k] = v.strip('"')
        info["distribution"] = {
            "id": release.get("ID"),
            "name": release.get("NAME"),
            "version": release.get("VERSION_ID"),
        }
        info["pretty_name"] = release.get("PRETTY_NAME")
        info["kernel"] = platform.release()

    elif os_family == "macOS":
        mac_version = platform.mac_ver()[0]
        info["macos_version"] = mac_version
        info["darwin_kernel"] = platform.release()
        info["pretty_name"] = f"macOS {mac_version}"

    elif os_family == "Windows":
        release, version, _, _ = platform.win32_ver()
        build = safe(lambda: int(version.split(".")[-1]))
        # Старые версии Python возвращают "10" и для Windows 11 — различаем по номеру сборки
        if release == "10" and build is not None and build >= 22000:
            release = "11"
        info["windows_release"] = release
        info["build"] = build
        info["edition"] = safe(platform.win32_edition)
        info["display_version"] = safe(lambda: win_registry_value(
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "DisplayVersion"))
        info["pretty_name"] = f"Windows {release} {info['edition'] or ''}".strip()

    return info


def collect_cpu_info(os_family):
    model = None
    if os_family == "Linux":
        text = safe(lambda: read_text("/proc/cpuinfo"), "")
        fields = {}
        for line in text.splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() not in fields:
                fields[key.strip()] = value.strip()
        # x86: "model name"; ARM: "Hardware" или "Model" (Raspberry Pi и т.п.)
        model = fields.get("model name") or fields.get("Hardware") or fields.get("Model")
    elif os_family == "macOS":
        model = safe(lambda: mac_sysctl_str("machdep.cpu.brand_string"))
    elif os_family == "Windows":
        model = safe(lambda: win_registry_value(
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString"))
        if model:
            model = model.strip()

    return {
        "model": model or platform.processor() or None,
        "architecture": platform.machine(),
        "bits": platform.architecture()[0],
        "logical_cores": os.cpu_count(),
    }


def collect_memory_info(os_family):
    total = available = None
    if os_family == "Linux":
        meminfo = {}
        for line in safe(lambda: read_text("/proc/meminfo"), "").splitlines():
            key, _, rest = line.partition(":")
            parts = rest.split()
            if parts:
                meminfo[key] = int(parts[0]) * 1024  # значения в kB
        total = meminfo.get("MemTotal")
        available = meminfo.get("MemAvailable")
    elif os_family == "macOS":
        total = safe(lambda: mac_sysctl_int("hw.memsize"))
    elif os_family == "Windows":
        total, available = safe(win_memory, (None, None))

    used_percent = None
    if total and available is not None:
        used_percent = round((total - available) / total * 100, 1)

    return {
        "total_gb": bytes_to_gb(total),
        "available_gb": bytes_to_gb(available),
        "used_percent": used_percent,
    }


def collect_disk_info(os_family):
    root = os.environ.get("SystemDrive", "C:") + "\\" if os_family == "Windows" else "/"
    usage = safe(lambda: shutil.disk_usage(root))
    if usage is None:
        return {"path": root}
    return {
        "path": root,
        "total_gb": bytes_to_gb(usage.total),
        "used_gb": bytes_to_gb(usage.used),
        "free_gb": bytes_to_gb(usage.free),
        # как в df: доля от места, доступного пользователю (без резерва ФС)
        "used_percent": round(usage.used / (usage.used + usage.free) * 100, 1),
    }


def collect_uptime_info(os_family):
    uptime = None
    if os_family == "Linux":
        uptime = safe(lambda: float(read_text("/proc/uptime").split()[0]))
    elif os_family == "macOS":
        boot = safe(mac_boot_time)
        if boot:
            uptime = time.time() - boot
    elif os_family == "Windows":
        uptime = safe(win_uptime_seconds)

    if uptime is None:
        return {"uptime_seconds": None, "boot_time": None}
    boot_time = datetime.datetime.now().astimezone() - datetime.timedelta(seconds=uptime)
    return {
        "uptime_seconds": int(uptime),
        "uptime_human": str(datetime.timedelta(seconds=int(uptime))),
        "boot_time": boot_time.isoformat(timespec="seconds"),
    }


def get_local_ip():
    # connect() для UDP-сокета не отправляет пакетов, а лишь выбирает
    # интерфейс по таблице маршрутизации — так узнаём основной IP.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def collect_network_info():
    hostname = socket.gethostname()
    return {
        "hostname": hostname,
        "fqdn": safe(socket.getfqdn),
        "local_ip": safe(get_local_ip),
    }


def collect_user_info():
    return {
        "username": safe(getpass.getuser),
        "home_dir": os.path.expanduser("~"),
        "shell": os.environ.get("SHELL") or os.environ.get("COMSPEC"),
        "is_admin": safe(is_admin),
    }


def is_admin():
    if hasattr(os, "geteuid"):
        return os.geteuid() == 0
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def collect_locale_info():
    lang = safe(lambda: locale.getlocale()[0])
    return {
        "locale": lang,
        "preferred_encoding": locale.getpreferredencoding(False),
        "filesystem_encoding": sys.getfilesystemencoding(),
        "timezone": time.tzname[time.localtime().tm_isdst > 0],
        "utc_offset": datetime.datetime.now().astimezone().strftime("%z"),
    }


def collect_python_info():
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
    }


def collect_all():
    os_family = detect_os()
    return {
        "meta": {
            "script_version": SCRIPT_VERSION,
            "collected_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        "os": collect_os_info(os_family),
        "cpu": collect_cpu_info(os_family),
        "memory": collect_memory_info(os_family),
        "disk": collect_disk_info(os_family),
        "uptime": collect_uptime_info(os_family),
        "network": collect_network_info(),
        "user": collect_user_info(),
        "locale": collect_locale_info(),
        "python": collect_python_info(),
    }


# ---------------------------------------------------------------------------
# 3. Запись в JSON
# ---------------------------------------------------------------------------
def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def main():
    parser = argparse.ArgumentParser(description="Сбор информации об ОС в JSON")
    parser.add_argument("-o", "--output", default="os_info.json",
                        help="путь к выходному файлу (по умолчанию os_info.json)")
    args = parser.parse_args()

    data = collect_all()
    save_json(data, args.output)

    print(f"Обнаружена ОС: {data['os']['pretty_name'] or data['os']['family']}")
    print(f"Результат сохранён в: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
