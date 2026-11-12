#!/usr/bin/env python3
"""Лаба 1: определяет ОС, собирает её параметры и сохраняет в JSON.
Только стандартные модули Python, утилиты ОС не вызываются.
Запуск: python my_script.py [-o файл.json]"""

import argparse, ctypes, ctypes.util, datetime, getpass, json, locale, os, platform, shutil, socket, time

OS = platform.system()  # 'Linux', 'Darwin' (macOS) или 'Windows'


def read_proc(path, key):  # Linux: ищем строку в файле из /proc
    with open(path, encoding="utf-8") as f:
        return next(l.split(":", 1)[1].strip() for l in f if l.startswith(key))


def mac_sysctl(name, ctype=None):  # macOS: sysctlbyname из libc
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    size = ctypes.c_size_t(256)
    buf = ctype() if ctype else ctypes.create_string_buffer(256)
    libc.sysctlbyname(name.encode(), ctypes.byref(buf), ctypes.byref(size), None, 0)
    return buf.value if ctype else buf.value.decode()


def cpu_model():
    try:
        if OS == "Linux":
            return read_proc("/proc/cpuinfo", "model name")
        if OS == "Darwin":
            return mac_sysctl("machdep.cpu.brand_string")
        if OS == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    except Exception:
        return platform.processor() or None


def ram_bytes():
    try:
        if OS == "Linux":
            return int(read_proc("/proc/meminfo", "MemTotal").split()[0]) * 1024
        if OS == "Darwin":
            return mac_sysctl("hw.memsize", ctypes.c_uint64)
        if OS == "Windows":
            mem = ctypes.c_ulonglong()
            ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(mem))
            return mem.value * 1024
    except Exception:
        return None


def gb(x):
    return round(x / 1024 ** 3, 2) if x else None


def collect():
    disk = shutil.disk_usage(os.path.abspath(os.sep))
    return {
        "collected_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "os": {"name": {"Darwin": "macOS"}.get(OS, OS), "release": platform.release(),
               "version": platform.version(), "architecture": platform.machine()},
        "cpu": {"model": cpu_model(), "logical_cores": os.cpu_count()},
        "ram_total_gb": gb(ram_bytes()),
        "disk_gb": {"total": gb(disk.total), "used": gb(disk.used), "free": gb(disk.free)},
        "system": {"hostname": socket.gethostname(), "user": getpass.getuser(),
                   "timezone": time.tzname[0], "locale": locale.getlocale()[0]},
        "python_version": platform.python_version(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Сбор информации об ОС")
    parser.add_argument("-o", "--output", default="os_info.json")
    out = parser.parse_args().output
    data = collect()
    print("Скрипт запущен в ОС:", data["os"]["name"])
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print("Результат сохранён в", out)
