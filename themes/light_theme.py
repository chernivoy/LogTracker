# themes/light_theme.py
# Світла тема у стилі трендів 2026: тепла «паперова» база (#F5F4F1) замість
# чистого білого, багатошаровість (біла контент-картка на паперовому фоні),
# один впевнений акцент — індиго (#4F46E5), і near-black «чорнило» (#1C1C1E)
# замість pure black. Шрифт — Inter (де-факто стандарт UI-типографіки).
THEME_SETTINGS = {
    "ctk_appearance_mode": "Light",
    "default_color_theme": "blue",
    # Тепла паперова база — м'якша за #FFFFFF, дає глибину під білу картку нижче.
    "main_frame_fg_color": "#F5F4F1",
    # Контур самого вікна (безрамкового) — найтемніша сходинка драбини рамок:
    # #E6E4DF (внутрішня картка) → #D6D4CD (поля вводу) → #C9C6BF (край вікна).
    # Саме він тут критичний: на білому тлі паперовий фон майже не відрізнити
    # від робочого столу, а біла картка внизу не відрізнялася зовсім.
    "window_border_color": "#C9C6BF",
    "window_border_width": 1,
    # Window Transparency
    "transparent_color": "#000001",
    "window_alpha": 1,
    #Стиль для header_label
    # Заголовок — акцент-індиго: впізнаваний, «брендовий», сучасний.
    "header_label_text_color": "#4F46E5",
    "header_label_font": ("Inter", 13, "bold"),
    #Стиль для to_tray_button
    # Кнопки — це PNG-іконки з text="", тож видно лише hover_color (фон при
    # наведенні). text_color тримаємо нейтральним «чорнилом» про запас.
    "to_tray_button_text_color": "#3F3E3A",
    "to_tray_button_font": ("Inter", 11, "bold"),
    "to_tray_button_fg_color": "transparent",
    "to_tray_button_hover_color": "#EAE9E4",
    #Стиль для burger_button
    "burger_button_text_color": "#3F3E3A",
    "burger_button_font": ("Inter", 11, "bold"),
    "burger_button_fg_color": "transparent",
    "burger_button_hover_color": "#EAE9E4",
    #Стиль для error_frame
    # Контент — біла картка на паперовому фоні (багатошаровість). Бордер тут
    # НЕ ховаємо (як було раніше), а робимо делікатною волосяною лінією, щоб
    # картка читалась як окрема поверхня.
    "error_frame_fg_color": "#FFFFFF",
    "error_frame_border_color": "#E6E4DF",
    "error_frame_border_width": 1,
    #Стиль для error_textbox
    "error_textbox_fg_color": "transparent",
    # Текст помилки — максимально читабельне «чорнило», без відтінку.
    "error_textbox_text_color": "#1C1C1E",
    "error_textbox_font": ("Inter", 13),
    "error_textbox_border_width": 0,
    "error_textbox_corner_radius": 8,
    #Стиль для context_menu (бургер-меню — власний попап, ui/context_menu.py)
    # Та сама багатошаровість, що в контенті: біла картка над паперовим фоном
    # вікна, з контуром по краю. Ховер — м'який індиго-акцент.
    "context_menu_bg": "#FFFFFF",
    "context_menu_fg": "#1C1C1E",
    "context_menu_active_bg": "#DEE3FB",
    "context_menu_active_fg": "#1C1C1E",
    # Контур картки — сходинка драбини рамок, темніша за лінію сепаратора:
    # меню лягає на довільний вміст екрана, і його межа має читатись певніше
    # за внутрішній розділювач.
    "context_menu_border_color": "#D6D4CD",
    "context_menu_separator_color": "#E6E4DF",
    "context_menu_accent_color": "#4F46E5",
    "context_menu_muted_fg": "#8A8880",
    "context_menu_font": ("Inter", 13),
    #Стиль для settings_window (модальне вікно Path settings)
    # Фон = паперовий фон вікна, поля — чисті білі, кнопки — індиго-акцент.
    "settings_bg": "#F5F4F1",
    "settings_text_color": "#1C1C1E",
    "settings_font": ("Inter", 13),
    "settings_entry_fg_color": "#FFFFFF",
    "settings_entry_border_color": "#D6D4CD",
    "settings_button_fg_color": "#4F46E5",
    "settings_button_hover_color": "#4338CA",
    "settings_button_text_color": "#FFFFFF",
    #Стиль для toast (плашка «Copied!» у заголовку, одразу за іменем файла)
    # Та сама багатошаровість, що й у контенті: біла картка на паперовому фоні
    # заголовка (#F5F4F1) з волосяною лінією по краю — точно як error_frame.
    # Колір несе текст, і то той самий індиго, що в імені файла поруч.
    "toast_bg": "#FFFFFF",
    "toast_border_color": "#E6E4DF",
    "toast_text_color": "#4F46E5",
    "toast_font": ("Inter", 12, "bold"),
}
