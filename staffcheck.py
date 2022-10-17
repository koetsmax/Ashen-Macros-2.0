from email.policy import default
from tkinter import *
from tkinter import ttk

class FeetToMeters:

    def __init__(self, root):

        root.title("Staffcheck")
        root.option_add('*tearOff', FALSE)

        menubar = Menu(root)
        root['menu'] = menubar

        menu_edit = Menu(menubar)
        menu_help = Menu(menubar)

        menubar.add_cascade(menu=menu_edit, label='Edit')
        menubar.add_cascade(menu=menu_help, label='Help')

        menu_edit.add_command(label='Good to check message', command=self.newFile)
        menu_edit.add_command(label='Not good to check message', command=self.newFile)
        menu_help.add_command(label='Help', command=self.newFile)

        mainframe = ttk.Frame(root, padding="3 3 12 12")
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        ttk.Label(mainframe, text="Discord ID:").grid(column=1, row=1, sticky=E)
        self.userID = StringVar()
        userID_entry = ttk.Entry(mainframe, width=19, textvariable=self.userID)
        userID_entry.grid(column=2, row=1, sticky=(W, E))
        
        ttk.Label(mainframe, text="Xbox GamerTag:").grid(column=1, row=2, sticky=E)
        self.xboxGT = StringVar()
        xboxGT_entry = ttk.Entry(mainframe, textvariable=self.xboxGT)
        xboxGT_entry.grid(column=2, row=2, sticky=(W, E))
        
        ttk.Label(mainframe, text="Channel:").grid(column=1, row=3, sticky=E)
        self.channel = StringVar(value="#on-duty-commands")
        channel_comboBox = ttk.Combobox(mainframe, textvariable=self.channel)
        channel_comboBox.grid(column=2, row=3, sticky=(W, E))
        channel_comboBox['values'] = ('#staff-commands', '#on-duty-commands', '#captains-commands', '#admin-commands')

        ttk.Label(mainframe, text="Method:").grid(column=1, row=4, sticky=E)
        self.method = StringVar(value="All commands")
        method_comboBox = ttk.Combobox(mainframe, textvariable=self.method)
        method_comboBox.grid(column=2, row=4, sticky=(W, E))
        method_comboBox['values'] = ('All Commands', 'Elemental Commands', 'Ashen Commands', 'Invite Tracker', 'SOT Official', 'Check Message')
        
        # ttk.Label(mainframe, text="Check ID in onduty chat:").grid(column=1, row=5, sticky=E)
        self.check = BooleanVar(value=False)
        check = ttk.Checkbutton(mainframe, variable=self.check, text="Check ID/GT in onduty chat", onvalue=1, offvalue=0)
        check.grid(column=2, row=5, sticky=(W, E))

        ttk.Button(mainframe, text="Start check!", command=self.calculate).grid(column=3, row=5, sticky=(W, E))


        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        userID_entry.focus()
        root.bind("<Return>", self.calculate)
        
    def calculate(self, *args):
        try:
            value = float(self.userID.get())
            self.xboxGT.set(int(0.3048 * value * 10000.0 + 0.5)/10000.0)
        except ValueError:
            self.xboxGT.set(0.0)
            pass
    
    def newFile(self):
        print("test")
        pass

    def openFile(self):
        pass

    def closeFile(self):
        pass

root = Tk()
root.eval('tk::PlaceWindow . center')
FeetToMeters(root)
root.mainloop()