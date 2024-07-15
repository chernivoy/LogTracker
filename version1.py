
import customtkinter as ctk


# Importing Libraries
from tkinter import *





def main():
    # Setting up theme of your app
    ctk.set_appearance_mode("dark")

    root = ctk.CTk()
    root.geometry("300x400")
    button = ctk.CTkButton(master=root, text="Hello world")
    button.place(relx=0.5, rely=0.5, anchor=CENTER)
    root.mainloop()


if __name__ == "__main__":
    main()
