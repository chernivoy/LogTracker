import os
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from config_manager import ConfigManager
from ui.ui_assets import APP_ICO_PATH
from ui.window_handler import WindowHandler
from utils import rdp


class _PathTooltip:
    """Підказка з повним вмістом поля при наведенні курсора.

    CustomTkinter не має вбудованих тултіпів, тож малюємо власний
    overrideredirect-Toplevel під полем зі СВІЖИМ текстом (entry.get() читаємо
    при кожному наведенні, бо шлях міг змінитися через Browse). Порожнє поле
    підказки не показує. Ховаємо на виході курсора, кліку та знищенні поля.
    """

    def __init__(self, entry, font):
        self._entry = entry
        self._base_font = font  # темовий спек у пунктах — лише як фолбек
        self._tip = None
        entry.bind("<Enter>", self._show, add="+")
        entry.bind("<Leave>", self._hide, add="+")
        entry.bind("<ButtonPress>", self._hide, add="+")
        entry.bind("<Destroy>", self._hide, add="+")

    def _show(self, _event=None):
        if self._tip is not None:
            return
        text = self._entry.get().strip()
        if not text:
            return  # порожнє поле — показувати нічого
        x = self._entry.winfo_rootx() + 8
        y = self._entry.winfo_rooty() + self._entry.winfo_height() + 4

        tip = tk.Toplevel(self._entry)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tip, text=text, justify="left",
            background="#1e1e1e", foreground="#f5f5f5",
            relief="solid", borderwidth=1, font=self._resolve_font(),
            padx=6, pady=3,
        ).pack()
        self._tip = tip

    def _resolve_font(self):
        """Спек шрифту для нативного tk.Label, узгоджений з DPI.

        Плаский кортеж ('Inter', 13) — це ПУНКТИ, і Tk під DPI-awareness сам
        домножує їх на масштаб дисплея → на high-DPI текст виходив завеликим.
        Беремо вже масштабований CTk спек прямо з внутрішнього поля
        (cget('font') віддає піксельний розмір, напр. 'Inter -26'), тож тултіп
        збігається з текстом поля за кеглем і DPI. Фолбек відтворює формулу CTk
        вручну: піксельний (від'ємний) розмір = -round(base * scale).
        """
        try:
            return self._entry._entry.cget("font")
        except Exception:
            scale = WindowHandler._window_scale(self._entry)
            fam, size = self._base_font[0], self._base_font[1]
            return (fam, -round(abs(size) * scale), *self._base_font[2:])

    def _hide(self, _event=None):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


