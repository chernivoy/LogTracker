def create_text_window_old():
    ctk.set_appearance_mode("dark")
    # ctk.deactivate_automatic_dpi_awareness()
    # ctk.set_window_scaling(0.5)
    # ctk.set_widget_scaling(0.5)
    global root
    root = ctk.CTk()
    # root.tk.call('tk', 'scaling', 0.5)
    root.title("Logs")
    root.attributes('-topmost', True)
    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))

    load_window_size(root)

    main_frame = ctk.CTkFrame(root)
    main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    pin_button = ctk.CTkButton(main_frame, text="Unpin", command=lambda: toggle_pin(root, pin_button))
    pin_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

    minimize_button = ctk.CTkButton(main_frame, text="To Tray", command=lambda: minimize_to_tray(root))
    minimize_button.grid(row=0, column=2, padx=5, pady=5, sticky="ne")


    file_label = ctk.CTkLabel(main_frame, text="File1: ", anchor="w")
    file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

    error_frame = ctk.CTkFrame(main_frame)
    error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)

    error_label = ctk.CTkLabel(error_frame, text="ERR:", anchor="w")
    error_label.pack(side="left", padx=(10, 0))

    error_text_widget_frame = ctk.CTkFrame(error_frame)
    error_text_widget_frame.pack(fill="both", expand=True)

    error_text_widget = ctk.CTkTextbox(error_text_widget_frame, height=4, wrap="word", state="disabled")
    error_text_widget.pack(fill="both", expand=True, padx=5)

    text_widget_frame = ctk.CTkFrame(main_frame)
    text_widget_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)

    text_widget = ctk.CTkTextbox(text_widget_frame, wrap="none")
    text_widget.pack(fill="both", expand=True)

    # Настройка растягивания для окна и фреймов
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    main_frame.grid_rowconfigure(0, weight=0)
    main_frame.grid_rowconfigure(1, weight=0)
    main_frame.grid_rowconfigure(2, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=0)

    error_frame.grid_rowconfigure(0, weight=1)
    error_frame.grid_columnconfigure(0, weight=1)

    text_widget_frame.grid_rowconfigure(0, weight=1)
    text_widget_frame.grid_columnconfigure(0, weight=1)

    icon_image = PhotoImage(file="err_pic.png")

    toggle_button = ctk.CTkButton(main_frame, image=icon_image, text="", command=lambda: show_context_menu(root))
    toggle_button.image = icon_image
    toggle_button.grid(row=1, column=2, padx=5, pady=5, sticky="ne")

    return root, text_widget, error_text_widget, file_label

def create_text_window_old2():
    ctk.set_appearance_mode("dark")
    # ctk.deactivate_automatic_dpi_awareness()
    # ctk.set_window_scaling(0.5)
    # ctk.set_widget_scaling(0.5)
    global root
    root = ctk.CTk()
    # root.tk.call('tk', 'scaling', 0.5)
    root.title("Logs")
    root.attributes('-topmost', True)
    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))

    load_window_size(root)

    main_frame = ctk.CTkFrame(root)
    main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    pin_button = ctk.CTkButton(main_frame, text="Pin", command=lambda: toggle_pin(root, pin_button))
    pin_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

    minimize_button = ctk.CTkButton(main_frame, text="To Tray", command=lambda: minimize_to_tray(root))
    minimize_button.grid(row=0, column=2, padx=5, pady=5, sticky="ne")

    file_label = ctk.CTkLabel(main_frame, text="File: ", anchor="w")
    file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

    error_frame = ctk.CTkFrame(main_frame)
    error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)

    error_label = ctk.CTkLabel(error_frame, text="ERR:", anchor="w")
    error_label.pack(side="left", padx=(10, 0))

    error_text_widget_frame = ctk.CTkFrame(error_frame)
    error_text_widget_frame.pack(fill="both", expand=True)

    error_text_widget = ctk.CTkTextbox(error_text_widget_frame, height=4, wrap="word", state="disabled")
    error_text_widget.pack(fill="both", expand=True, padx=5)

    text_widget_frame = ctk.CTkFrame(main_frame)
    text_widget_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)

    text_widget = ctk.CTkTextbox(text_widget_frame, wrap="none")
    text_widget.pack(fill="both", expand=True)

    # Настройка растягивания для окна и фреймов
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    main_frame.grid_rowconfigure(0, weight=0)
    main_frame.grid_rowconfigure(1, weight=1)  # Изменяем weight на 1, чтобы error_frame растягивался
    main_frame.grid_rowconfigure(2, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=0)

    error_frame.grid_rowconfigure(0, weight=1)
    error_frame.grid_columnconfigure(0, weight=1)

    error_text_widget_frame.grid_rowconfigure(0, weight=1)  # Добавляем настройки растягивания для фрейма
    error_text_widget_frame.grid_columnconfigure(0, weight=1)  # Добавляем настройки растягивания для фрейма

    text_widget_frame.grid_rowconfigure(0, weight=1)
    text_widget_frame.grid_columnconfigure(0, weight=1)

    icon_image = PhotoImage(file="err_pic.png")

    toggle_button = ctk.CTkButton(main_frame, image=icon_image, text="", command=lambda: show_context_menu(root))
    toggle_button.image = icon_image
    toggle_button.grid(row=1, column=2, padx=5, pady=5, sticky="ne")

    return root, text_widget, error_text_widget, file_label

