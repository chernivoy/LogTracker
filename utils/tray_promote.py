"""Win11: підвищення іконки застосунку в треї до «always show».

Windows 11 за замовчуванням ховає іконки нових застосунків у overflow
(прихована зона за шевроном ^). Офіційного API, щоб застосунок сам себе
підвищив у завжди-видиму зону, немає — Microsoft віддає це рішення
користувачу (Settings → Taskbar → Other system tray icons).

Недокументований механізм, на який спираємось: Explorer тримає стан кожної
іконки в `HKCU\\Control Panel\\NotifyIconSettings\\<id>`, де серед значень є
`ExecutablePath` (шлях до exe) і `IsPromoted` (DWORD: 1 = завжди показувати,
0/відсутнє = в overflow). Підключ `<id>` — хеш від Explorer, наперед його не
відтворити, тож він з'являється лише ПІСЛЯ першого показу іконки. Знаходимо
потрібний підключ за збігом `ExecutablePath` і ставимо `IsPromoted=1`.

Обмеження (усі свідомі; будь-який збій — тихий no-op, застосунок не страждає):
  * Тільки Windows 11. На Win10 ключ інший (зашифрований блоб IconStreams) —
    там функція нічого не знайде й тихо вийде.
  * Тільки frozen-збірка: у dev `sys.executable == python.exe`, підвищувати
    інтерпретатор немає сенсу.
  * Найперший запуск ще буде в overflow — підключа ще нема. З 2-го запуску
    (Explorer уже створив запис при першому показі) і далі — завжди видима.
  * Прапорець прив'язаний до шляху exe: перенесення/перезбірка exe в іншу
    теку = для Windows новий застосунок, видимість скидається. Тому підвищуємо
    щоразу на старті — код сам «лікує» новий шлях.
  * Механізм недокументований: формат може змінитись у майбутньому Windows,
    тому все обгорнуто в try/except.
"""

import os
import sys


def promote_tray_icon():
    """Best-effort: позначити іконку цього exe в треї як «always show» (Win11).

    Викликати ОДИН раз на старті — до того, як застосунок уперше згорнеться в
    трей: тоді `IsPromoted` уже стоїть, коли Explorer додає іконку, і вона
    з'являється одразу у видимій зоні. Нічого не повертає; про результат друкує
    в лог.
    """
    if sys.platform != "win32":
        return
    if not getattr(sys, "frozen", False):
        # dev-запуск: sys.executable — це python.exe, а не наш застосунок.
        return

    try:
        import winreg
    except ImportError:
        return

    target = os.path.normcase(os.path.abspath(sys.executable))
    root_path = r"Control Panel\NotifyIconSettings"

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, root_path) as base:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(base, index)
                except OSError:
                    break  # підключі скінчились
                index += 1
                try:
                    with winreg.OpenKey(
                        base, name, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
                    ) as entry:
                        try:
                            exe, _ = winreg.QueryValueEx(entry, "ExecutablePath")
                        except FileNotFoundError:
                            continue  # запис без ExecutablePath — не наш
                        if os.path.normcase(os.path.abspath(exe)) != target:
                            continue
                        winreg.SetValueEx(entry, "IsPromoted", 0, winreg.REG_DWORD, 1)
                        print(f"INFO: tray icon promoted (IsPromoted=1) for {exe}")
                        return
                except OSError:
                    continue  # цей підключ не відкрився — пробуємо наступний
        # Циклу кінець без збігу: підключа для нашого exe ще нема (найперший
        # запуск, іконку ще жодного разу не показували) — наступний запуск його
        # створить і підхопить.
        print("INFO: tray promote — no NotifyIconSettings entry yet (first run?)")
    except OSError as e:
        # Ключа NotifyIconSettings нема (Win10) або доступ впав — не критично.
        print(f"INFO: tray promote skipped: {e}")
