import tkinter as tk


def create_label_frame():
    labelframe = tk.LabelFrame(root, text="loghistory")
    labelframe.pack(padx=20, pady=20, expand=True, fill="both")

    label = tk.Label(labelframe, text="Widgets Inside the 'Window'")
    label.pack(padx=10, pady=10)

    button = tk.Button(labelframe, text="Click Me", command=lambda: print("Hello World!"))
    button.pack(padx=10, pady=10)


root = tk.Tk()
root.title("Main Window")

create_label_frame()

root.mainloop()
