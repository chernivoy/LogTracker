import ctypes
import os
import time
import tkinter as tk

import customtkinter as ctk

from config_manager import ConfigManager
from utils.path import PathUtils
from utils import rdp

CONFIG_FILE_WINDOW = PathUtils.user_config_path("window_config.ini")

# --- ctypes: типи Win32-викликів округлення кутів -------------------------
# Без явних restype 64-бітні HWND/HRGN зрізаються до 32 біт (типовий restype
# ctypes — c_int), і зіпсований дескриптор регіону міг би піти далі в
# SetWindowRgn. Ці функції кличе лише window_handler (і мертвий pin.py), тож
# налаштування на кешованому windll стороннього коду не зачіпає. RedrawWindow
# теж типізуємо — інакше передача 64-бітного hwnd у нетипізовану функцію дала б
# OverflowError на великому вказівнику.
_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_user32.GetParent.restype = ctypes.c_void_p
_user32.GetParent.argtypes = (ctypes.c_void_p,)
_gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
_gdi32.CreateRoundRectRgn.argtypes = (ctypes.c_int,) * 6
_user32.SetWindowRgn.restype = ctypes.c_int
_user32.SetWindowRgn.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
_gdi32.DeleteObject.restype = ctypes.c_int
_gdi32.DeleteObject.argtypes = (ctypes.c_void_p,)
_user32.RedrawWindow.restype = ctypes.c_int
_user32.RedrawWindow.argtypes = (
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
)


