import customtkinter as ctk
from tkinter import *

def main():
    # Setting up theme of your app
    ctk.set_appearance_mode("dark")

    root = ctk.CTk()
    root.geometry("300x400")

    # Установите вес для строки и колонки в главном окне
    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)

    label_frame = ctk.CTkFrame(root)
    label_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    label_frame.grid_rowconfigure(0, weight=1)
    label_frame.grid_columnconfigure(0, weight=1)

    label = ctk.CTkLabel(master=label_frame,
                                   textvariable="test",
                                   width=120,
                                   height=25,
                                   fg_color=("white", "gray75"),
                                   corner_radius=8)
    label.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

    err_field_2 = ctk.CTkEntry(
        master=label_frame,
        placeholder_text="ERR",
        width=120,
        height=25,
        border_width=2,
        corner_radius=10
    )
    err_field_2.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    error_frame = ctk.CTkFrame(root)
    error_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

    error_frame.grid_rowconfigure(0, weight=1)
    error_frame.grid_columnconfigure(0, weight=1)

    err_field = ctk.CTkEntry(
        master=error_frame,
        placeholder_text="ERR",
        width=120,
        height=25,
        border_width=2,
        corner_radius=10
    )
    err_field.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    root.mainloop()

if __name__ == "__main__":
    main()
