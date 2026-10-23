#!/usr/bin/env python3
"""Брендирование клиента «Астральный Порт».

Запускается в GitHub Actions после скачивания исходников RustDesk,
до компиляции. Меняет сервер, ключ, имя программы, цвета, тему по
умолчанию и копирует иконки и логотипы из папки branding/.

Каждая замена проверяет, что исходная строка найдена ровно столько раз,
сколько ожидается. Если исходники RustDesk изменились и строка не
найдена, сборка останавливается с понятной ошибкой, а не собирает
молча «полу-брендированный» клиент.
"""
import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------- настройки
APP_NAME = "AstralPort"            # внутреннее имя: латиница, без пробелов
DISPLAY_NAME = "Астральный Порт"   # имя в заголовках окон

ACCENT = "2F9E4F"      # основной зелёный: кнопки, выделения
ID_COLOR = "4ADE80"    # светло-зелёный: ваш ID на главном экране
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
BRAND = Path(__file__).resolve().parent
errors = []


def fail(msg):
    print(f"::error::{msg}")
    errors.append(msg)


def patch(rel_path, replacements):
    """replacements: список (старое, новое, ожидаемое_число_вхождений)."""
    path = ROOT / rel_path
    if not path.is_file():
        fail(f"{rel_path}: file not found")
        return
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    for old, new, expected in replacements:
        found = text.count(old)
        if found != expected:
            fail(f"{rel_path}: expected {expected} match(es), found {found}: {old[:70]!r}")
            continue
        text = text.replace(old, new)
        print(f"  ok  {rel_path}: {old.splitlines()[0][:60]!r}")
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def wide_literal(s):
    """Строка для C++ в виде L"\\uXXXX..." без кириллицы в исходнике."""
    return 'L"' + "".join(c if ord(c) < 128 else f"\\u{ord(c):04x}" for c in s) + '"'


def copy(src_name, dst_rel):
    src = BRAND / src_name
    dst = ROOT / dst_rel
    if not src.is_file():
        fail(f"branding/{src_name}: file not found")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"  ok  copy {src_name} -> {dst_rel}")