class WindowHandler:
    """
    Відповідає за налаштування та поведінку вікна:
    зміна розміру, переміщення та округлення кутів.
    """

    # Радіус округлення кутів вікна у ЛОГІЧНИХ px (масштабується за DPI).
    #
    # 15 — це РЕАЛЬНИЙ радіус. CreateRoundRectRgn приймає не радіус, а РОЗМІР
    # ЕЛІПСА кута (тобто діаметр), тож _set_corner_region подвоює значення перед
    # викликом. Раніше тут стояло 30 і йшло у Win32 як є — фактичне округлення
    # усе одно виходило 15, просто константа брехала вдвічі. Вигляд вікна від
    # виправлення не змінився, зате число тепер чесне, і рівно його ж дістає
    # main_frame як corner_radius: намальована CTk рамка вікна має лягти ТОЧНО
    # на межу регіону, інакше між дугою CTk і дугою регіону лишається видимий
    # клин фону канви.
    CORNER_RADIUS = 15

    # Віджети, у яких клік і протяг мають лишатися кліком і протягом, а не
    # ставати ресайзом вікна: кнопки заголовка (згорнути/бургер), кнопки й поля
    # вводу панелі налаштувань. Розпізнаємо за шляхом Tk-віджета — він містить
    # ім'я класу CTk (в т.ч. для внутрішніх canvas/label/entry).
    #
    # Поля вводу тут критичні: панель займає низ вікна, а її поля відступають
    # від краю лише на _CONTENT_INSET (6 логічних px), тобто цілком потрапляють
    # у 20-піксельну смугу захоплення краю. Без цієї перевірки виділення тексту
    # мишею біля лівого/правого краю ресайзило б вікно замість виділення.
    _CLICKABLE_WIDGETS = ("ctkbutton", "ctkentry")

    @staticmethod
    def _is_clickable_widget(event: tk.Event):
        widget_path = str(event.widget)
        return any(name in widget_path for name in WindowHandler._CLICKABLE_WIDGETS)

    @staticmethod
    def _event_root(event: tk.Event):
        """Вікно, у якому сталася подія, або None — якщо віджета вже нема.

        `event.widget` не завжди віджет: Tkinter підставляє туди сирий
        РЯДОК-шлях, коли Python-об'єкта за цим шляхом немає в реєстрі, тобто
        коли віджет уже знищено. Це не екзотика, а звичайний наслідок того, що
        всі кнопки миші прив'язані ще й на рівні ВІКНА: Tk виконує прив'язки по
        bindtags по черзі (віджет → клас → вікно → all), і якщо віджетна
        встигла знищити сам віджет, до віконної доходить мертвий шлях.

        Саме так поводяться Save/Cancel панелі налаштувань: `CTkButton` кличе
        команду на `<Button-1>`, команда ховає панель разом із кнопкою — і
        `start_resize`, що йде наступним у ланцюгу, падав тут на
        `.winfo_toplevel()`. Нічого страшного в події вже не лишилось (клік по
        кнопці ресайзу все одно не починає), тож повертаємо None і виходимо.
        """
        widget = event.widget
        if isinstance(widget, str):
            return None
        try:
            return widget.winfo_toplevel()
        except Exception:
            return None

    @staticmethod
    def save_window_size(section, root):
        # Симетрично до load_window_size: зберігаємо ЛОГІЧНІ width/height
        # (як їх бачить CTk) і ФІЗИЧНІ x/y. Round-trip save↔load іде через
        # рідну модель масштабування CTk, без ручного множника: load віддає
        # логічні w/h у geometry(), а CTk сам домножує їх до фізичних.
        #
        # x/y лишаємо фізичними через winfo_x()/winfo_y(): це надійні цілі
        # (можуть бути від'ємними на моніторі ліворуч/вгорі), а розбір рядка
        # geometry() для позиції неоднозначний — Tk трактує "-100" як «100 px
        # від правого краю», а не x=-100.
        width = WindowHandler._to_logical(root, root.winfo_width())
        height = WindowHandler._to_logical(root, root.winfo_height())
        x = root.winfo_x()
        y = root.winfo_y()

        # Поки внизу вікна відкрита панель налаштування шляхів, вікно тимчасово
        # вище рівно на її висоту (ui/settings_panel.py). В ini має лежати
        # ВЛАСНА висота користувача: інакше закриття панелі повернуло б розмір
        # вікна, а збережений лишився б з нею — і наступний запуск відкрився б
        # із зайвим порожнім місцем унизу. load_window_size додає приріст назад,
        # якщо панель відкрита (відновлення з трея).
        height = max(1, height - getattr(root, "_panel_extra_logical", 0))

        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            config[section] = {}

        config[section]['width'] = str(width)   # ЛОГІЧНА ширина
        config[section]['height'] = str(height)  # ЛОГІЧНА висота
        config[section]['x'] = str(x)  # ФІЗИЧНИЙ X
        config[section]['y'] = str(y)  # ФІЗИЧНИЙ Y

        ConfigManager.save_atomic(config, CONFIG_FILE_WINDOW)

    @staticmethod
    def save_window_params(section, x=None, y=None, width=None, height=None):
        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            config[section] = {}

        config[section]['x'] = str(x) if x is not None else "100"
        config[section]['y'] = str(y) if y is not None else "100"
        config[section]['width'] = str(width) if width is not None else "300"
        config[section]['height'] = str(height) if height is not None else "300"

        ConfigManager.save_atomic(config, CONFIG_FILE_WINDOW)

    @staticmethod
    def _window_scale(root):
        """Масштаб, який CTk застосовує до geometry() (== DPI монітора / 96).

        Беремо його з самого CustomTkinter — це кешоване значення, без
        Win32-викликів на кожну подію. Тоді ділення розмірів тут і множення
        всередині CTk.geometry() скорочуються ТОЧНО (включно з можливим
        користувацьким window_scaling), а не приблизно, як при окремому
        запиті GetDpiForMonitor. Запасний варіант — прямий запит DPI монітора.
        """
        getter = getattr(root, "_get_window_scaling", None)
        if callable(getter):
            try:
                scale = getter()
                if scale and scale > 0:
                    return scale
            except Exception:
                pass
        try:
            scale = rdp.get_windows_dpi_scale(root)
            if scale and scale > 0:
                return scale
        except Exception:
            pass
        return 2.0

    @staticmethod
    def _to_logical(root, physical_value):
        """Фізичні пікселі → логічні (як їх зберігає CTk), тим самим
        реверсом масштабу, який CTk застосовує в geometry(). Пара до того,
        як geometry() домножує назад. Запасний варіант — ділення на
        _window_scale()."""
        rev = getattr(root, "_reverse_window_scaling", None)
        if callable(rev):
            try:
                return int(rev(physical_value))
            except Exception:
                pass
        scale = WindowHandler._window_scale(root)
        return int(physical_value / scale) if scale else int(physical_value)

    @staticmethod
    def load_window_size(section, root):
        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            return None

        # У INI лежать ЛОГІЧНІ width/height і ФІЗИЧНІ x/y. Логічні w/h
        # передаємо в geometry() як є — CTk домножить їх до фізичних сам
        # (симетрично до save_window_size). Жодного ручного множника тут
        # більше немає: round-trip повністю на рідній моделі масштабування
        # CTk, тож при зміні DPI (реконект) зберігається ЛОГІЧНИЙ розмір
        # вікна, а не фіксований піксельний.
        width = config.getint(section, 'width', fallback=800)
        height = config.getint(section, 'height', fallback=600)
        x = config.getint(section, 'x', fallback=100)
        y = config.getint(section, 'y', fallback=100)

        # Симетрично до save_window_size: в ini лежить висота БЕЗ панелі
        # налаштувань, тож якщо вона зараз відкрита — повертаємо приріст.
        # Інакше відновлення з трея з відкритою панеллю підрізало б вікно на
        # її висоту, і панель тиснула б поле помилки.
        height += getattr(root, "_panel_extra_logical", 0)

        # Захист від зниклого вікна: clamp у фізичному просторі екрана, тож
        # логічні w/h переводимо в фізичну оцінку розміру через масштаб CTk.
        scale = WindowHandler._window_scale(root)
        phys_w = int(width * scale)
        phys_h = int(height * scale)
        x, y = rdp.clamp_to_visible(x, y, phys_w, phys_h)

        return f'{width}x{height}+{x}+{y}'

    @staticmethod
    def min_height_logical(root):
        """Мінімальна ЛОГІЧНА висота вікна на ЦЕЙ момент.

        Складається з двох частин, які живуть окремо:

        - `root._min_height_logical` — заголовок плюс запас під ~кілька рядків
          тексту; міряє й виставляє `ErrorWindow.apply_dynamic_min_height`;
        - `root._panel_extra_logical` — висота відкритої панелі налаштувань
          (0, коли її нема); виставляє `ui/settings_panel.py`.

        Складати їх мусить одне місце, бо число потрібне ТРЬОМ сторонам одразу:
        `root.minsize(...)`, межі ручного ресайзу в `do_resize` і самій панелі
        при згортанні вікна. Розійшлися б вони — і при ресайзі з півночі/заходу
        OS клампив би розмір по одній межі, а x/y зсувалися б по іншій: вікно
        «повзло» б (та сама пастка, що описана в do_resize).
        """
        return (getattr(root, "_min_height_logical", 100)
                + getattr(root, "_panel_extra_logical", 0))

    @staticmethod
    def _outline_radius_px(root):
        """ФІЗИЧНИЙ радіус кута, яким CTk РЕАЛЬНО малює контур вікна.

        Форму вікна задають ДВА незалежні малювальники: Win32-регіон (жорсткий
        зріз) і рамка, яку CTk малює на main_frame по своєму corner_radius. Щоб
        між ними не лишалось видимого клина, радіус мусить бути тим самим
        числом — тож беремо його не власним перерахунком, а тим самим віджетом
        і тією самою функцією масштабування, якими CTk малює дугу:
        root._outline_frame (його ставить ErrorWindow.create_widgets) і
        _apply_widget_scaling. DrawEngine ще й округлює результат (round), тож
        round тут — не «приблизно», а точно те число, що лягає на канву.

        ЛОГІЧНИЙ радіус береться з `root._outline_radius`, якщо він виставлений
        поруч із `_outline_frame`. Так само округляє собі кути попап бургер-меню
        (ui/context_menu.py), а картка меню менша за вікно й радіус має свій.
        Обидва числа лишаються парою на одному вікні, тож розійтися не можуть.

        Раніше радіус рахувався як CORNER_RADIUS * _window_scale(root), тобто з
        ВІКОННОГО масштабу CTk. У сталому стані він дорівнює віджетному (обидва
        = window_dpi_scaling_dict[root]), але читаються вони в РІЗНІ моменти й
        оновлюються РІЗНИМИ подіями, тож розходяться при зміні DPI: у полі
        спіймано регіон з радіусом 15 при намальованій дузі 30 (масштаб 1.0
        проти 2.0). Видно це як ДВІ дуги в кожному куті — жорсткий зріз регіону
        по малому радіусу і намальована рамка по великому, а між ними смуга
        фону вікна без жодної межі.
        """
        frame = getattr(root, "_outline_frame", None)
        logical = getattr(root, "_outline_radius", WindowHandler.CORNER_RADIUS)
        scaler = getattr(frame, "_apply_widget_scaling", None)
        if callable(scaler):
            try:
                return max(0, round(scaler(logical)))
            except Exception:
                pass
        return max(0, round(logical * WindowHandler._window_scale(root)))

    @staticmethod
    def _set_corner_region(hwnd, width, height, radius, redraw=True):
        """Створює округлий регіон width×height (ФІЗИЧНІ px) і віддає його
        вікну hwnd. `radius` — ФІЗИЧНИЙ радіус кута. Повертає True на успіх.

        Останні два аргументи CreateRoundRectRgn — це РОЗМІР ЕЛІПСА кута
        (діаметр), а не радіус, тому *2. Без подвоєння фактичне округлення
        вдвічі менше за задане, і рамка, яку CTk малює по corner_radius (де те
        саме число означає саме радіус), проходила б не по межі регіону.

        SetWindowRgn ПЕРЕБИРАЄ володіння регіоном і сам видаляє попередній,
        тож на успіху окремий DeleteObject не потрібен. На ЗБОЇ ОС регіон НЕ
        приймає — володіння лишається за нами, тому звільняємо його вручну,
        інакше кожен збій = витік GDI-об'єкта.
        """
        hrgn = _gdi32.CreateRoundRectRgn(0, 0, width, height, radius * 2, radius * 2)
        if not hrgn:
            return False
        if _user32.SetWindowRgn(hwnd, hrgn, redraw) == 0:
            _gdi32.DeleteObject(hrgn)
            return False
        return True

    @staticmethod
    def round_corners(window):
        """Накладає округлий регіон на все вікно.

        Радіус не параметр: його дає _outline_radius_px — те саме число, яким
        CTk малює контур на main_frame. Доки обидва беруться звідти, зріз
        регіону і намальована дуга збігаються ЗА ПОБУДОВОЮ, а не завдяки збігу
        двох незалежних перерахунків масштабу (саме він і розсинхронізувався
        при зміні DPI — див. _outline_radius_px).

        Викликається в кінці КОЖНОГО ресайзу і при відновленні з трея, тож
        друкуємо лише на збої — інакше success-рядок спамив би logger.log
        (у windowed-збірці файл має ліміт MAX_BYTES).

        Годиться для будь-якого безрамкового вікна застосунку, а не лише для
        головного: попап бургер-меню кладе на себе ті самі `_outline_frame` /
        `_outline_radius` і кличе цей же метод.
        """
        hwnd = _user32.GetParent(window.winfo_id())
        radius = WindowHandler._outline_radius_px(window)
        width, height = window.winfo_width(), window.winfo_height()
        if WindowHandler._set_corner_region(hwnd, width, height, radius):
            # Стан, під який регіон реально накладено. Його звіряє
            # ensure_corner_region, щоб не смикати Win32 на кожен <Configure>
            # (вони йдуть і на переміщення вікна, де нічого не змінюється).
            # РАДІУС у стані обов'язковий: при зміні DPI розмір вікна може
            # лишитися той самий, а радіус дуги — ні, і перевірка лише за
            # розміром пропустила б саме той випадок, який ламає кути.
            window._corner_region = (width, height, radius)
        else:
            print("[round_corners] SetWindowRgn failed")

    @staticmethod
    def start_move(event: tk.Event, root: ctk.CTk):
        """
        Зберігає початкову позицію курсора відносно вікна
        для подальшого переміщення.
        """
        root._start_move_x = event.x_root - root.winfo_x()
        root._start_move_y = event.y_root - root.winfo_y()

    @staticmethod
    def do_move(event: tk.Event, root: ctk.CTk):
        """
        Переміщує вікно відповідно до руху курсора.
        """
        if not root.overrideredirect():
            return

        # Якщо активний ресайз краю — не рухаємо вікно. Обробники move (на
        # заголовку/фреймі) і resize (на root) прив'язані обидва, і в зоні
        # краю спрацьовували б разом, даючи дрож «рух + зміна розміру».
        if getattr(root, "_resize_dir", None):
            return

        new_x_logical = event.x_root - root._start_move_x
        new_y_logical = event.y_root - root._start_move_y

        root.geometry(f"+{new_x_logical}+{new_y_logical}")

    @staticmethod
    def bind_resize_events(root: ctk.CTk):
        """
        Прив'язує події ресайзу (зміна розміру вікна) до кореневого вікна.

        Move-прив'язки (перетягування за заголовок) тут НЕ ставляться: їх вішає
        ErrorWindow.bind_events напряму на file_label і main_frame, де є прямі
        посилання на віджети. Раніше цей метод ще й дублював їх, шукаючи заголовок
        за жорстко зашитим Tk-шляхом ".!ctkframe.!ctklabel" — крихким до зміни
        ієрархії віджетів; ті самі хендлери одразу перезаписувались у bind_events,
        тож lookup був зайвий і лише створював точку мовчазної деградації.
        """
        # Події для ресайзу (зміна розміру вікна)
        resize_handlers = [
            ("<Motion>", WindowHandler.change_cursor),  # Зміна курсора при наведенні на край
            ("<ButtonPress-1>", WindowHandler.start_resize),  # Початок ресайзу
            ("<B1-Motion>", WindowHandler.do_resize),  # Виконання ресайзу
            ("<ButtonRelease-1>", WindowHandler.stop_resize),  # Завершення ресайзу
        ]

        # Прив'язуємо події ресайзу безпосередньо до кореневого вікна.
        for event_type, handler_func in resize_handlers:
            root.bind(event_type, handler_func)

        # add="+" ОБОВ'ЯЗКОВИЙ: <Configure> на root вішає ще й LogTrackerApp
        # (дебаунс збереження геометрії). Прив'язка без add= стирає всі
        # попередні, тож обидві сторони мусять додавати, а не заміщати.
        root.bind("<Configure>", WindowHandler._sync_corner_region, add="+")

    @staticmethod
    def ensure_corner_region(root):
        """Приводить округлий регіон у відповідність поточному розміру вікна І
        поточному радіусу дуги, яку малює CTk. No-op, якщо вже збігається.

        Регіон — це жорсткий кліп фіксованого розміру, тож щойно вікно змінює
        розмір без нового SetWindowRgn, форма розходиться з вікном: більше вікно
        обрізається по старій межі (прямий зріз без кутів), менше — лишається з
        квадратними кутами, а поверх них видно фон канви CTk (у light це gray92,
        помітно сіріший за паперовий фон) — ті самі «порожні кути». Так само
        розходиться і РАДІУС: при зміні DPI CTk перемальовує дугу під новий
        масштаб, і регіон зі старим радіусом дає в кожному куті дві дуги.

        Раніше регіон оновлювали лише три місця: побудова вікна, кінець ресайзу
        і відновлення з трея. Геометрію ж міняють і інші: `_reapply_saved_geometry`
        (запобіжник від «замалого вікна» на старті) і сам CTk у `check_dpi_scaling`
        при зміні DPI — головний сценарій цього застосунку (реконект RDP). Після
        них регіон лишався від попереднього розміру.
        """
        if not root.overrideredirect():
            return
        # Під час ЖЕСТУ ресайзу регіон веде _apply_resize_frame — щокадру, разом
        # із перемальовкою. Другий SetWindowRgn на ту саму подію лише додав би
        # роботи на кожен рух миші.
        #
        # Ознака жесту — _resize_scale (ставить start_resize, знімає stop_resize),
        # а НЕ _resize_dir: той виставляє change_cursor на КОЖЕН <Motion> у зоні
        # краю, тобто на просте наведення без кліку. Курсор, що пішов з вікна
        # через край, лишав _resize_dir виставленим назавжди (нових Motion уже
        # нема, скинути нікому) — і синхронізація регіону мовчки вимикалась до
        # наступного кліку. Саме так регіон і переживав зміну DPI зі старим
        # радіусом, даючи подвійну дугу в кутах.
        if getattr(root, "_resize_scale", None):
            return
        state = (root.winfo_width(), root.winfo_height(),
                 WindowHandler._outline_radius_px(root))
        if state == getattr(root, "_corner_region", None):
            return  # <Configure> сипле і на переміщення — там регіон не чіпаємо
        WindowHandler.round_corners(root)

    @staticmethod
    def _sync_corner_region(event: tk.Event):
        """<Configure> на root → перевірити регіон (див. ensure_corner_region)."""
        root = event.widget
        if isinstance(root, ctk.CTk):
            WindowHandler.ensure_corner_region(root)

    @staticmethod
    def _header_bottom(root):
        """Нижня Y-межа заголовка у координатах вікна (фізичні px) = верх
        контент-фрейму. Уся смуга над нею — зона ПЕРЕМІЩЕННЯ вікна, а не
        ресайзу. Якщо межу не визначити — 0 (зони заголовка нема, поведінка
        як раніше)."""
        content = getattr(root, "_content_frame", None)
        if content is not None:
            try:
                return content.winfo_rooty() - root.winfo_rooty()
            except Exception:
                pass
        return 0

    @staticmethod
    def change_cursor(event: tk.Event):
        """
        Змінює вигляд курсора на краю вікна для вказівки на можливість ресайзу.
        """
        root = WindowHandler._event_root(event)
        if root is None:
            return
        # Якщо вікно має рамку (не overrideredirect), ОС сама керує курсором.
        if not root.overrideredirect():
            root.configure(cursor="")
            root._resize_dir = None
            return

        # Кнопки й поля вводу самі обробляють клік (див. _CLICKABLE_WIDGETS) —
        # там ані ресайзу, ані переміщення. Перевіряємо ДО зони заголовка, бо
        # кнопки згорнути/бургер лежать саме в ній.
        if WindowHandler._is_clickable_widget(event):
            root.configure(cursor="")
            root._resize_dir = None
            return

        # Координати курсора відносно ВІКНА (у фізичних пікселях, як і winfo_*).
        x_logical = event.x_root - root.winfo_rootx()
        y_logical = event.y_root - root.winfo_rooty()
        width_logical = root.winfo_width()
        height_logical = root.winfo_height()

        # Уся смуга заголовка (над контентом) — зона ПЕРЕМІЩЕННЯ: і текст
        # заголовка, і порожній фон рухають вікно (move-прив'язки заголовка та
        # main_frame самі це роблять), тож resize-курсор тут не показуємо й
        # напрямок не ставимо. Ресайз лишається на нижньому/бічних краях.
        if y_logical < WindowHandler._header_bottom(root):
            root.configure(cursor="")
            root._resize_dir = None
            return

        # Зона краю ~20 логічних px: множимо на масштаб, інакше при DPI 200%
        # смуга захоплення була б лише ~10 фізичних px — важко влучити,
        # надто трекпадом через RDP. _window_scale читає кеш CTk, без Win32.
        border = int(20 * WindowHandler._window_scale(root))

        cursor = ""
        root._resize_dir = None  # Скидаємо напрямок ресайзу

        # Визначаємо зону й ставимо СТАНДАРТНИЙ віндовсний курсор ресайзу.
        # Ці Tk-імена мапляться на нативні курсори Windows:
        #   size_nw_se -> IDC_SIZENWSE (⤡), size_ne_sw -> IDC_SIZENESW (⤢),
        #   size_we    -> IDC_SIZEWE   (↔), size_ns    -> IDC_SIZENS   (↕).
        # Раніше стояло "sizing <напрямок>": друге слово Tk ігнорує, тож усі
        # зони показували один 4-стрілковий IDC_SIZEALL, а не напрямкові.
        if x_logical <= border and y_logical <= border:
            cursor = "size_nw_se"
            root._resize_dir = "nw"
        elif x_logical >= width_logical - border and y_logical <= border:
            cursor = "size_ne_sw"
            root._resize_dir = "ne"
        elif x_logical <= border and y_logical >= height_logical - border:
            cursor = "size_ne_sw"
            root._resize_dir = "sw"
        elif x_logical >= width_logical - border and y_logical >= height_logical - border:
            cursor = "size_nw_se"
            root._resize_dir = "se"
        elif x_logical <= border:
            cursor = "size_we"
            root._resize_dir = "w"
        elif x_logical >= width_logical - border:
            cursor = "size_we"
            root._resize_dir = "e"
        elif y_logical <= border:
            cursor = "size_ns"
            root._resize_dir = "n"
        elif y_logical >= height_logical - border:
            cursor = "size_ns"
            root._resize_dir = "s"

        root.configure(cursor=cursor or "")

    @staticmethod
    def start_resize(event: tk.Event):
        root = WindowHandler._event_root(event)
        if root is None:
            return

        # Клік по кнопці чи в поле вводу — це клік, а не початок ресайзу або
        # переміщення (див. _CLICKABLE_WIDGETS). Перевіряємо ДО зони заголовка,
        # бо кнопки згорнути/бургер лежать саме в ній.
        if WindowHandler._is_clickable_widget(event):
            root._resize_dir = None
            return

        # Кешуємо масштаб на весь жест: DPI монітора під час одного
        # перетягування не змінюється, тож не смикаємо Win32 на кожну подію.
        scale = WindowHandler._window_scale(root)

        x_logical = event.x_root - root.winfo_rootx()
        y_logical = event.y_root - root.winfo_rooty()
        width_logical = root.winfo_width()
        height_logical = root.winfo_height()
        border = int(20 * scale)

        # Уся смуга заголовка (над контентом) — зона ПЕРЕМІЩЕННЯ, не ресайзу:
        # move-прив'язки заголовка/main_frame самі рухатимуть вікно, а ми лише
        # не вмикаємо тут ресайз. Ресайз лишається на нижньому/бічних краях.
        if y_logical < WindowHandler._header_bottom(root):
            root._resize_dir = None
            return

        # Визначаємо напрямок ресайзу на основі позиції курсора в момент кліка
        root._resize_dir = None
        if x_logical <= border and y_logical <= border:
            root._resize_dir = "nw"
        elif x_logical >= width_logical - border and y_logical <= border:
            root._resize_dir = "ne"
        elif x_logical <= border and y_logical >= height_logical - border:
            root._resize_dir = "sw"
        elif x_logical >= width_logical - border and y_logical >= height_logical - border:
            root._resize_dir = "se"
        elif x_logical <= border:
            root._resize_dir = "w"
        elif x_logical >= width_logical - border:
            root._resize_dir = "e"
        elif y_logical <= border:
            root._resize_dir = "n"
        elif y_logical >= height_logical - border:
            root._resize_dir = "s"

        # Якщо ми не в зоні ресайзу, виходимо
        if not root.overrideredirect() or not root._resize_dir:
            root._resize_dir = None  # Впевнюємося, що напрямок скинуто
            return
        # --- КІНЕЦЬ НОВОЇ ЛОГІКИ ---

        # Округлення НЕ скидаємо: регіон тепер тримається живим і
        # перераховується щокадру в _apply_resize_frame під новий розмір, тож
        # кути лишаються скругленими протягом усього жесту. (Раніше тут стояв
        # SetWindowRgn(hwnd, 0) — квадратні кути аж до stop_resize.)
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())

        root._resize_hwnd = hwnd     # кешуємо hwnd на весь жест (для перемальовки)
        root._resize_scale = scale  # масштаб зафіксовано на весь жест ресайзу
        root._resize_pending = None      # остання відкладена геометрія (тротлінг)
        root._resize_trail_job = None    # трейлінг-таймер фінального кадру
        root._resize_last_paint = 0.0    # час останнього застосованого кадру
        root._start_cursor_x_logical = event.x_root
        root._start_cursor_y_logical = event.y_root
        root._start_width_logical = root.winfo_width()
        root._start_height_logical = root.winfo_height()
        root._start_win_x_logical = root.winfo_x()
        root._start_win_y_logical = root.winfo_y()

    @staticmethod
    def do_resize(event: tk.Event):
        """
        Виконує зміну розміру вікна відповідно до руху курсора.
        """
        root = WindowHandler._event_root(event)
        if root is None:
            return

        # Ознака, що жест РЕАЛЬНО почався, — `_resize_scale`, а не `_resize_dir`:
        # напрямок виставляє `change_cursor` на КОЖЕН `<Motion>` у зоні краю,
        # тобто на просте наведення без кліку, а опорні точки (`_start_*`) кладе
        # лише `start_resize`. Без цієї перевірки досить було провести мишею
        # понад краєм — і будь-який наступний `<B1-Motion>` рахував нову
        # геометрію від опорних точок ПОПЕРЕДНЬОГО жесту, тобто жбурляв вікно в
        # чужий розмір і позицію.
        #
        # Ловилось це так: миша йде до кнопки Save панелі налаштувань низом
        # вікна (там і кнопки, і зона краю), `start_resize` на самій кнопці
        # виходить достроково, кнопка своєю ж командою ховає панель — і
        # найменший порух із затиснутою кнопкою «ресайзив» вікно.
        if not getattr(root, "_resize_scale", None):
            return
        if not getattr(root, "_resize_dir", None):
            return
        if not root.overrideredirect():
            return

        current_cursor_x_logical = event.x_root
        current_cursor_y_logical = event.y_root

        dx_logical = current_cursor_x_logical - root._start_cursor_x_logical
        dy_logical = current_cursor_y_logical - root._start_cursor_y_logical

        dir = root._resize_dir

        # Масштаб зафіксовано в start_resize — не смикаємо Win32 на кожну подію.
        scale = getattr(root, "_resize_scale", None) or WindowHandler._window_scale(root)

        # Мінімум у ФІЗИЧНИХ пікселях, узгоджений з root.minsize(...): CTk
        # застосовує до minsize той самий масштаб, тож OS-мінімум теж
        # (min_logical * scale). Якби межі не збігалися, при ресайзі з заходу/
        # півночі OS клампив би розмір, а x/y усе одно зсувалися б — вікно
        # «повзло» б убік. Висота — динамічна (заголовок + запас під текст, а з
        # відкритою панеллю налаштувань ще й вона), її дає min_height_logical.
        min_width = int(300 * scale)
        min_height = int(WindowHandler.min_height_logical(root) * scale)

        new_width_logical = root._start_width_logical
        new_height_logical = root._start_height_logical
        new_x_logical = root._start_win_x_logical
        new_y_logical = root._start_win_y_logical

        if "e" in dir:  # East (right)
            new_width_logical = max(root._start_width_logical + dx_logical, min_width)
        if "s" in dir:  # South (bottom)
            new_height_logical = max(root._start_height_logical + dy_logical, min_height)

        if "w" in dir:  # West (left)
            potential_new_width = root._start_width_logical - dx_logical
            if potential_new_width >= min_width:
                new_width_logical = potential_new_width
                new_x_logical = root._start_win_x_logical + dx_logical
            else:
                new_width_logical = min_width
                new_x_logical = root._start_win_x_logical + root._start_width_logical - min_width

        if "n" in dir:  # North (top)
            potential_new_height = root._start_height_logical - dy_logical
            if potential_new_height >= min_height:
                new_height_logical = potential_new_height
                new_y_logical = root._start_win_y_logical + dy_logical
            else:
                new_height_logical = min_height
                new_y_logical = root._start_win_y_logical + root._start_height_logical - min_height

        # Компенсуємо фізичні розміри, ділячи на масштаб CTk перед geometry()
        # (усередині CTk множить назад). X/Y — фізичні, без ділення.
        final_width_for_geometry = int(new_width_logical / scale)
        final_height_for_geometry = int(new_height_logical / scale)

        # Зберігаємо цільову геометрію й малюємо з ТРОТЛІНГОМ ~60 к/с. Кожен
        # застосований кадр — це `geometry()` + синхронна перемальовка дітей
        # (див. _apply_resize_frame), що недешево, надто по RDP. Миша ж сипле
        # ~100–125 подій/с; без тротлінгу кожна робила б повний erase+repaint
        # шаруватого вікна, і кадри не встигали б — звідси ривки.
        root._resize_pending = (
            f"{final_width_for_geometry}x{final_height_for_geometry}+{int(new_x_logical)}+{int(new_y_logical)}",
            dir,
        )
        now = time.perf_counter()
        if now - getattr(root, "_resize_last_paint", 0.0) >= 0.016:  # leading edge, ~60 к/с
            root._resize_last_paint = now
            WindowHandler._apply_resize_frame(root)
        # Трейлінг: гарантуємо, що остання позиція (можливо, «пропущена»
        # тротлінгом) таки відмалюється, коли рух зупиниться.
        trail = getattr(root, "_resize_trail_job", None)
        if trail is not None:
            root.after_cancel(trail)
        root._resize_trail_job = root.after(24, lambda: WindowHandler._apply_resize_frame(root))

    @staticmethod
    def _apply_resize_frame(root):
        """Застосовує останню відкладену геометрію ресайзу і синхронно
        перемальовує дітей.

        Синхронна перемальовка потрібна, бо кнопки праворуч угорі закріплені
        за правим краєм (grid `sticky "ne"`, колонка з `weight 0`), тож при
        ресайзі змінюється лише їхня ПОЗИЦІЯ, а не розмір. CTk перемальовує
        віджет тільки на зміні РОЗМІРУ (`_update_dimensions_event`), тож
        пересунуті кнопки самі не перемальовуються — на шаруватому вікні вони
        зникають/стрибають. `update()` спершу забирає ConfigureNotify і застосовує
        re-layout (пересуває HWND кнопок), але `WM_PAINT` не обробляє, тому далі
        явно кличемо `RedrawWindow(...UPDATENOW)` — синхронний `WM_PAINT` усім
        дочірнім HWND на вже коректних позиціях.
        """
        # Реентрантність: root.update() нижче прокручує чергу подій, і звідти
        # може прилетіти новий <B1-Motion> → do_resize → знову сюди. Прапорець
        # робить вкладений виклик no-op: він лише оновить _resize_pending, а
        # намалює його зовнішній кадр — і намалює вже НОВІШУ ціль.
        if getattr(root, "_resize_painting", False):
            return
        pending = getattr(root, "_resize_pending", None)
        if not pending:
            return
        geometry_string, dir = pending
        # Кадр коштує повного синхронного перемалювання шаруватого вікна, тож
        # не платимо за нього, коли ціль та сама: миша сипле подіями і на
        # тремтінні в межах пікселя, а трейлінг-таймер приходить із тим самим
        # рядком, який щойно намалював leading edge.
        if geometry_string == getattr(root, "_resize_applied", None):
            return
        hwnd = getattr(root, "_resize_hwnd", None)

        root._resize_applied = geometry_string
        root._resize_painting = True
        try:
            root.geometry(geometry_string)
            # update(), а НЕ update_idletasks(): про новий розмір Tk дізнається
            # з ConfigureNotify, а це ЗВИЧАЙНА подія, не idle-таск. Забрати її
            # може лише update(). З update_idletasks Tk ще не переклав дітей під
            # новий розмір, і кадр малювався зі СТАРОЮ розкладкою на вже новому
            # вікні: намальований контур вікна й кнопки відставали від справжнього
            # краю на кадр — «привид» контуру, що тягнеться за курсором. Поки
            # рамки не було, відставання ховав однорідний фон; з контуром по
            # самому краю воно стало помітним. Ще один наслідок: winfo_width/
            # height нижче теж були б застарілі, тобто й РЕГІОН ліг би під
            # старий розмір.
            root.update()

            if hwnd:
                # Тримаємо округлення ЖИВИМ під час ресайзу: регіон перераховуємо
                # під новий ФІЗИЧНИЙ розмір щокадру (після update() winfo_* уже
                # оновлені), тож він завжди збігається з вікном і кутів не
                # обрізає. bRedraw=False — тут не малюємо, це зробить наступний
                # RedrawWindow (одна перемальовка на кадр, без подвійної).
                # Радіус — з того самого _outline_radius_px, що й поза жестом:
                # інакше кути протягом ресайзу мали б інший радіус, ніж дуга,
                # яку CTk малює тим самим кадром.
                WindowHandler._set_corner_region(
                    hwnd, root.winfo_width(), root.winfo_height(),
                    WindowHandler._outline_radius_px(root), redraw=False,
                )

                RDW_INVALIDATE, RDW_ERASE, RDW_ALLCHILDREN, RDW_UPDATENOW = 0x1, 0x4, 0x80, 0x100
                flags = RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_UPDATENOW
                # ERASE — лише для заходу/півночі, де рухається початок вікна:
                # там контент їде екраном і майже-чорні згладжені краї тексту
                # хедера (не keyʼяться в прозорість ключем "#000001") лишають
                # слід на старому місці; стирання фону його прибирає. На сході/
                # півдні початок не рухається — зайвий erase лише додав би
                # мерехтіння (виміряно: з ним кадр не стає чистішим).
                if "w" in dir or "n" in dir:
                    flags |= RDW_ERASE
                ctypes.windll.user32.RedrawWindow(hwnd, None, None, flags)

                # RedrawWindow(...UPDATENOW) лише РОЗСИЛАЄ WM_PAINT; Tk перетворює
                # його на свою подію Expose і малює вже у власному циклі подій.
                # Без прокрутки циклу кадр лишався НЕДОМАЛЬОВАНИМ: край вікна
                # виходив без рамки, а нижній/правий кут — без округлення, і
                # домальовувалось воно лише наступним оборотом циклу, тобто
                # «наздоганяло» курсор. Вимірювання (кадр ресайзу проти чесної
                # повної перемальовки того самого розміру): без цього update()
                # ~272k відмінних пікселів за 20 кадрів, з ним — рівно 0.
                root.update()
        finally:
            root._resize_painting = False

    @staticmethod
    def stop_resize(event: tk.Event):
        root = WindowHandler._event_root(event)
        if root is None:
            return

        # Жесту не було — не пишемо ini на кожен клік і не перемальовуємо кути,
        # лише скидаємо курсор. Ознака та сама, що й у do_resize: `_resize_scale`
        # ставить ЛИШЕ start_resize, тоді як `_resize_dir` лишається виставленим
        # від простого наведення на край (і на кліку по кнопці в тій зоні теж).
        if not getattr(root, "_resize_scale", None):
            root._resize_dir = None
            root.configure(cursor="")
            return

        # Скасовуємо трейлінг-таймер і застосовуємо ФІНАЛЬНИЙ кадр: остання
        # подія руху могла бути «пропущена» тротлінгом, тож без цього вікно
        # завмерло б на передостанній позиції до кінця жесту.
        trail = getattr(root, "_resize_trail_job", None)
        if trail is not None:
            root.after_cancel(trail)
            root._resize_trail_job = None
        WindowHandler._apply_resize_frame(root)

        # Оновлюємо реальні розміри перед clamp/заокругленням: після geometry()
        # у do_resize winfo_* могли ще не оновитися.
        root.update_idletasks()

        # Підстраховка: якщо вікно якось опинилося фактично поза екраном —
        # повертаємо його всередину. Перевіряємо саме видимість (а не «цілком
        # уміщається»), щоб звичайний ресайз за правий/нижній край не смикав
        # протилежну межу.
        cur_x, cur_y = root.winfo_x(), root.winfo_y()
        cur_w, cur_h = root.winfo_width(), root.winfo_height()
        if not rdp.is_rect_visible(cur_x, cur_y, cur_w, cur_h):
            nx, ny = rdp.clamp_to_visible(cur_x, cur_y, cur_w, cur_h)
            root.geometry(f"+{nx}+{ny}")
            root.update_idletasks()

        WindowHandler.save_window_size('Window', root)
        root._resize_dir = None
        root._resize_scale = None
        root._resize_hwnd = None
        root._resize_pending = None
        root._resize_applied = None  # наступний жест починає рахунок кадрів заново
        root.configure(cursor="")  # Повертаємо курсор до стандартного вигляду

        # Повертаємо округлення після завершення ресайзу (фінальний чистий
        # регіон під точний кінцевий розмір; під час жесту воно вже було живе).
        # Заразом це перший запис у _corner_region після жесту: під час нього
        # регіон вела _apply_resize_frame, не оновлюючи стан.
        if root.overrideredirect():
            WindowHandler.round_corners(root)
