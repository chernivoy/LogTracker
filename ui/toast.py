import time

import customtkinter as ctk

from ui.window_handler import WindowHandler


class Toast:
    """Плашка-підтвердження («Copied!») ВСЕРЕДИНІ головного вікна.

    Це звичайний CTk-віджет поверх контенту (`place`), а не окремий Toplevel.
    Окреме вікно поводилось як чужий об'єкт: висіло над рамкою, не рухалося
    разом із застосунком і не обрізалося його межами. Оверлей же належить
    вікну — їде з ним, ховається з ним у трей і не може опинитися «поруч».

    Місць два — за числом дій, які плашка підтверджує, і кожна показується
    ТАМ, КУДИ КОРИСТУВАЧ КЛІКНУВ:

    - `show_in_header()` — у смузі заголовка, одразу за іменем файла (Ctrl+клік
      по заголовку копіює файл). Тексту помилки не накриває, бо той друкується
      з лівого верхнього краю поля й переноситься вниз;
    - `show_in_field()` — по центру поля помилки (Ctrl+клік по полю копіює його
      текст). Тут накривати нема чого: текст щойно скопійований, а плашка
      живе 1.4 с.

    Контейнером кожного разу є той віджет, у якому плашка стоїть, тож фон під
    нею — рівно той, що цей віджет рендерить (важливо для згасання).

    **DPI.** Тут майже нема ручного масштабування: `place`/`grid` CustomTkinter
    самі множать `x`/`y`/`padx`/`pady` на масштаб віджетів, а шрифт із теми
    масштабує сам `CTkLabel` — та сама рідна модель, що й у решті вікна.
    Позицію задаємо у ВІДНОСНИХ `relx`/`rely` (частки розміру контейнера) —
    CTk їх не чіпає й не мусить: співвідношення однакове на будь-якому DPI, а
    `winfo_*`, з яких вони рахуються, фізичні і в чисельнику, і в знаменнику,
    тож масштаб скорочується. Вручну множимо лише зазор `_GAP`, бо він заданий
    логічним, а порівнюється з фізичними `winfo_*`.

    **Тема.** Стиль читається з `current_theme_data` при КОЖНОМУ показі (ключі
    `toast_*`), тож плашка завжди в актуальній темі. Реєструвати її в
    `ThemeManager.update_widgets_theme` не треба — вона живе ~1.4 с і в момент
    перемикання теми просто не існує (той самий виняток, що й SettingsWindow).
    """

    _VISIBLE_MS = 1200  # скільки висить на повному кольорі
    _FADE_OUT_MS = 220
    _FRAME_MS = 16  # ~60 к/с, як тротлінг ресайзу в WindowHandler

    # ЛОГІЧНІ px: CTk домножить padx/pady сам, зазор — вручну (див. _placement).
    # Вертикальний відступ малий навмисно: плашка мусить уміщатися у ВИСОТУ
    # смуги заголовка, інакше вона звисала б у поле помилки.
    _PAD_X = 10
    _PAD_Y = 2
    _GAP = 8  # зазор між іменем файла і плашкою (і до кнопок праворуч)
    _CORNER_RADIUS = 10
    # Волосяна рамка: фон плашки навмисно близький до фону заголовка (щоб не
    # випадати з теми), тож саме рамка окреслює її як окрему поверхню.
    _BORDER_WIDTH = 1

    def __init__(self, root, theme_manager, header_anchor, header_limit, field,
                 bind_move=None):
        """Віджети, відносно яких плашка стає, задаються один раз тут — щоб
        викликачу лишалося тільки сказати, ЯКУ дію він підтверджує.

        `header_anchor` — мітка з іменем файла (у заголовку стаємо одразу за
        нею), `header_limit` — перший віджет праворуч (кнопки), далі якого
        залазити не можна, `field` — поле помилки (у ньому центруємось).

        `bind_move` — необов'язковий колбек, яким власник вікна вішає на
        плашку ті самі прив'язки перетягування, що й на решту заголовка:
        уся смуга заголовка є зоною переміщення вікна, і плашка не повинна
        робити в ній «мертвий» прямокутник на час показу. Для плашки в полі
        помилки він не потрібен — поле вікна не рухає.
        """
        self._root = root
        self._theme_manager = theme_manager
        self._header_anchor = header_anchor
        self._header_limit = header_limit
        self._field = field
        self._bind_move = bind_move
        self._frame = None
        self._label = None
        self._job = None

    def show_in_header(self, text):
        """Плашка в смузі заголовка, одразу за іменем файла."""
        # Контейнер — той самий, у якому лежить мітка: так плашка стає з нею
        # в один рядок, а координати обох відлічуються від спільного початку.
        self._show(text, self._header_anchor.master, self._header_placement,
                   draggable=True)

    def show_in_field(self, text):
        """Плашка по центру поля помилки."""
        self._show(text, self._field, self._center_placement)

    def _show(self, text, parent, placement, draggable=False):
        """Спільна побудова плашки: `placement` віддає аргументи place().

        Повторний виклик перебиває попередню плашку (нове натискання скидає
        таймер), а не громадить другу поверх неї — байдуже, у якому з двох
        місць вона стояла.
        """
        self.hide()
        try:
            theme = self._theme_manager.current_theme_data

            self._frame = ctk.CTkFrame(
                parent,
                fg_color=theme["toast_bg"],
                border_color=theme["toast_border_color"],
                border_width=self._BORDER_WIDTH,
                corner_radius=self._CORNER_RADIUS,
            )
            self._label = ctk.CTkLabel(
                self._frame,
                text=text,
                text_color=theme["toast_text_color"],
                font=theme["toast_font"],
            )
            self._label.grid(row=0, column=0, padx=self._PAD_X, pady=self._PAD_Y)

            # Розмір потрібен ДО place: за ним рахуємо, чи влазить плашка між
            # іменем файла і кнопками. До update_idletasks reqwidth ще нульовий.
            self._frame.update_idletasks()
            self._frame.place(**placement())
            # Плашка створена після решти віджетів, але lift() робить порядок
            # явним — інакше він залежав би від черговості створення.
            self._frame.lift()

            # У заголовку плашка стоїть у зоні перетягування вікна: без цих
            # прив'язок вона робила б у ній «мертвий» прямокутник, за який
            # вікно не рухається.
            if draggable and self._bind_move is not None:
                self._bind_move(self._frame)
                self._bind_move(self._label)

            self._job = self._root.after(self._VISIBLE_MS, self._fade_out)
        except Exception as e:
            # Плашка — суто косметика: її збій не має валити дію, яку вона
            # підтверджує (файл уже в буфері).
            print(f"Cannot show toast: {e}")
            self.hide()

    def hide(self):
        """Прибирає плашку і скасовує заплановані кадри згасання."""
        if self._job is not None:
            try:
                self._root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._frame is not None:
            try:
                self._frame.destroy()
            except Exception:
                pass
            self._frame = None
            self._label = None

    def _center_placement(self):
        """Аргументи place(): точний центр контейнера.

        Суто відносні координати — ані розміру плашки, ані масштабу DPI тут
        не треба: центр лишається центром при будь-якому розмірі вікна, тож
        плашка сама тримається посередині й під час ресайзу.
        """
        return {"relx": 0.5, "rely": 0.5, "anchor": "center"}

    def _header_placement(self):
        """Аргументи place(): одразу за іменем файла, по центру заголовка.

        Ліва межа — правий край мітки з іменем плюс зазор. Ширина мітки
        натуральна (`sticky="nw"`), тож її правий край і є кінцем тексту
        (`.log`), під який вписує ім'я `_fit_header_text`.

        Права межа — кнопки заголовка: далі за них плашка залазити не може,
        тому при довгому імені вона зсувається ліворуч і накриває хвіст
        назви. Це свідомий обмін: кнопки мусять лишатись клікабельними, а
        ім'я користувач і так щойно прочитав. Якщо місця не лишилось зовсім
        (дуже вузьке вікно) — притискаємо до лівого краю.

        Вертикаль — центр мітки, тобто плашка стоїть у рядок із заголовком.

        Позиція у ВІДНОСНИХ relx/rely (частках розміру контейнера): CTk їх не
        масштабує й не мусить, а масштаб у частці скорочується, бо winfo_*
        фізичні і зверху, і знизу. Зазор заданий логічним, тому множимо його.
        """
        anchor, parent = self._header_anchor, self._header_anchor.master
        parent_w = max(1, parent.winfo_width())
        parent_h = max(1, parent.winfo_height())
        gap = self._GAP * WindowHandler._window_scale(self._root)

        x = anchor.winfo_x() + anchor.winfo_width() + gap
        limit = self._header_limit.winfo_x() - gap - self._frame.winfo_reqwidth()
        x = max(0, min(x, limit))
        y = anchor.winfo_y() + anchor.winfo_height() / 2

        return {"relx": x / parent_w, "rely": y / parent_h, "anchor": "w"}

    def _fade_out(self):
        """Розчиняє плашку у фоні під нею й прибирає її.

        Прозорості в окремого віджета Tk немає (`-alpha` є лише у вікна, і
        чіпати її не можна — це альфа ВСЬОГО вікна з теми), тож згасання
        робимо змішуванням кольорів із фоном контейнера. Ведемо ВСІ три
        кольори плашки — фон, рамку і текст: інакше поверхня розчинилася б, а
        контур і напис лишилися б висіти чіткими.

        Якщо фон визначити не вдалося (нетиповий колір теми) — просто ховаємо
        без анімації: це косметика, вона не варта ризику.
        """
        backdrop = self._backdrop_color()
        if backdrop is None:
            self.hide()
            return

        theme = self._theme_manager.current_theme_data
        start_bg = theme["toast_bg"]
        start_fg = theme["toast_text_color"]
        start_border = theme["toast_border_color"]
        started = time.perf_counter()

        def step():
            # Плашку могли прибрати (нове натискання, вихід) між кадрами.
            if self._frame is None or not self._frame.winfo_exists():
                return
            # Прогрес рахуємо за РЕАЛЬНИМ часом, а не за номером кадру: крок
            # таймера Windows ~15.6 мс, тож after(16) фактично спрацьовує
            # приблизно раз на 31 мс, і лічильник кадрів розтягнув би згасання
            # удвічі проти заявленого. Так тривалість витримується, а кадрів
            # просто менше.
            ratio = min(1.0, (time.perf_counter() - started) * 1000 / self._FADE_OUT_MS)
            # Рамку веземо разом з фоном: інакше плашка розчинилася б, а
            # контур лишився б висіти в заголовку до самого кінця.
            self._frame.configure(
                fg_color=self._mix(start_bg, backdrop, ratio),
                border_color=self._mix(start_border, backdrop, ratio),
            )
            self._label.configure(text_color=self._mix(start_fg, backdrop, ratio))
            if ratio < 1.0:
                self._job = self._root.after(self._FRAME_MS, step)
            else:
                self.hide()

        step()

    def _backdrop_color(self):
        """Колір, який РЕАЛЬНО намальовано під плашкою (None, якщо не вийшло).

        Питаємо його в самого CustomTkinter: у темах фон контейнера часто
        "transparent" (у dark прозорі всі шари), і тоді видно дефолтний фон
        вікна CTk — та сама пастка, що з `settings_bg`/`context_menu_bg`.
        `_detect_color_of_master` проходить цей ланцюг за нас. Кортеж
        (light, dark) розкриваємо за поточним режимом.

        Повертаємо колір як є, БЕЗ вимоги до формату '#rrggbb': CTk цілком
        може віддати назву кольору Tk (дефолтний фон вікна — саме 'gray14'),
        і саме на цьому згасання в dark мовчки вимикалось. Перекладає обидві
        форми в числа `winfo_rgb` у `_mix`; тут лише перевіряємо, що Tk такий
        колір узагалі розуміє.
        """
        try:
            color = self._frame._detect_color_of_master()
            if isinstance(color, (tuple, list)):
                color = color[0] if ctk.get_appearance_mode() == "Light" else color[1]
            self._frame.winfo_rgb(color)
            return color
        except Exception:
            return None

    def _mix(self, color, target, ratio):
        """Змішує два кольори Tk ('#rrggbb' або назва на кшталт 'gray14').

        ratio=0 — перший колір, ratio=1 — другий. winfo_rgb віддає 16 біт на
        канал, тож ділимо на 257, щоб отримати звичайні 0..255.
        """
        start = self._frame.winfo_rgb(color)
        end = self._frame.winfo_rgb(target)
        return "#%02x%02x%02x" % tuple(
            round((x + (y - x) * ratio) / 257) for x, y in zip(start, end)
        )
