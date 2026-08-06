# Файл: ui/context_menu.py
"""Бургер-меню застосунку — власний попап на CTk-віджетах.

Раніше меню будував нативний `tk.Menu`. Він давав системний вигляд, який не
належав жодній темі: прямі кути, 3D-гравіровані сепаратори, світлий
`activeborder`, ніякого ховера-пігулки й ніякої позначки поточної теми. До
того ж Tk не бачить per-monitor DPI при awareness V2, тож і кегль шрифту, і
розмір іконок доводилося масштабувати вручну (кегль копіювався з поля
помилки, іконки — через окремий `tk.PhotoImage` з явним множником).

Тепер меню — це `Toplevel` без рамки зі скругленою карткою CTk усередині:
контур, «пігулка» ховера, підменю збоку, позначка поточної теми. Масштаб і
кольори приходять звідти ж, звідки в решти вікна (CTk + ключі `context_menu_*`
теми), тож меню виглядає частиною застосунку в кожній темі.
"""

import time
import tkinter as tk

import customtkinter as ctk

from ui.settings_window import SettingsWindow
from ui.ui_assets import (
    EXIT_ICON_PATH, SETTINGS_ICON_PATH, THEME_ICON_PATH,
    DARK_THEME_ICON_PATH, LIGHT_THEME_ICON_PATH, GRAPHITE_THEME_ICON_PATH
)
from ui.window_handler import WindowHandler
from utils import rdp

# Усі розміри тут — ЛОГІЧНІ px: CTk домножує їх на масштаб DPI сам, як і в
# решті вікна. Вручну масштабуються лише ті, що порівнюються з фізичними
# winfo_* (зазори при позиціонуванні) — див. _place/_measure.
_CORNER_RADIUS = 10   # радіус картки меню; це саме число йде і у Win32-регіон
_ROW_RADIUS = 6       # радіус «пігулки» ховера
_CARD_PAD = 6         # від краю картки до рядків
_ROW_HEIGHT = 28      # висота рядка
_ROW_PAD_X = 8        # від краю рядка до іконки / до позначки праворуч
_ICON_GAP = 10        # між іконкою і текстом
_TRAIL_WIDTH = 12     # колонка під «›»/«✓» — фіксована, щоб рядки збігались
_ICON_SIZE = (16, 16)
_SEP_PAD_Y = 5        # повітря навколо сепаратора
_MIN_WIDTH = 190      # менше меню виглядає тісним, навіть якщо текст короткий
_GAP = 4              # зазор кнопка→меню і картка→підменю

# «›» і «✓» — гліфи, а не картинки: іконки довелося б малювати під кожну тему
# окремо (колір), а текст просто бере text_color з теми й масштабується разом
# зі шрифтом.
_CHEVRON = "›"
_CHECK = "✓"


def _bold(font_spec):
    """Той самий шрифт теми, але жирний — для «›» і «✓».

    Обидва гліфи дрібні й тонкі; звичайним накресленням вони на фоні тексту
    рядка майже не читаються. Кортеж CTk масштабує сам, тож розмір тут не
    чіпаємо.
    """
    return (font_spec[0], font_spec[1], "bold")


class _MenuItem:
    """Опис пункту меню (не віджет).

    `submenu` — список таких самих описів; пункт із ним нічого не виконує, а
    розкриває картку збоку. `checked` — позначка «це поточний стан» (у нас це
    активна тема).
    """

    __slots__ = ("label", "icon", "command", "submenu", "checked", "separator")

    def __init__(self, label="", icon=None, command=None, submenu=None,
                 checked=False, separator=False):
        self.label = label
        self.icon = icon
        self.command = command
        self.submenu = submenu
        self.checked = checked
        self.separator = separator


