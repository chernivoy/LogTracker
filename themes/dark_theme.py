# themes/dark_theme.py
# Налаштування для темної теми
THEME_SETTINGS = {
    "ctk_appearance_mode": "Dark",
    "default_color_theme": "blue",
    "main_frame_fg_color": "transparent",
    # Контур самого вікна — той самий колір, що бордер полів: на крок світліший
    # за те, що вікно реально рендерить (gray14 #242424). У dark вікно й так
    # контрастує з будь-яким світлим тлом, тож роль контуру тут скромніша —
    # окреслити округлені кути, щоб вони читались як край вікна, а не як зріз.
    "window_border_color": "#3a3d42",
    "window_border_width": 1,
    # Window Transparency
    "transparent_color": "#000001",
    "window_alpha": 0.9,
    #Стиль для header_label
    "header_label_text_color": "#5f8dfc",
    "header_label_font": ("Inter", 13, "bold"),
    #Стиль для to_tray_button
    "to_tray_button_text_color": "#ce885f",
    "to_tray_button_font": ("Inter", 11, "bold"),
    "to_tray_button_fg_color": "transparent",
    "to_tray_button_hover_color": "#2d436e",
    #Стиль для burger_button
    "burger_button_text_color": "#ce885f",
    "burger_button_font": ("Inter", 11, "bold"),
    "burger_button_fg_color": "transparent",
    "burger_button_hover_color": "#2d436e",
    #Стиль для error_frame
    "error_frame_fg_color": "transparent",
    # Поле в dark прозоре (немає суцільного фону), тож бордер кольором
    # transparent_color лишав би прозору «щілину», а будь-який інший колір було б
    # видно. Тому рамку тут прибираємо зовсім (width 0) — колір нижче не рендериться.
    "error_frame_border_color": "#000001",
    "error_frame_border_width": 0,
    #Стиль для error_textbox
    "error_textbox_fg_color": "transparent",
    "error_textbox_text_color": "#b4b361",
    "error_textbox_font": ("Inter", 13),
    "error_textbox_border_width": 0,
    "error_textbox_corner_radius": 1,
    #Стиль для context_menu (бургер-меню — власний попап, ui/context_menu.py)
    # Меню — ПІДНЯТА поверхня, як і плашка Toast: воно висить над вікном, має
    # власний контур і скруглені кути, тож фон тут на крок світліший за той, що
    # рендерить вікно (#242424), а не дорівнює йому. (Правило «дочірня поверхня
    # = фон вікна» лишається чинним для settings_bg: те вікно пласке й без
    # контуру, і збіг фонів — єдине, що прив'язує його до головного.)
    "context_menu_bg": "#2b2c2f",
    "context_menu_fg": "#e2e0e6",
    "context_menu_active_bg": "#2d436e",
    "context_menu_active_fg": "#e2e0e6",
    # Контур картки і лінія сепаратора — колір бордера полів, той самий, яким
    # окреслені вікно і плашка.
    "context_menu_border_color": "#3a3d42",
    "context_menu_separator_color": "#3a3d42",
    # Позначка «✓» поточної теми — акцент теми (той самий, що в імені файла).
    "context_menu_accent_color": "#5f8dfc",
    # Стрілка «›» підменю: службовий гліф, приглушений відносно тексту.
    "context_menu_muted_fg": "#8b8a94",
    "context_menu_font": ("Inter", 13),
    #Стиль для settings_window (модальне вікно Path settings)
    # Стиль співпадає з головним вікном. У dark main_frame_fg_color="transparent",
    # тож усі шари головного вікна прозорі й воно показує ДЕФОЛТНИЙ фон вікна CTk
    # для Dark — gray14 (#242424). Саме його беремо тут (а не context_menu_bg
    # #2b2c2f, який світліший), інакше діалог у dark помітно світліший за головне
    # вікно. В інших темах main_frame_fg_color конкретний, і settings_bg дорівнює
    # йому. Текст нейтральний, поля темніші за фон, кнопки — синій акцент.
    "settings_bg": "#242424",
    "settings_text_color": "#e2e0e6",
    "settings_font": ("Inter", 13),
    "settings_entry_fg_color": "#1e1f22",
    "settings_entry_border_color": "#3a3d42",
    "settings_button_fg_color": "#2d436e",
    "settings_button_hover_color": "#375a94",
    "settings_button_text_color": "#e2e0e6",
    #Стиль для toast (плашка «Copied!» у заголовку, одразу за іменем файла)
    # Плашка говорить мовою ПОВЕРХОНЬ теми, а не заливкою акцентом: фон на
    # крок світліший за той, що рендерить вікно (#242424) — «піднята» поверхня,
    # волосяна рамка кольору бордера полів, а колір несе ТЕКСТ, і то рівно той
    # самий акцент, що в імені файла поруч. Залитий акцентний прямокутник у
    # dark виглядав чужим: суцільним кольором тут не залито нічого, акцент
    # живе лише як ховер. Кегль на пункт менший за заголовок і жирний — це
    # короткий службовий сигнал, він не має конкурувати з вмістом вікна.
    "toast_bg": "#2b2c2f",
    "toast_border_color": "#3a3d42",
    "toast_text_color": "#5f8dfc",
    "toast_font": ("Inter", 12, "bold"),
}
