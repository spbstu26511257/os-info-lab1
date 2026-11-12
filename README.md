# Лабораторная работа 1 — сбор информации об ОС

> **Дисклеймер.** Это учебный проект, выполненный в рамках лабораторной работы. Скрипт только читает общедоступные параметры системы, на которой его запустил сам пользователь, и сохраняет их в локальный файл. Он ничего не изменяет в системе, не требует прав администратора, не отправляет данные по сети и не предназначен для сбора информации о чужих компьютерах. Полученный `os_info.json` может содержать имя компьютера и имя пользователя — не публикуйте его без необходимости.

## Что делает скрипт

1. Определяет ОС, в которой запущен: Linux, macOS или Windows (через `platform.system()`).
2. Собирает параметры системы и оборудования.
3. Сохраняет результат в JSON-файл (по умолчанию `os_info.json` в текущей папке).

## Запуск

Нужен Python 3.6+. Установка дополнительных пакетов не требуется.

```bash
python my_script.py                 # результат в os_info.json
python my_script.py -o result.json  # свой путь к файлу
```

## Собираемые параметры

| Раздел JSON | Параметр | Описание |
|---|---|---|
| — | `collected_at` | Дата и время сбора данных |
| `os` | `name` | Название ОС (Linux / macOS / Windows) |
| `os` | `release` | Выпуск ОС (версия ядра или номер Windows) |
| `os` | `version` | Полная версия / сборка ОС |
| `os` | `architecture` | Архитектура (x86_64, arm64 и т. п.) |
| `cpu` | `model` | Модель процессора |
| `cpu` | `logical_cores` | Число логических ядер |
| — | `ram_total_gb` | Объём оперативной памяти, ГБ |
| `disk_gb` | `total`, `used`, `free` | Системный диск: всего, занято, свободно, ГБ |
| `system` | `hostname` | Имя компьютера |
| `system` | `user` | Имя текущего пользователя |
| `system` | `timezone` | Часовой пояс |
| `system` | `locale` | Язык и регион системы |
| — | `python_version` | Версия интерпретатора Python |

## Откуда берутся данные

Внешние утилиты ОС (`uname`, `systeminfo`, `wmic`, `sysctl`, `lscpu` и т. п.) **не вызываются**. Используются только стандартные модули Python:

| Данные | Linux | macOS | Windows |
|---|---|---|---|
| Модель процессора | файл `/proc/cpuinfo` | `sysctlbyname` из libc через `ctypes` | реестр через `winreg` |
| Объём ОЗУ | файл `/proc/meminfo` | `sysctlbyname` через `ctypes` | `GetPhysicallyInstalledSystemMemory` (kernel32) через `ctypes` |
| ОС, архитектура, версия Python | модуль `platform` | `platform` | `platform` |
| Ядра процессора | `os.cpu_count()` | `os.cpu_count()` | `os.cpu_count()` |
| Диск | `shutil.disk_usage` | `shutil.disk_usage` | `shutil.disk_usage` |
| Имя компьютера, пользователь | `socket`, `getpass` | `socket`, `getpass` | `socket`, `getpass` |
| Часовой пояс, локаль | `time`, `locale` | `time`, `locale` | `time`, `locale` |

Внешние модули не используются, поэтому обоснование их выбора не требуется.

## Пример результата

```json
{
    "collected_at": "2026-11-12T17:49:22",
    "os": {
        "name": "Linux",
        "release": "6.18.44",
        "version": "#1 SMP PREEMPT_DYNAMIC",
        "architecture": "x86_64"
    },
    "cpu": {
        "model": "Intel(R) Xeon(R) Processor @ 2.10GHz",
        "logical_cores": 2
    },
    "ram_total_gb": 7.83,
    "disk_gb": {
        "total": 251.97,
        "used": 11.92,
        "free": 30.01
    },
    "system": {
        "hostname": "my-pc",
        "user": "student",
        "timezone": "MSK",
        "locale": "ru_RU"
    },
    "python_version": "3.13.18"
}
```

Если какой-то параметр получить не удалось, вместо значения записывается `null`.

## Совместимость

Скрипт рассчитан на работу в Linux, macOS и Windows.