class _MenuWindow(tk.Toplevel):
    """Вікно попапа: звичайний `tk.Toplevel`, а НЕ `CTkToplevel`.

    CTkToplevel у конструкторі робить `withdraw()` + `update()` + відкладений
    `deiconify()` заради кольору заголовка і ще через 200 мс ставить свою
    іконку. Для безрамкового попапа, який живе секунду й не має заголовка
    взагалі, це зайве блимання і TclError у `after`-колбеку, якщо меню закрили
    раніше. Крім того, CTkToplevel масштабує `geometry()` у ЛОГІЧНІ одиниці, а
    попап позиціонується від `winfo_rootx()` кнопки, тобто у ФІЗИЧНИХ —
    звичайний Toplevel лишає геометрію в тих самих одиницях, що й усі `winfo_*`.

    Два порожні методи потрібні `ScalingTracker`: CustomTkinter вважає КОЖЕН
    Toplevel, у якому лежать його віджети, окремим «вікном зі своїм DPI», і при
    зміні масштабу кличе в нього `block_update_dimensions_event()` — метод, який
    є лише в CTk-вікон. Без заглушок зміна DPI з відкритим меню (реконект RDP —
    головний сценарій цього застосунку) кинула б AttributeError усередині циклу
    `check_dpi_scaling`, і цикл перестав би перезапускатися: CTk більше не
    помічав би зміни DPI до перезапуску застосунку.
    """

    def block_update_dimensions_event(self):
        pass

    def unblock_update_dimensions_event(self):
        pass


class _MenuRow:
    """Один клікабельний рядок: [іконка] [текст] [›/✓].

    Три колонки замість одного `CTkButton` з `compound="left"`: кнопка вміє
    рівно одну картинку, тож правої позначки в неї не було б, а зазор між
    іконкою і текстом задавав би сам Tk — у нескальованих пікселях, тобто на
    200% DPI іконка майже торкалася б тексту.
    """

    def __init__(self, master, item, theme, image_manager):
        self.item = item
        self._theme = theme

        self.frame = ctk.CTkFrame(master, fg_color="transparent",
                                  corner_radius=_ROW_RADIUS, height=_ROW_HEIGHT)
        # Текст займає весь вільний простір, тож позначка тримається правого
        # краю картки, а не «їде» за довжиною напису.
        self.frame.grid_columnconfigure(1, weight=1)

        # CTkImage сам множить логічний розмір на масштаб віджета, тож ручний
        # DPI-множник (як був у tk.PhotoImage для нативного меню) тут не
        # потрібен. Джерела — ті самі 128×128 PNG, тобто завжди ЗМЕНШення.
        icon = image_manager.get_ctk_image(item.icon, _ICON_SIZE) if item.icon else None
        self._icon = ctk.CTkLabel(self.frame, text="", image=icon,
                                  width=_ICON_SIZE[0], height=_ROW_HEIGHT)
        self._icon.grid(row=0, column=0, padx=(_ROW_PAD_X, _ICON_GAP))

        self._text = ctk.CTkLabel(self.frame, text=item.label, anchor="w",
                                  height=_ROW_HEIGHT,
                                  font=theme["context_menu_font"],
                                  text_color=theme["context_menu_fg"])
        self._text.grid(row=0, column=1, sticky="ew")

        self._trail = ctk.CTkLabel(self.frame, text=self._trail_text(), anchor="e",
                                   width=_TRAIL_WIDTH, height=_ROW_HEIGHT,
                                   font=_bold(theme["context_menu_font"]),
                                   text_color=self._trail_color(False))
        self._trail.grid(row=0, column=2, padx=(_ICON_GAP, _ROW_PAD_X))

    def _trail_text(self):
        if self.item.submenu:
            return _CHEVRON
        return _CHECK if self.item.checked else ""

    def _trail_color(self, active):
        # Позначка поточної теми — акцентом (це стан, його треба бачити одразу).
        # Стрілка підменю — приглушена: вона службова й не має конкурувати з
        # написом, але на підсвіченому рядку переходить у колір активного
        # тексту, інакше «тонула» б у заливці ховера.
        theme = self._theme
        if self.item.checked and not self.item.submenu:
            return theme["context_menu_accent_color"]
        if active:
            return theme["context_menu_active_fg"]
        return theme["context_menu_muted_fg"]

    def set_active(self, active):
        """Вмикає/вимикає «пігулку» ховера.

        `fg_color` рядка CTkFrame сам роздає дочірнім CTk-віджетам новий
        `bg_color`, тож підкладка під текстом та іконкою міняється разом із
        рамкою — окремо їх фарбувати не треба.
        """
        theme = self._theme
        self.frame.configure(
            fg_color=theme["context_menu_active_bg"] if active else "transparent")
        self._text.configure(
            text_color=theme["context_menu_active_fg"] if active
            else theme["context_menu_fg"])
        self._trail.configure(text_color=self._trail_color(active))