def main():
    server = os.environ.get("MY_SERVER", "").strip()
    key = os.environ.get("MY_KEY", "").strip()
    if not server or not key:
        fail("Secrets RENDEZVOUS_SERVER or RS_PUB_KEY are empty")
        return

    print("== server, key, app name")
    patch("libs/hbb_common/src/config.rs", [
        ('pub const RENDEZVOUS_SERVERS: &[&str] = &["rs-ny.rustdesk.com"];',
         f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{server}"];', 1),
        ('pub const RS_PUB_KEY: &str = "OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw=";',
         f'pub const RS_PUB_KEY: &str = "{key}";', 1),
        ('pub static ref APP_NAME: RwLock<String> = RwLock::new("RustDesk".to_owned());',
         f'pub static ref APP_NAME: RwLock<String> = RwLock::new("{APP_NAME}".to_owned());', 1),
        # Без этого программа считает, что работает через публичный сервер:
        # показывает подсказку «настройте собственный сервер» и урезает
        # качество/FPS, как для публичных серверов RustDesk.
        ('pub static ref PROD_RENDEZVOUS_SERVER: RwLock<String> = RwLock::new("".to_owned());',
         f'pub static ref PROD_RENDEZVOUS_SERVER: RwLock<String> = RwLock::new("{server}".to_owned());', 1),
    ])

    print("== colors, dark theme, window title")
    patch("flutter/lib/common.dart", [
        ("static const Color accent = Color(0xFF0071FF);",
         f"static const Color accent = Color(0xFF{ACCENT});", 1),
        ("static const Color accent50 = Color(0x770071FF);",
         f"static const Color accent50 = Color(0x77{ACCENT});", 1),
        ("static const Color accent80 = Color(0xAA0071FF);",
         f"static const Color accent80 = Color(0xAA{ACCENT});", 1),
        ("static const Color idColor = Color(0xFF00B6F0);",
         f"static const Color idColor = Color(0xFF{ID_COLOR});", 1),
        ("static const Color button = Color(0xFF2C8CFF);",
         f"static const Color button = Color(0xFF{ACCENT});", 1),
        ("  return Color(0xFF2C8CFF);\n",
         f"  return Color(0xFF{ACCENT});\n", 1),
        ("primary: Colors.blue", "primary: accent", 2),
        ('      case "dark":\n        return ThemeMode.dark;\n      default:\n        return ThemeMode.system;',
         '      case "dark":\n        return ThemeMode.dark;\n      case "":\n        return ThemeMode.dark;\n'
         '      default:\n        return ThemeMode.system;', 1),
        ("String getWindowName({WindowType? overrideType}) {\n  final name = bind.mainGetAppNameSync();",
         f"String getWindowName({{WindowType? overrideType}}) {{\n  final name = '{DISPLAY_NAME}';", 1),
    ])

    # Главное окно теперь называется DISPLAY_NAME. Windows ищет уже
    # открытую копию программы по заголовку окна, поэтому меняем и поиск.
    print("== windows runner")
    patch("flutter/windows/runner/main.cpp", [
        ("  HWND hwnd = ::FindWindowW(getWindowClassName(), app_name.c_str());",
         f"  std::wstring display_name = {wide_literal(DISPLAY_NAME)};\n"
         "  HWND hwnd = ::FindWindowW(getWindowClassName(), display_name.c_str());", 1),
        ("    window_title = app_name;\n", "    window_title = display_name;\n", 1),
    ])
    patch("src/core_main.rs", [
        ("            &crate::platform::FLUTTER_RUNNER_WIN32_WINDOW_CLASS,\n"
         "            &crate::get_app_name(),",
         "            &crate::platform::FLUTTER_RUNNER_WIN32_WINDOW_CLASS,\n"
         f'            "{DISPLAY_NAME}",', 1),
    ])
    # Установщик ищет в папке установки {APP_NAME}.exe, а сборка кладёт
    # туда rustdesk.exe. Обновление (update_me) уже переименовывает файл,
    # а установка (install_me) — нет; добавляем то же переименование.
    patch("src/platform/windows.rs", [
        ('md \\"{path}\\"\n{copy_exe}\nreg add {subkey} /f\n',
         'md \\"{path}\\"\n{copy_exe}\n{rename_exe}\nreg add {subkey} /f\n', 1),
        ("        copy_exe = copy_exe_cmd(&src_exe, &exe, &path)?,\n"
         "        import_config = get_import_config(&exe),",
         "        copy_exe = copy_exe_cmd(&src_exe, &exe, &path)?,\n"
         "        rename_exe = rename_exe_cmd(&src_exe, &path)?,\n"
         "        import_config = get_import_config(&exe),", 1),
    ])
    # Главная надёжная защита: в самораспаковывающийся exe кладём копию
    # rustdesk.exe под именем {APP_NAME}.exe и запускаем именно её. Тогда
    # программа с первого запуска работает как {APP_NAME}.exe, и установщик
    # находит файл с ожидаемым именем. rustdesk.exe остаётся рядом, потому
    # что его ищет сборка MSI.
    patch("libs/portable/generate.py", [
        ("    folder = options.folder or './rustdesk'\n",
         "    folder = options.folder or './rustdesk'\n"
         "    _brand_src = os.path.join(folder, 'rustdesk.exe')\n"
         f"    _brand_dst = os.path.join(folder, '{APP_NAME}.exe')\n"
         "    if os.path.exists(_brand_src):\n"
         "        import shutil\n"
         "        shutil.copyfile(_brand_src, _brand_dst)\n"
         f"        print('Branding: copied rustdesk.exe -> {APP_NAME}.exe')\n"
         # Только замена имени в строке: os.path.join на Windows вставил бы
         # обратный слеш, и проверка «файл внутри папки» ниже не проходила.
         "    _brand_exe = options.executable or ''\n"
         "    if _brand_exe.replace('\\\\', '/').split('/')[-1].lower() == 'rustdesk.exe':\n"
         f"        options.executable = _brand_exe[:-len('rustdesk.exe')] + '{APP_NAME}.exe'\n",
         1),
    ])
    patch("flutter/windows/runner/Runner.rc", [
        ('VALUE "FileDescription", "RustDesk Remote Desktop" "\\0"',
         f'VALUE "FileDescription", "{APP_NAME} Remote Desktop" "\\0"', 1),
        ('VALUE "ProductName", "RustDesk" "\\0"',
         f'VALUE "ProductName", "{APP_NAME}" "\\0"', 1),
    ])

    print("== icons and logos")
    for dst in ("res/icon.ico",
                "flutter/windows/runner/resources/app_icon.ico",
                "flutter/assets/icon.ico"):
        copy("icon.ico", dst)
    copy("tray-icon.ico", "res/tray-icon.ico")
    copy("icon.png", "res/icon.png")
    copy("icon.png", "flutter/assets/icon.png")
    for name in ("32x32.png", "64x64.png", "128x128.png", "128x128@2x.png"):
        copy(name, f"res/{name}")
    for name in ("logo.png", "logo_light.png", "logo_dark.png"):
        copy(name, f"flutter/assets/{name}")


if __name__ == "__main__":
    main()
    if errors:
        print(f"\nBranding FAILED: {len(errors)} problem(s)")
        sys.exit(1)
    print("\nBranding applied: Astral Port")
