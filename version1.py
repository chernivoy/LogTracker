
import customtkinter as ctk


# Importing Libraries
from tkinter import *





def main():
    # Setting up theme of your app
    ctk.set_appearance_mode("dark")

    root = ctk.CTk()
    root.geometry("300x400")
    main_frame = ctk.CTkFrame(root)
    main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    button = ctk.CTkButton(master=main_frame, text="Hello world")
    # button.place(relx=0.5, rely=0.5, anchor=CENTER)

    entry = ctk.CTkEntry(master=main_frame,
                                   placeholder_text="CTkEntry",
                                   width=120,
                                   height=25,
                                   border_width=2,
                                   corner_radius=10)
    entry.place(relx=0.5, rely=0.5, anchor=CENTER)

    root.mainloop()


if __name__ == "__main__":
    main()