class SettingsWindow:
    """Модальне вікно налаштування шляхів.

    Стиль повністю береться з поточної теми через групу ключів settings_* —
    ті самі, що є в усіх темах (контракт: набір ключів однаковий скрізь). Тож
    вікно візуально належить до того ж застосунку, що й головне вікно з полем
    помилки, і виглядає коректно в кожній темі. Тема застосовується один раз
    при відкритті: вікно модальне (grab_set), тож змінити тему, поки воно
    відкрите, неможливо — живого оновлення стилю не потрібно.
    """

    # Колір повідомлення про помилку валідації. Фіксований, а не з теми: це
    # службовий індикатор стану, а не частина палітри, і читається на фоні
    # всіх трьох тем (світлій, темній, graphite). Заводити заради нього ключ
    # у theme-контракт (довелося б додати в кожну тему) не варто.
    _ERROR_COLOR = "#e06c75"

    # Дефолтний ЛОГІЧНИЙ розмір вікна (CTk домножить на масштаб DPI сам).
    # Висота підібрана так, щоб уся вертикальна розмітка — дві пари
    # підпис+поле, рядок статусу валідації і дві кнопки — уміщалась, і Save/
    # Cancel були повністю видні на мінімальному розмірі. Використовується і
    # для minsize, і для дефолтної геометрії, щоб вони не розходились.
    _DEFAULT_WIDTH = 400
    _DEFAULT_HEIGHT = 310

    @staticmethod
    def open_settings_window(app):
        """Відкриває вікно налаштувань для шляхів, стилізоване під поточну тему."""
        # Guard від другого вікна: обидва роблять grab_set() і стекалися б,
        # перехоплюючи фокус одне в одного. Наявне — просто піднімаємо.
        existing = getattr(app, "_settings_window", None)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return

        theme = app.theme_manager.current_theme_data

        window = ctk.CTkToplevel(app.root, fg_color=theme["settings_bg"])
        window.title("Path settings")
        app._settings_window = window

        SettingsWindow._apply_deferred_icon(window)

        # Розмір фіксований у мінімальному: min == max + resizable(False).
        # Вікно вміщає весь контент і розтягувати його нема сенсу — ресайз лише
        # плутав би. Обмеження ставимо ДО геометрії, тож навіть якщо в ini лежить
        # старий (більший) розмір, Tk одразу затисне його до фіксованого;
        # позицію (де користувач лишив вікно) при цьому зберігаємо.
        w, h = SettingsWindow._DEFAULT_WIDTH, SettingsWindow._DEFAULT_HEIGHT
        window.minsize(w, h)
        window.maxsize(w, h)
        window.resizable(False, False)
        SettingsWindow._apply_geometry(window)
        window.grab_set()  # Заблокувати інші вікна до закриття цього

        source_entry = SettingsWindow._add_labeled_entry(
            window, theme, "Path to source directory:", app.source_directory)
        destination_entry = SettingsWindow._add_labeled_entry(
            window, theme, "Path to destination directory:", app.destination_directory)

        # Рядок для повідомлень валідації: доти порожній і місця майже не
        # займає. save_settings пише сюди текст замість мовчазного закриття.
        status_label = ctk.CTkLabel(
            window, text="", text_color=SettingsWindow._ERROR_COLOR,
            font=theme["settings_font"], wraplength=360, justify="center")
        status_label.pack(pady=(4, 0))
        window._status_label = status_label

        def _save():
            SettingsWindow.save_settings(
                app, window, source_entry.get(), destination_entry.get())

        SettingsWindow._add_button(window, theme, "Save", pady=10, command=_save)
        SettingsWindow._add_button(
            window, theme, "Cancel", pady=5, command=window.destroy)

        SettingsWindow._bind_geometry_autosave(window)
        SettingsWindow._bind_keyboard(window, _save)
        source_entry.focus_set()

    # ---- Побудова стилізованих під тему віджетів ----

    @staticmethod
    def _add_labeled_entry(window, theme, label_text, value):
        """Підпис + рядок «поле вводу + кнопка вибору теки», у стилі теми.
        Повертає поле вводу."""
        ctk.CTkLabel(
            window,
            text=label_text,
            text_color=theme["settings_text_color"],
            font=theme["settings_font"],
        ).pack(pady=10)

        # Поле і кнопка Browse — в одному прозорому рядку, поруч.
        row = ctk.CTkFrame(window, fg_color="transparent")
        row.pack(pady=5)

        entry = ctk.CTkEntry(
            row,
            width=300,
            fg_color=theme["settings_entry_fg_color"],
            text_color=theme["settings_text_color"],
            border_color=theme["settings_entry_border_color"],
            font=theme["settings_font"],
        )
        entry.insert(0, value)
        entry.pack(side="left")

        ctk.CTkButton(
            row,
            text="Browse",
            width=70,
            command=lambda: SettingsWindow._browse_directory(window, entry),
            fg_color=theme["settings_button_fg_color"],
            hover_color=theme["settings_button_hover_color"],
            text_color=theme["settings_button_text_color"],
            font=theme["settings_font"],
        ).pack(side="left", padx=(6, 0))

        # Повний шлях часто ширший за поле (300px) — показуємо його підказкою
        # при наведенні, щоб було видно «хвіст» без прокрутки поля.
        _PathTooltip(entry, theme["settings_font"])

        return entry

    @staticmethod
    def _browse_directory(window, entry):
        """Відкриває нативний діалог вибору теки і вписує результат у поле.

        Стартуємо з теки, яка вже в полі (якщо вона існує). grab_set на вікні
        тимчасово знімаємо: нативний діалог вибору теки на Windows — окреме
        вікно ОС, і локальний grab батька може перехопити в нього фокус.
        Порожній результат означає скасування — поле не чіпаємо.
        """
        current = entry.get().strip().strip('"')
        kwargs = {"parent": window, "title": "Select folder"}
        if os.path.isdir(current):
            kwargs["initialdir"] = current

        try:
            window.grab_release()
        except Exception:
            pass
        try:
            path = filedialog.askdirectory(**kwargs)
        finally:
            try:
                if window.winfo_exists():
                    window.grab_set()
            except Exception:
                pass

        if path:  # '' = користувач скасував діалог
            entry.delete(0, "end")
            entry.insert(0, os.path.normpath(path))

    @staticmethod
    def _add_button(window, theme, text, command, pady):
        """Кнопка Save/Cancel у стилі теми."""
        ctk.CTkButton(
            window,
            text=text,
            command=command,
            fg_color=theme["settings_button_fg_color"],
            hover_color=theme["settings_button_hover_color"],
            text_color=theme["settings_button_text_color"],
            font=theme["settings_font"],
        ).pack(pady=pady)

    # ---- Вікно: іконка, геометрія, автозбереження позиції, клавіатура ----

    @staticmethod
    def _apply_deferred_icon(window):
        """Ставить іконку заголовка з відкладенням.

        CTkToplevel сам виставляє свою іконку ~через 200 мс після створення,
        тож ранній iconbitmap він затер би. try/except — бо відсутній .ico
        кинув би TclError.
        """
        def _apply():
            try:
                window.iconbitmap(APP_ICO_PATH)
            except Exception as e:
                print(f"INFO: settings window icon not set: {e}")

        window.after(250, _apply)

    @staticmethod
    def _apply_geometry(window):
        geometry_string = WindowHandler.load_window_size('Window_path', window)
        if geometry_string:
            window.geometry(geometry_string)
            return

        # Дефолт: позицію клампимо у видимий екран так само, як load_window_size.
        # Хардкод +668+661 на іншій конфігурації моніторів (RDP-реконект з
        # іншою роздільністю) міг опинитися поза екраном — і модальне вікно
        # було б невидиме, тоді як grab_set блокує решту UI. Розмір логічний,
        # у фізичну оцінку для клампа переводимо через масштаб CTk.
        w, h = SettingsWindow._DEFAULT_WIDTH, SettingsWindow._DEFAULT_HEIGHT
        scale = WindowHandler._window_scale(window)
        x, y = rdp.clamp_to_visible(668, 661, int(w * scale), int(h * scale))
        window.geometry(f'{w}x{h}+{x}+{y}')

    @staticmethod
    def _bind_geometry_autosave(window):
        """Зберігає позицію вікна при зміні — з дебаунсом, інакше кожна подія
        <Configure> під час перетягування переписує ini."""
        window._geometry_save_job = None

        def _save_geometry():
            window._geometry_save_job = None
            # Save/Cancel можуть знищити вікно, поки запис ще відкладений.
            if window.winfo_exists():
                WindowHandler.save_window_size('Window_path', window)

        def _on_configure(event):
            # <Configure> надходить і від дочірніх віджетів; реагуємо лише на
            # переміщення/ресайз самого вікна, щоб не смикати дебаунс дарма.
            if event.widget is not window:
                return
            if window._geometry_save_job is not None:
                window.after_cancel(window._geometry_save_job)
            window._geometry_save_job = window.after(500, _save_geometry)

        window.bind("<Configure>", _on_configure)

    @staticmethod
    def _bind_keyboard(window, save_command):
        """Enter — зберегти, Escape — закрити. Модальний діалог має реагувати
        на клавіатуру, а не лише на кліки по кнопках."""
        window.bind("<Return>", lambda _e: save_command())
        window.bind("<Escape>", lambda _e: window.destroy())

    # ---- Валідація і збереження ----

    @staticmethod
    def _validate(source_directory, destination_directory):
        """Повертає текст помилки або None, якщо шляхи придатні.

        Раніше поля писалися в config як є: порожній рядок, друкарська
        помилка чи source == destination тихо ламали копіювання аж до
        наступного перегляду налаштувань. Тепер відмова видима, а некоректні
        значення взагалі не зберігаються.
        """
        if not source_directory:
            return "Source directory is required."
        if not destination_directory:
            return "Destination directory is required."
        if not os.path.isdir(source_directory):
            return "Source directory does not exist."
        if os.path.normcase(os.path.abspath(source_directory)) == \
                os.path.normcase(os.path.abspath(destination_directory)):
            return "Source and destination must differ."
        # Неіснуючу теку призначення дозволяємо — застосунок її створить
        # (create_directory_if_not_exists). Але наявний ФАЙЛ за цим шляхом
        # текою стати не може.
        if os.path.exists(destination_directory) and \
                not os.path.isdir(destination_directory):
            return "Destination path is not a directory."
        return None

    @staticmethod
    def save_settings(app, settings_window, source_directory, destination_directory):
        """Валідує, зберігає шляхи, застосовує їх наживо і закриває вікно."""
        # .strip() прибирає випадкові пробіли, .strip('"') — лапки навколо
        # вставленого з провідника шляху; і те, й те інакше мовчки ламало б шлях.
        source_directory = source_directory.strip().strip('"')
        destination_directory = destination_directory.strip().strip('"')

        error = SettingsWindow._validate(source_directory, destination_directory)
        if error:
            status = getattr(settings_window, "_status_label", None)
            if status is not None and status.winfo_exists():
                status.configure(text=error)
            return  # Вікно лишається відкритим — користувач виправляє ввід.

        # ConfigManager.load_config при відсутньому файлі створює його лише
        # з секцією [Window] — байдуже, який це конфіг. Тож на свіжій
        # інсталяції (немає src/config.ini) секції [Settings] не існувало,
        # і .set() падав з NoSectionError просто по кнопці Save.
        if not app.config.has_section('Settings'):
            app.config.add_section('Settings')

        app.config.set('Settings', 'source_directory', source_directory)
        app.config.set('Settings', 'destination_directory', destination_directory)

        # Уникаємо циклічного імпорту, імпортуючи config_path тут
        from constants import CONFIG_PATH
        ConfigManager.save_atomic(app.config, CONFIG_PATH)

        # Застосувати наживо. Без цього зміна теки призначення діяла б лише
        # після перезапуску: її тримають закешованою обробник і watchdog.
        app.apply_directory_settings(source_directory, destination_directory)

        WindowHandler.save_window_size('Window_path', settings_window)
        settings_window.destroy()
