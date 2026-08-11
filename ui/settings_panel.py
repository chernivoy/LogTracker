import math
import os
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from config_manager import ConfigManager
from constants import CONFIG_PATH
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


class SettingsPanel:
    """Налаштування шляхів — смуга контролів УНИЗУ головного вікна.

    Раніше це було окреме модальне вікно (`ui/settings_window.py`): власна
    геометрія в ini, `grab_set`, іконка заголовка, автозбереження позиції — цілий
    другий життєвий цикл вікна заради двох полів. Тепер ті самі контролі
    (два поля зі своїми Browse, рядок статусу, Save і Cancel) з'являються прямо
    в головному вікні під полем помилки, а вікно на час показу стає рівно на їх
    висоту вищим. Save/Cancel ховають панель і повертають попередню висоту.

    **Вікно росте, а не тиснеться.** Поле помилки лишається того самого розміру:
    панель міряється ДО того, як стати в grid, і на її висоту спершу росте
    вікно. Приріст живе в `root._panel_extra_logical` — звідти його бачать
    `WindowHandler.min_height_logical` (межа ручного ресайзу і `minsize`),
    `save_window_size` (в ini має лежати ВЛАСНА висота користувача, без панелі) і
    `load_window_size` (відновлення з трея з відкритою панеллю має врахувати її).

    **Тема.** Стиль читається з `current_theme_data` при побудові (група ключів
    `settings_*`), а панель будується заново на кожне відкриття. Але, на відміну
    від колишнього модального вікна, тему тепер МОЖНА перемкнути, не закриваючи
    панель — бургер-меню поруч, — тож `LogTrackerApp.toggle_theme` кличе
    `apply_theme()`, який перефарбовує відкриту панель наживо.
    """

    # Колір повідомлення про помилку валідації. Фіксований, а не з теми: це
    # службовий індикатор стану, а не частина палітри, і читається на фоні
    # всіх трьох тем (світлій, темній, graphite). Заводити заради нього ключ
    # у theme-контракт (довелося б додати в кожну тему) не варто.
    _ERROR_COLOR = "#e06c75"

    # Усі розміри — ЛОГІЧНІ px: CTk домножує їх на масштаб DPI сам.
    #
    # Висоти віджетів задані явно (а не лишені дефолтними 28), бо панель
    # розсуває вікно рівно на свою висоту: що компактніша смуга, то менше
    # головне вікно смикається на час налаштування. Заразом фіксовані висоти
    # роблять приріст незалежним від шрифту теми — `apply_theme` міняє кольори
    # й кегль, а виміряна висота лишається чинною.
    _LABEL_HEIGHT = 16
    _FIELD_HEIGHT = 26
    _BROWSE_WIDTH = 70
    _BUTTON_WIDTH = 80
    _GAP = 6        # поле → Browse, Save → Cancel
    _ROW_GAP = 3    # підпис → його поле
    _BLOCK_GAP = 6  # між блоками (сепаратор, поле → наступний підпис, статус)

    def __init__(self, app, root, master, row, inset):
        """`master`/`row` — куди панель стає в grid головного фрейму;
        `inset` — той самий `_CONTENT_INSET`, що й у поля помилки: контент не
        має налазити на дуги нижніх кутів і ховати контур вікна."""
        self.app = app
        self.root = root
        self._master = master
        self._row = row
        self._inset = inset

        self._frame = None
        self._separator = None
        self._status_label = None
        self._source_entry = None
        self._destination_entry = None
        self._labels = []
        self._entries = []
        self._buttons = []

    # ---- публічний API ----

    def is_open(self):
        return self._frame is not None

    def open(self):
        """Показує панель, розсунувши вікно рівно на її висоту."""
        if self.is_open():
            self._focus_first()  # повторний виклик з меню — просто повернути фокус
            return

        self._build()
        # Міряємо ДО grid: якби панель спершу стала у вікно, а вікно виросло
        # потім, перший кадр показав би її втиснутою за рахунок поля помилки.
        extra = self._measure_extra()
        self._expand(extra)
        self._frame.grid(row=self._row, column=0, columnspan=3, sticky="ew",
                         padx=self._inset, pady=(0, self._inset))
        self._bind_keys()
        self._focus_first()

    def close(self):
        """Ховає панель і повертає вікну висоту, яка була до відкриття."""
        if not self.is_open():
            return

        extra = getattr(self.root, "_panel_extra_logical", 0)
        self._unbind_keys()
        self._frame.destroy()
        self._frame = None
        self._separator = None
        self._status_label = None
        self._source_entry = None
        self._destination_entry = None
        self._labels, self._entries, self._buttons = [], [], []
        self._collapse(extra)

    def apply_theme(self):
        """Перефарбовує ВІДКРИТУ панель під поточну тему (no-op, якщо закрита).

        Колишнє вікно налаштувань було модальним, тож перемкнути тему при ньому
        було неможливо — стиль читався один раз при відкритті. Панель же живе в
        головному вікні, і бургер-меню поруч лишається доступним.
        """
        if not self.is_open():
            return

        theme = self.app.theme_manager.current_theme_data
        self._separator.configure(fg_color=theme["settings_entry_border_color"])
        for label in self._labels:
            label.configure(text_color=theme["settings_text_color"],
                            font=theme["settings_font"])
        for entry in self._entries:
            entry.configure(fg_color=theme["settings_entry_fg_color"],
                            text_color=theme["settings_text_color"],
                            border_color=theme["settings_entry_border_color"],
                            font=theme["settings_font"])
        for button in self._buttons:
            button.configure(fg_color=theme["settings_button_fg_color"],
                             hover_color=theme["settings_button_hover_color"],
                             text_color=theme["settings_button_text_color"],
                             font=theme["settings_font"])
        self._status_label.configure(font=theme["settings_font"])

    # ---- побудова ----

    def _build(self):
        theme = self.app.theme_manager.current_theme_data
        # Списки для apply_theme збираються заново: панель будується на кожне
        # відкриття, і посилання на віджети минулого разу вже мертві.
        self._labels, self._entries, self._buttons = [], [], []

        self._frame = ctk.CTkFrame(self._master, fg_color="transparent")
        # Поле вводу розтягується на всю вільну ширину, Browse тримає свою.
        self._frame.grid_columnconfigure(0, weight=1)
        self._frame.grid_columnconfigure(1, weight=0)

        # Волосяна лінія відділяє налаштування від поля помилки. У dark поле
        # прозоре й без рамки, тож без неї контролі просто зависали б у вікні.
        self._separator = ctk.CTkFrame(
            self._frame, height=1, corner_radius=0,
            fg_color=theme["settings_entry_border_color"])
        self._separator.grid(row=0, column=0, columnspan=2, sticky="ew",
                             pady=(0, self._BLOCK_GAP))

        self._source_entry = self._add_field(
            theme, 1, "Path to source directory:", self.app.source_directory)
        self._destination_entry = self._add_field(
            theme, 3, "Path to destination directory:", self.app.destination_directory)

        # Рядок валідації: постійно на місці (порожній), щоб поява повідомлення
        # не міняла висоту панелі, під яку вже розсунуте вікно. Тому ж він в
        # ОДИН рядок, без wraplength — довге повідомлення обріжеться колонкою,
        # а не з'їсть поле помилки другим рядком.
        self._status_label = ctk.CTkLabel(
            self._frame, text="", anchor="w", height=self._LABEL_HEIGHT,
            text_color=self._ERROR_COLOR, font=theme["settings_font"])
        self._status_label.grid(row=5, column=0, columnspan=2, sticky="ew",
                                pady=(self._BLOCK_GAP, 0))

        actions = ctk.CTkFrame(self._frame, fg_color="transparent")
        actions.grid(row=6, column=0, columnspan=2, sticky="e",
                     pady=(self._ROW_GAP, 0))
        self._add_button(actions, theme, "Save", self._save)
        self._add_button(actions, theme, "Cancel", self.close, padx=(self._GAP, 0))

    def _add_field(self, theme, row, label_text, value):
        """Підпис + рядок «поле вводу + Browse». Повертає поле вводу."""
        label = ctk.CTkLabel(
            self._frame, text=label_text, anchor="w", height=self._LABEL_HEIGHT,
            text_color=theme["settings_text_color"], font=theme["settings_font"])
        label.grid(row=row, column=0, columnspan=2, sticky="ew",
                   pady=(0, self._ROW_GAP))
        self._labels.append(label)

        entry = ctk.CTkEntry(
            self._frame,
            height=self._FIELD_HEIGHT,
            fg_color=theme["settings_entry_fg_color"],
            text_color=theme["settings_text_color"],
            border_color=theme["settings_entry_border_color"],
            font=theme["settings_font"],
        )
        entry.insert(0, value)
        entry.grid(row=row + 1, column=0, sticky="ew", pady=(0, self._BLOCK_GAP))
        self._entries.append(entry)

        browse = ctk.CTkButton(
            self._frame,
            text="Browse",
            width=self._BROWSE_WIDTH,
            height=self._FIELD_HEIGHT,
            command=lambda: self._browse(entry),
            fg_color=theme["settings_button_fg_color"],
            hover_color=theme["settings_button_hover_color"],
            text_color=theme["settings_button_text_color"],
            font=theme["settings_font"],
        )
        browse.grid(row=row + 1, column=1, sticky="e",
                    padx=(self._GAP, 0), pady=(0, self._BLOCK_GAP))
        self._buttons.append(browse)

        # Повний шлях часто ширший за поле — показуємо його підказкою при
        # наведенні, щоб було видно «хвіст» без прокрутки поля.
        _PathTooltip(entry, theme["settings_font"])

        return entry

    def _add_button(self, master, theme, text, command, padx=0):
        button = ctk.CTkButton(
            master,
            text=text,
            width=self._BUTTON_WIDTH,
            height=self._FIELD_HEIGHT,
            command=command,
            fg_color=theme["settings_button_fg_color"],
            hover_color=theme["settings_button_hover_color"],
            text_color=theme["settings_button_text_color"],
            font=theme["settings_font"],
        )
        button.pack(side="left", padx=padx)
        self._buttons.append(button)

    def _browse(self, entry):
        """Відкриває нативний діалог вибору теки і вписує результат у поле.

        Стартуємо з теки, яка вже в полі (якщо вона існує). Порожній результат
        означає скасування — поле не чіпаємо. `grab_release`/`grab_set` навколо
        діалогу більше не потрібні: панель не модальна, локального граба, який
        перехопив би фокус у вікна ОС, немає.
        """
        current = entry.get().strip().strip('"')
        kwargs = {"parent": self.root, "title": "Select folder"}
        if os.path.isdir(current):
            kwargs["initialdir"] = current

        path = filedialog.askdirectory(**kwargs)
        if path:  # '' = користувач скасував діалог
            entry.delete(0, "end")
            entry.insert(0, os.path.normpath(path))
        entry.focus_set()

    # ---- розмір вікна ----

    def _logical(self, physical):
        """Фізичні px → логічні, з ОКРУГЛЕННЯМ.

        Саме округленням, а не відкиданням дробової частини: панель відкривають
        і закривають скільки завгодно разів за сесію, і кожен раз проходить
        повний цикл «логічне → фізичне (CTk) → логічне (тут)». Втрачений на
        зрізі піксель накопичувався б, і вікно повзло б у меншу сторону.
        """
        scale = WindowHandler._window_scale(self.root)
        return max(1, round(physical / scale)) if scale else max(1, physical)

    def _measure_extra(self):
        """ЛОГІЧНА висота, на яку має вирости вікно (панель + її нижній відступ).

        Панель у цей момент ще не в grid — розмір їй дає розкладка ВЛАСНИХ
        дітей, тож `winfo_reqheight` уже коректний. Він фізичний (CTk масштабує
        розміри віджетів сам), а відступ ми задаємо логічним, тож переводимо.
        """
        self._frame.update_idletasks()
        scale = WindowHandler._window_scale(self.root)
        return math.ceil(self._frame.winfo_reqheight() / max(scale, 0.01)) + self._inset

    def _expand(self, extra):
        root = self.root
        root._panel_extra_logical = extra
        root.minsize(300, WindowHandler.min_height_logical(root))

        width = self._logical(root.winfo_width())
        height = self._logical(root.winfo_height()) + extra
        # Вікно росте вниз, тож біля нижнього краю екрана могло б вилізти за
        # нього — той самий кламп, що й скрізь, де змінюється геометрія.
        scale = WindowHandler._window_scale(root)
        x, y = rdp.clamp_to_visible(root.winfo_x(), root.winfo_y(),
                                    round(width * scale), round(height * scale))
        root.geometry(f"{width}x{height}+{x}+{y}")

    def _collapse(self, extra):
        root = self.root
        root._panel_extra_logical = 0
        root.minsize(300, WindowHandler.min_height_logical(root))

        # Позицію не чіпаємо: вікно згортається знизу, верхній край лишається
        # там, де стояв. Віднімаємо від ПОТОЧНОЇ висоти, а не повертаємо
        # запам'ятану, — користувач міг ресайзити вікно з відкритою панеллю.
        width = self._logical(root.winfo_width())
        height = max(WindowHandler.min_height_logical(root),
                     self._logical(root.winfo_height()) - extra)
        root.geometry(f"{width}x{height}")

    # ---- клавіатура і фокус ----

    def _bind_keys(self):
        """Enter — Save, Escape — Cancel.

        Прив'язуємо на root (без add="+"), бо подія з поля піднімається
        bindtags до свого toplevel, а більше ці дві клавіші на головному вікні
        не слухає ніхто — тож зняти їх у `_unbind_keys` можна без побічних
        ефектів. (Попап бургер-меню теж ловить Escape, але на СВОЄМУ Toplevel.)
        """
        self.root.bind("<Return>", self._on_return)
        self.root.bind("<KP_Enter>", self._on_return)
        self.root.bind("<Escape>", self._on_escape)

    def _unbind_keys(self):
        for sequence in ("<Return>", "<KP_Enter>", "<Escape>"):
            try:
                self.root.unbind(sequence)
            except Exception:
                pass

    def _on_return(self, _event=None):
        self._save()
        return "break"

    def _on_escape(self, _event=None):
        self.close()
        return "break"

    def _focus_first(self):
        """Фокус у перше поле. `focus_force` обов'язковий: головне вікно
        безрамкове (overrideredirect), і після закриття бургер-меню, з якого
        панель відкрили, клавіатурний фокус до нього сам не повертається."""
        try:
            self.root.focus_force()
            self._source_entry.focus_set()
        except Exception as e:
            print(f"INFO: settings panel cannot take focus: {e}")

    # ---- валідація і збереження ----

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

    def _save(self):
        """Валідує, зберігає шляхи, застосовує їх наживо і ховає панель."""
        if not self.is_open():
            return

        # .strip() прибирає випадкові пробіли, .strip('"') — лапки навколо
        # вставленого з провідника шляху; і те, й те інакше мовчки ламало б шлях.
        source_directory = self._source_entry.get().strip().strip('"')
        destination_directory = self._destination_entry.get().strip().strip('"')

        error = self._validate(source_directory, destination_directory)
        if error:
            self._status_label.configure(text=error)
            return  # Панель лишається відкритою — користувач виправляє ввід.

        # ConfigManager.load_config при відсутньому файлі створює його лише
        # з секцією [Window] — байдуже, який це конфіг. Тож на свіжій
        # інсталяції (немає src/config.ini) секції [Settings] не існувало,
        # і .set() падав з NoSectionError просто по кнопці Save.
        config = self.app.config
        if not config.has_section('Settings'):
            config.add_section('Settings')

        config.set('Settings', 'source_directory', source_directory)
        config.set('Settings', 'destination_directory', destination_directory)
        ConfigManager.save_atomic(config, CONFIG_PATH)

        # Ховаємо ПЕРЕД застосуванням: apply_directory_settings робить повну
        # синхронізацію тек і пише в поле помилки, тобто працює вже з тим
        # вікном, яке користувач побачить після закриття панелі.
        self.close()

        # Застосувати наживо. Без цього зміна теки призначення діяла б лише
        # після перезапуску: її тримають закешованою обробник і watchdog.
        self.app.apply_directory_settings(source_directory, destination_directory)