class _MenuPopup:
    """Одна картка меню — головна або підменю."""

    def __init__(self, menu, items):
        self._menu = menu
        self.items = items
        self.active = None

        theme = menu.app.theme_manager.current_theme_data
        self._theme = theme

        self.top = _MenuWindow(menu.root)
        # Будуємо невидимим: розмір відомий лише після побудови рядків, а
        # показувати картку, поки її ще переставляють, — це блимання.
        self.top.withdraw()
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)  # головне вікно теж topmost
        # Прозорість — ТА САМА, що у головного вікна (ключ теми `window_alpha`),
        # інакше меню читалося б як чужий, «твердіший» об'єкт над напівпрозорим
        # вікном. Значення береться при кожному відкритті, тож після зміни теми
        # (dark/graphite 0.9, light 1) меню одразу відповідає вікну.
        self.top.attributes("-alpha", theme["window_alpha"])
        # Фон вікна = фон картки: у кутах, де дуга CTk згладжується, під нею
        # видно саме його, і будь-яка різниця читалася б як облямівка.
        self.top.configure(bg=theme["context_menu_bg"])

        self._adopt_window_scaling()

        self.card = ctk.CTkFrame(
            self.top,
            corner_radius=_CORNER_RADIUS,
            fg_color=theme["context_menu_bg"],
            border_width=1,
            border_color=theme["context_menu_border_color"],
        )
        self.card.pack(fill="both", expand=True)
        self.card.grid_columnconfigure(0, weight=1)

        # Win32-регіон бере радіус із ЦЬОГО віджета (`_outline_radius_px`), як
        # і в головному вікні: зріз регіону і намальована дуга — одне число за
        # побудовою, а не збіг двох перерахунків масштабу.
        self.top._outline_frame = self.card
        self.top._outline_radius = _CORNER_RADIUS

        self.rows = self._build_rows()
        self._bind_events()

    # ---- побудова ----

    def _adopt_window_scaling(self):
        """Прив'язує масштаб віджетів попапа до масштабу ГОЛОВНОГО вікна.

        CustomTkinter визначає масштаб для кожного Toplevel окремо і робить це
        при створенні першого CTk-віджета в ньому — через `MonitorFromWindow`.
        Попап у цей момент ще не показаний, тож Windows віддала б DPI монітора,
        на якому опинився невидимий HWND (типово первинного): на конфігурації з
        різним DPI меню було б іншого кегля, ніж вікно, з якого його відкрили.
        Тому переносимо вже відоме значення головного вікна — меню належить йому
        й мусить жити в тому самому масштабі. Не вийшло — CTk визначить сам.
        """
        try:
            scaling = ctk.ScalingTracker.window_dpi_scaling_dict
            scaling.setdefault(self.top, scaling[self._menu.root])
        except Exception:
            pass

    def _build_rows(self):
        """Створює рядки й сепаратори. Повертає список, паралельний items
        (None на місці сепаратора), щоб індекс пункту й індекс рядка збігались."""
        rows = []
        last = len(self.items) - 1
        for index, item in enumerate(self.items):
            top_pad = _CARD_PAD if index == 0 else 1
            bottom_pad = _CARD_PAD if index == last else 1

            if item.separator:
                line = ctk.CTkFrame(self.card, height=1, corner_radius=0,
                                    fg_color=self._theme["context_menu_separator_color"])
                line.grid(row=index, column=0, sticky="ew",
                          padx=_CARD_PAD + _ROW_PAD_X,
                          pady=(max(top_pad, _SEP_PAD_Y), max(bottom_pad, _SEP_PAD_Y)))
                rows.append(None)
                continue

            row = _MenuRow(self.card, item, self._theme, self._menu.image_manager)
            row.frame.grid(row=index, column=0, sticky="ew",
                           padx=_CARD_PAD, pady=(top_pad, bottom_pad))
            rows.append(row)
        return rows

    def _bind_events(self):
        """Усі прив'язки — на самому Toplevel.

        Прив'язувати кожен рядок окремо не треба: bindtags дочірнього віджета
        містять шлях його вікна, тож подія з будь-якої мітки всередині картки
        доходить сюди. Заразом це прибирає класичне мигання ховера на межі між
        іконкою й текстом (перехід між віджетами дає Leave+Enter, хоча курсор
        не залишав рядка) — тут позиція просто зіставляється з рядками.
        """
        top = self.top
        top.bind("<Motion>", lambda event: self._menu.on_motion(self, event))
        top.bind("<Button-1>", lambda event: self._menu.on_click(self, event))
        top.bind("<Leave>", lambda event: self._menu.on_leave(self, event))
        top.bind("<FocusOut>", lambda event: self._menu.on_focus_out())
        for key in ("<Escape>", "<Up>", "<Down>", "<Left>", "<Right>",
                    "<Return>", "<KP_Enter>", "<space>"):
            top.bind(key, self._menu.on_key)

    # ---- показ і позиціонування ----

    def _scale(self):
        return WindowHandler._window_scale(self._menu.root)

    def _measure(self):
        """ФІЗИЧНИЙ розмір картки. Розміри віджетів CTk уже масштабовані, тож
        `winfo_req*` віддає саме фізичні пікселі — ті самі, у яких працюють
        geometry() звичайного Toplevel і всі winfo_*."""
        self.top.update_idletasks()
        width = max(self.card.winfo_reqwidth(), round(_MIN_WIDTH * self._scale()))
        return width, self.card.winfo_reqheight()

    def open_under(self, widget):
        """Показує меню під віджетом, вирівняним по його ПРАВОМУ краю.

        Бургер стоїть у правому верхньому куті вузького вікна, тож меню,
        вирівняне ліворуч, вилазило б за правий край екрана майже завжди.
        """
        width, height = self._measure()
        gap = max(1, round(_GAP * self._scale()))
        x = widget.winfo_rootx() + widget.winfo_width() - width
        y = widget.winfo_rooty() + widget.winfo_height() + gap

        _, virtual_y, _, virtual_h = rdp.get_virtual_screen_rect()
        if y + height > virtual_y + virtual_h:
            y = widget.winfo_rooty() - gap - height  # не влазить донизу — вгору
        self._place(x, y, width, height)

    def open_beside(self, owner_row):
        """Показує підменю збоку від рядка-власника (як меню ОС і IDE)."""
        width, height = self._measure()
        scale = self._scale()
        gap = max(1, round(_GAP * scale))
        parent = owner_row.frame.winfo_toplevel()

        x = parent.winfo_rootx() + parent.winfo_width() + gap
        # Верх картки підменю зсуваємо на її ж внутрішній відступ, щоб ПЕРШИЙ
        # пункт став рівно проти рядка-власника, а не нижче за нього.
        y = owner_row.frame.winfo_rooty() - round(_CARD_PAD * scale)

        virtual_x, _, virtual_w, _ = rdp.get_virtual_screen_rect()
        if x + width > virtual_x + virtual_w:
            x = parent.winfo_rootx() - gap - width  # не влазить праворуч — ліворуч
        self._place(x, y, width, height)

    def _place(self, x, y, width, height):
        """Ставить картку на екран і накладає округлий регіон.

        `clamp_to_visible` — той самий запобіжник, що й у головного вікна:
        після реконекту RDP координати кнопки можуть дати позицію поза новим
        екраном. Регіон накладаємо ПІСЛЯ показу: wrapper-HWND, якому його
        віддають, Tk створює лише при мапінгу вікна.
        """
        x, y = rdp.clamp_to_visible(x, y, width, height)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        self.top.deiconify()
        self.top.update_idletasks()
        WindowHandler.round_corners(self.top)

    def focus(self):
        """Забирає фокус — інакше не працювала б клавіатура, а клік повз меню
        не давав би FocusOut, тобто не закривав би його."""
        try:
            self.top.focus_force()
        except Exception as e:
            print(f"INFO: menu cannot take focus: {e}")

    def destroy(self):
        try:
            self.top.destroy()
        except Exception:
            pass
        # ScalingTracker лишає КЛЮЧ знищеного вікна в обох своїх словниках
        # (CTk прибирає звідти лише колбеки віджетів), а меню за сесію
        # відкривають десятки разів. Прибираємо запис самі, щоб цикл
        # check_dpi_scaling не обходив щосекунди дедалі довший список мертвих
        # вікон.
        for registry in (ctk.ScalingTracker.window_widgets_dict,
                         ctk.ScalingTracker.window_dpi_scaling_dict):
            registry.pop(self.top, None)

    # ---- стан рядків ----

    def item_at(self, index):
        if index is None or self.rows[index] is None:
            return None
        return self.items[index]

    def row_index_at(self, x_root, y_root):
        """Індекс рядка під курсором (None — курсор повз рядки)."""
        if not self.contains(x_root, y_root):
            return None
        for index, row in enumerate(self.rows):
            if row is None:
                continue
            top = row.frame.winfo_rooty()
            if top <= y_root < top + row.frame.winfo_height():
                return index
        return None

    def contains(self, x_root, y_root):
        top = self.top
        x, y = top.winfo_rootx(), top.winfo_rooty()
        return (x <= x_root < x + top.winfo_width()
                and y <= y_root < y + top.winfo_height())

    def set_active(self, index):
        """Підсвічує рядок index (None — зняти підсвітку)."""
        if index is not None and self.rows[index] is None:
            index = None
        if index == self.active:
            return
        if self.active is not None and self.rows[self.active] is not None:
            self.rows[self.active].set_active(False)
        self.active = index
        if index is not None:
            self.rows[index].set_active(True)

    def step_active(self, delta):
        """Переставляє підсвітку на наступний/попередній рядок (по колу),
        перестрибуючи сепаратори."""
        indexes = [i for i, row in enumerate(self.rows) if row is not None]
        if not indexes:
            return
        if self.active in indexes:
            position = indexes.index(self.active) + delta
        else:
            position = 0 if delta > 0 else -1
        self.set_active(indexes[position % len(indexes)])