def create_text_window_old3():
    ctk.set_appearance_mode("dark")
    global root
    root = ctk.CTk()
    root.title("Logs")
    root.attributes('-topmost', True)
    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))

    load_window_size(root)

    main_frame = ctk.CTkFrame(root)
    main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    pin_button = ctk.CTkButton(main_frame, text="Pin", command=lambda: toggle_pin(root, pin_button))
    pin_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

    minimize_button = ctk.CTkButton(main_frame, text="To Tray", command=lambda: minimize_to_tray(root))
    minimize_button.grid(row=0, column=2, padx=5, pady=5, sticky="ne")

    file_label = ctk.CTkLabel(main_frame, text="File: ", anchor="w")
    file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

    error_frame = ctk.CTkFrame(main_frame)
    error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)

    error_label = ctk.CTkLabel(error_frame, text="ERR:", anchor="w")
    error_label.pack(side="left", padx=(10, 0))

    error_text_widget_frame = ctk.CTkFrame(error_frame)
    error_text_widget_frame.pack(fill="both", expand=True)

    error_text_widget = ctk.CTkTextbox(error_text_widget_frame, height=80, corner_radius=20, border_width=1, border_color="blue", wrap="word", state="disabled")  # Высота 80 пикселей
    error_text_widget.pack(fill="both", expand=True, padx=5)

    text_widget_frame = ctk.CTkFrame(main_frame)
    text_widget_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)

    text_widget = ctk.CTkTextbox(text_widget_frame, wrap="none")
    text_widget.pack(fill="both", expand=True)

    # Настройка растягивания для окна и фреймов
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    main_frame.grid_rowconfigure(0, weight=0)
    main_frame.grid_rowconfigure(1, weight=1)  # Изменяем weight на 1, чтобы error_frame растягивался
    main_frame.grid_rowconfigure(2, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=0)

    error_frame.grid_rowconfigure(0, weight=1)
    error_frame.grid_columnconfigure(0, weight=1)

    text_widget_frame.grid_rowconfigure(0, weight=1)
    text_widget_frame.grid_columnconfigure(0, weight=1)

    icon_image = PhotoImage(file="err_pic.png")

    toggle_button = ctk.CTkButton(main_frame, image=icon_image, text="", command=lambda: show_context_menu(root))
    toggle_button.image = icon_image
    toggle_button.grid(row=1, column=2, padx=5, pady=5, sticky="ne")

    return root, text_widget, error_text_widget, file_label

def create_text_windowOld4():
    ctk.set_appearance_mode("dark")
    global root
    root = ctk.CTk()
    root.title("Logs")
    root.attributes('-topmost', True)
    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))

    load_window_size(root)

    main_frame = ctk.CTkFrame(root)
    main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    pin_button = ctk.CTkButton(main_frame, text="Pin", command=lambda: toggle_pin(root, pin_button))
    pin_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

    minimize_button = ctk.CTkButton(main_frame, text="To Tray", command=lambda: minimize_to_tray(root))
    minimize_button.grid(row=0, column=2, padx=5, pady=5, sticky="ne")

    file_label = ctk.CTkLabel(main_frame, text="File: ", anchor="w")
    file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

    error_frame = ctk.CTkFrame(main_frame)
    error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)

    error_label = ctk.CTkLabel(error_frame, text="ERR:", anchor="w")
    error_label.pack(side="left", padx=(10, 0))

    error_text_widget_frame = ctk.CTkFrame(error_frame)
    error_text_widget_frame.pack(fill="both", expand=True)

    error_text_widget = ctk.CTkTextbox(error_text_widget_frame, height=80, corner_radius=20, border_width=1, border_color="blue", wrap="word", state="disabled")
    error_text_widget.pack(fill="both", expand=True, padx=5)

    text_widget_frame = ctk.CTkFrame(main_frame)
    text_widget_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)
    text_widget_frame.grid_remove()

    text_widget = ctk.CTkTextbox(text_widget_frame, wrap="none")
    text_widget.pack(fill="both", expand=True)

    # Настройка растягивания для окна и фреймов
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    main_frame.grid_rowconfigure(0, weight=0)
    main_frame.grid_rowconfigure(1, weight=1)
    main_frame.grid_rowconfigure(2, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=0)

    error_frame.grid_rowconfigure(0, weight=1)
    error_frame.grid_columnconfigure(0, weight=1)

    text_widget_frame.grid_rowconfigure(0, weight=1)
    text_widget_frame.grid_columnconfigure(0, weight=1)

    icon_image = PhotoImage(file="err_pic.png")
    icon_width = icon_image.width()  # Ширина иконки
    icon_height = icon_image.height()  # Высота иконки

    toggle_button = ctk.CTkButton(main_frame, image=icon_image, text="", height=icon_height, width=icon_width, fg_color="#1a1a1a", corner_radius=40, command=lambda: show_context_menu(root))
    toggle_button.image = icon_image
    toggle_button.grid(row=1, column=2, padx=5, pady=5, sticky="n")

    return root, text_widget, error_text_widget, file_label