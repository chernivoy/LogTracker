def create_text_window():
    root = ctk.CTk()  # Используем customtkinter
    root.title("Файлы в целевой директории")
    root.attributes('-topmost', True)
    load_window_size(root)

    main_frame = ctk.CTkFrame(root)  # Используем CTkFrame вместо ttk.Frame
    main_frame.pack(fill="both", expand=True, padx=20, pady=20)

    pin_button = ctk.CTkButton(main_frame, text="Unpin", command=lambda: toggle_pin(root, pin_button))
    pin_button.grid(row=0, column=0, padx=5, pady=5, sticky="ne")

    minimize_button = ctk.CTkButton(main_frame, text="To Tray", command=lambda: minimize_to_tray(root))
    minimize_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

    file_label = ctk.CTkLabel(main_frame, text="Файл: Не выбран")
    file_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")

    text_widget = ctk.CTkTextbox(main_frame, wrap="word", height=20)  # Используем CTkTextbox вместо tk.Text
    text_widget.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

    error_text_widget = ctk.CTkTextbox(main_frame, wrap="word", height=20, state="disabled")  # Используем CTkTextbox вместо tk.Text
    error_text_widget.grid(row=3, column=0, padx=5, pady=5, sticky="nsew")

    main_frame.grid_rowconfigure(2, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)

    return root, text_widget, error_text_widget, file_label