class ContextMenu:
    """Контролер меню: тримає ланцюг карток і всю поведінку.

    Ланцюг — це головна картка і, за потреби, одне підменю. Події з обох
    приходять сюди, бо рішення завжди стосується ланцюга цілком: підсвітити
    рядок в одній картці, тримати відкритою іншу, закрити все.

    **Грабів (`grab_set`) тут навмисно немає.** Глобальний граб перенаправляє
    події вікну, що його тримає, тож підменю (окремий Toplevel) перестало б
    отримувати рух миші. Замість нього клік повз меню ловиться через FocusOut:
    будь-який клік по іншому вікну — своєму чи чужому — забирає фокус.
    """

    # Клік по бургеру при відкритому меню приходить ПІСЛЯ FocusOut, який меню
    # вже закрив, тож без цього вікна воно б миттєво відкрилося знову.
    _REOPEN_GUARD_S = 0.25
    # Підменю розкривається праворуч, і дорога до нього мишею часто йде по
    # діагоналі — через сусідні рядки. Закриваємо із затримкою, інакше
    # підменю зникало б просто по дорозі до себе.
    _SUBMENU_CLOSE_MS = 250
    # FocusOut приходить і тоді, коли фокус перейшов у СВОЄ ж підменю (клік по
    # його рядку), тож рішення відкладаємо й перевіряємо, де фокус насправді.
    _FOCUS_CHECK_MS = 60

    def __init__(self, root, app, image_manager):
        self.root = root
        self.app = app
        self.image_manager = image_manager
        self._chain = []
        self._submenu_owner = None
        self._submenu_close_job = None
        self._closed_at = 0.0

    # ---- публічний API ----

    def show_menu(self, button):
        """Відкриває меню під кнопкою; повторний клік по кнопці — закриває."""
        if self.is_open():
            self.close()
            return
        if time.perf_counter() - self._closed_at < self._REOPEN_GUARD_S:
            return

        popup = _MenuPopup(self, self._build_items())
        self._chain.append(popup)
        popup.open_under(button)
        popup.focus()

    def close(self):
        """Закриває всі відкриті картки."""
        self._cancel_submenu_close()
        while self._chain:
            self._chain.pop().destroy()
        self._submenu_owner = None
        self._closed_at = time.perf_counter()

    def is_open(self):
        return bool(self._chain)

    # ---- вміст ----

    def _build_items(self):
        """Пункти меню будуються на КОЖНЕ відкриття: позначка поточної теми
        (і кольори всіх карток) залежать від стану, який міг змінитися."""
        current = self.app.theme_manager.current_theme_name
        themes = [
            _MenuItem("Dark", DARK_THEME_ICON_PATH,
                      command=lambda: self.app.toggle_theme("dark"),
                      checked=current == "dark"),
            _MenuItem("Light", LIGHT_THEME_ICON_PATH,
                      command=lambda: self.app.toggle_theme("light"),
                      checked=current == "light"),
            _MenuItem("Graphite", GRAPHITE_THEME_ICON_PATH,
                      command=lambda: self.app.toggle_theme("graphite"),
                      checked=current == "graphite"),
        ]
        # Сепаратор один — перед Exit. Розділяти ним кожен пункт (як робило
        # старе меню) означає читати три однакові групи по одному пункту;
        # тут же відділене саме те, що завершує роботу застосунку.
        return [
            _MenuItem("Theme", THEME_ICON_PATH, submenu=themes),
            _MenuItem("Path settings", SETTINGS_ICON_PATH,
                      command=lambda: SettingsWindow.open_settings_window(self.app)),
            _MenuItem(separator=True),
            _MenuItem("Exit", EXIT_ICON_PATH, command=self.app.on_closing),
        ]

    # ---- події ----

    def on_motion(self, popup, event):
        # Події можуть прилетіти вже після закриття (знищення вікна саме дає
        # Leave), тож кожен обробник спершу переконується, що меню ще живе.
        if not self._chain:
            return
        index = popup.row_index_at(event.x_root, event.y_root)
        # Курсор повз рядки (сепаратор, відступ картки) підсвітку НЕ знімає:
        # інакше вона мигала б у зазорах між рядками.
        if index is not None:
            popup.set_active(index)

        if popup is not self._chain[0]:
            self._cancel_submenu_close()  # курсор дійшов до підменю
            return

        item = popup.item_at(index)
        if item is not None and item.submenu:
            self._cancel_submenu_close()
            self._open_submenu(popup, index)
        elif index is not None and len(self._chain) > 1:
            self._schedule_submenu_close()

    def on_click(self, popup, event):
        if not self._chain:
            return
        index = popup.row_index_at(event.x_root, event.y_root)
        item = popup.item_at(index)
        if item is None:
            return  # клік по сепаратору чи відступу — меню лишається відкритим
        if item.submenu:
            self._open_submenu(popup, index)
            return
        self._activate(item)

    def on_leave(self, popup, event):
        if not self._chain:
            return
        # Leave приходить і на перехід між віджетами всередині картки (мітка →
        # мітка), тож віримо лише позиції курсора.
        if popup.contains(event.x_root, event.y_root):
            return
        if popup is self._chain[0] and len(self._chain) > 1:
            # Курсор пішов у бік підменю — рядок-власник лишається підсвіченим,
            # інакше відкрите підменю висіло б «нічиїм».
            popup.set_active(self._submenu_owner)
            return
        popup.set_active(None)

    def on_focus_out(self):
        try:
            self.root.after(self._FOCUS_CHECK_MS, self._close_if_unfocused)
        except Exception:
            # Знищення вікна теж дає FocusOut, і на виході з застосунку root
            # може вже не приймати after — перевіряти тоді все одно нічого.
            pass

    def on_key(self, event):
        """Клавіатура працює з найглибшою відкритою карткою.

        Фокус завжди тримає головна картка (підменю ми не фокусуємо), тож
        подія приходить сюди незалежно від того, що зараз розкрите.
        """
        if not self._chain:
            return
        popup = self._chain[-1]
        key = event.keysym

        if key == "Escape":
            # Escape закриває рівень за рівнем, як у меню ОС.
            if len(self._chain) > 1:
                self._close_submenu()
            else:
                self.close()
        elif key in ("Down", "Up"):
            popup.step_active(1 if key == "Down" else -1)
        elif key == "Right":
            item = popup.item_at(popup.active)
            if item is not None and item.submenu:
                self._open_submenu(popup, popup.active)
                self._chain[-1].step_active(1)
        elif key == "Left":
            if len(self._chain) > 1:
                self._close_submenu()
        elif key in ("Return", "KP_Enter", "space"):
            item = popup.item_at(popup.active)
            if item is None:
                return
            if item.submenu:
                self._open_submenu(popup, popup.active)
                self._chain[-1].step_active(1)
            else:
                self._activate(item)

    # ---- внутрішня механіка ----

    def _activate(self, item):
        # Спершу закриваємо, потім виконуємо: команда може перемкнути тему
        # (CTk пройдеться по ВСІХ живих віджетах, зокрема по картках меню) або
        # взагалі завершити застосунок.
        self.close()
        if item.command is not None:
            item.command()

    def _open_submenu(self, parent, index):
        if self._submenu_owner == index and len(self._chain) > 1:
            return  # вже розкрите для цього ж рядка
        self._close_submenu()

        item = parent.item_at(index)
        if item is None or not item.submenu:
            return

        popup = _MenuPopup(self, item.submenu)
        self._chain.append(popup)
        self._submenu_owner = index
        popup.open_beside(parent.rows[index])
        parent.set_active(index)

    def _close_submenu(self):
        self._cancel_submenu_close()
        while len(self._chain) > 1:
            self._chain.pop().destroy()
        self._submenu_owner = None

    def _schedule_submenu_close(self):
        if self._submenu_close_job is not None:
            return
        self._submenu_close_job = self.root.after(
            self._SUBMENU_CLOSE_MS, self._close_submenu)

    def _cancel_submenu_close(self):
        if self._submenu_close_job is not None:
            self.root.after_cancel(self._submenu_close_job)
            self._submenu_close_job = None

    def _close_if_unfocused(self):
        """Закриває меню, якщо фокус пішов ПОВЗ нього.

        `focus_displayof()` віддає None, коли фокус у чужому застосунку, і
        віджет — коли у своєму. Клік по рядку підменю теж дає FocusOut головній
        картці, тож без цієї перевірки меню закривалося б від власного ж кліку.
        """
        if not self._chain:
            return
        try:
            focused = self._chain[0].top.focus_displayof()
        except Exception:
            focused = None
        if focused is not None:
            top = focused.winfo_toplevel()
            if any(top is popup.top for popup in self._chain):
                return
        self.close()
