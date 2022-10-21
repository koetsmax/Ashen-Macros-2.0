from tkinter import *
from tkinter import ttk as tk
import configparser
from submodules.functions.ContinueToNext import _StartCheck
from submodules.BuildExampleMessage import _BuildExampleMessage, _TestCheckMessages

class StaffCheck:

    def __init__(self, root):
        self.root = root
        self.config = configparser.ConfigParser()
        try:
            #parse staffcheck config
            self.config.read('settings.ini')
            self.good_to_check_message = self.config['STAFFCHECK']['goodtocheckmessage']
            self.not_good_to_check_message = self.config['STAFFCHECK']['notgoodtocheckmessage']
        except:
            self.config['STAFFCHECK'] = {'goodtocheckmessage': 'userID Good to check -- GT: xboxGT',
                                        'notgoodtocheckmessage': 'userID **Not** Good to check -- GT: xboxGT -- Reason'}
            with open('settings.ini', 'w') as configfile:
                self.config.write(configfile)
            self.config.read('settings.ini')
            self.good_to_check_message = self.config['STAFFCHECK']['goodtocheckmessage']
            self.not_good_to_check_message = self.config['STAFFCHECK']['notgoodtocheckmessage']
        self.root.title("StaffCheck")
        self.root.option_add('*tearOff', FALSE)

        menubar = Menu(self.root)
        self.root['menu'] = menubar

        self.menu_customize = Menu(menubar)
        self.menu_help = Menu(menubar)

        menubar.add_cascade(menu=self.menu_customize, label='Customize')
        menubar.add_cascade(menu=self.menu_help, label='Help')

        self.menu_customize.add_command(label='Good to check message', command=self.EditGoodToCheck)
        self.menu_customize.add_command(label='Not good to check message', command=self.EditNotGoodToCheck)
        self.menu_help.add_command(label='Help', command=self.ShowHelp)

        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        tk.Label(self.mainframe, text="Discord ID:").grid(column=1, row=1, sticky=E)
        self.userID = StringVar()
        self.userID_entry = tk.Entry(self.mainframe, width=19, textvariable=self.userID)
        self.userID_entry.grid(column=2, row=1, sticky=(W, E))
        
        tk.Label(self.mainframe, text="GamerTag:").grid(column=1, row=2, sticky=E)
        self.xboxGT = StringVar()
        self.xboxGT_entry = tk.Entry(self.mainframe, textvariable=self.xboxGT)
        self.xboxGT_entry.grid(column=2, row=2, sticky=(W, E))
        
        tk.Label(self.mainframe, text="Channel:").grid(column=1, row=3, sticky=E)
        self.channel = StringVar(value="#on-duty-commands")
        self.channel_comboBox = tk.Combobox(self.mainframe, textvariable=self.channel)
        self.channel_comboBox.grid(column=2, row=3, sticky=(W, E))
        self.channel_comboBox['values'] = ('#staff-commands', '#on-duty-commands', '#captains-commands', '#admin-commands')

        tk.Label(self.mainframe, text="Method:").grid(column=1, row=4, sticky=E)
        self.method = StringVar(value="All Commands")
        self.method_comboBox = tk.Combobox(self.mainframe, textvariable=self.method)
        self.method_comboBox.grid(column=2, row=4, sticky=(W, E))
        self.method_comboBox['values'] = ('All Commands', 'Elemental Commands', 'Ashen Commands', 'Invite Tracker', 'SOT Official', 'Check Message')
        
        self.check = BooleanVar(value=False)
        self.checkbutton = tk.Checkbutton(self.mainframe, variable=self.check, text="Check ID/GT in on-duty-chat", onvalue=1, offvalue=0)
        self.checkbutton.grid(column=2, row=5, sticky=(W, E))
        
        self.progressbar = tk.Progressbar(self.mainframe, orient=HORIZONTAL, length=200, mode='determinate')
        self.progressbar.grid(column=1, columnspan=2, row=9, sticky=(W, E))
        
        self.log = Text(self.mainframe, state='disabled', width=20, height=3, wrap='word')
        self.log.grid(column=1, columnspan=2, row=10, sticky=(E, W))
        self.log.tag_configure('highlightline', font=('TkTextFont:', 10))

        self.functionbutton = tk.Button(self.mainframe, text="Cool Button")
        self.functionbutton.grid(column=1, row=5, sticky=(W, E))
        self.functionbutton.state(['disabled'])

        self.killbutton = tk.Button(self.mainframe, text="Kill Program", command=self.kill)
        self.killbutton.grid(column=1, row=6, sticky=(W, E))

        self.startbutton = tk.Button(self.mainframe, text="Start check!", command=lambda: _StartCheck(self))
        self.startbutton.grid(columnspan=2, column=2, row=6, sticky=(E, W))

        _TestCheckMessages(self)

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.userID_entry.focus()

    def EditGoodToCheck(self):
        
        self.goodwindow = Toplevel()

        explanation_label = tk.Label(self.goodwindow, text="Discord ID = userID\nGamertag = xboxGT")
        explanation_label.grid(rowspan=2, column=1, row=1, sticky=(W))

        good_to_check_label = tk.Label(self.goodwindow, text="Good to check message:")
        good_to_check_label.grid(column=1, row=3, sticky=W)

        self.good_to_check_message = StringVar(value=self.config['STAFFCHECK']['goodtocheckmessage'])
        self.good_to_check_entry = tk.Entry(self.goodwindow, width=60, textvariable=self.good_to_check_message)
        self.good_to_check_entry.grid(column=1, row=4, sticky=(E, W))

        _BuildExampleMessage(self, 1)
        _TestCheckMessages(self)

        self.save_button = tk.Button(self.goodwindow, text="Save Changes!", command=self.SaveChangesGood)
        self.save_button.grid(column=1, row=6, sticky=W)

        self.reset_button = tk.Button(self.goodwindow, text="Reset To Default!", command=self.ResetToDefaultGood)
        self.reset_button.grid(column=1, row=6, sticky=E)

        for child in self.goodwindow.winfo_children():
            child.grid_configure(padx=5, pady=5)
        
        self.root.eval(f'tk::PlaceWindow {str(self.goodwindow)} center')

    def SaveChangesGood(self):
        with open('settings.ini', 'w') as configfile:
            self.example_label.destroy()
            self.config['STAFFCHECK']['goodtocheckmessage'] = self.good_to_check_message.get()
            self.config.write(configfile)
            _BuildExampleMessage(self, 1)
            _TestCheckMessages(self)

    def ResetToDefaultGood(self):
        with open('settings.ini', 'w') as configfile:
            self.example_label.destroy()
            self.config['STAFFCHECK']['goodtocheckmessage'] = "userID Good to check -- GT: xboxGT"
            self.config.write(configfile)
            self.good_to_check_message.set("userID Good to check -- GT: xboxGT")
            _BuildExampleMessage(self, 1)
            _TestCheckMessages(self)

    def EditNotGoodToCheck(self):
        self.notgoodwindow = Toplevel()

        explanation_label = tk.Label(self.notgoodwindow, text="Discord ID = userID\nGamertag = xboxGT\nreason = Reason")
        explanation_label.grid(rowspan=3, column=1, row=1, sticky=(W))

        not_good_to_check_label = tk.Label(self.notgoodwindow, text="Not Good to check message:")
        not_good_to_check_label.grid(column=1, row=4, sticky=W)
        
        self.not_good_to_check_message = StringVar(value=self.config['STAFFCHECK']['notgoodtocheckmessage'])
        self.not_good_to_check_entry = tk.Entry(self.notgoodwindow, width=60, textvariable=self.not_good_to_check_message)
        self.not_good_to_check_entry.grid(column=1, row=5, sticky=(E, W))

        _BuildExampleMessage(self, 0)
        _TestCheckMessages(self)

        self.save_button = tk.Button(self.notgoodwindow, text="Save Changes!", command=self.SaveChangesNotGood)
        self.save_button.grid(column=1, row=7, sticky=W)

        self.reset_button = tk.Button(self.notgoodwindow, text="Reset To Default!", command=self.ResetToDefaultNotGood)
        self.reset_button.grid(column=1, row=7, sticky=E)

        for child in self.notgoodwindow.winfo_children():
            child.grid_configure(padx=5, pady=5)
        
        self.root.eval(f'tk::PlaceWindow {str(self.notgoodwindow)} center')

    def SaveChangesNotGood(self):
        with open('settings.ini', 'w') as configfile:
            self.example_label1.destroy()
            self.config['STAFFCHECK']['notgoodtocheckmessage'] = self.not_good_to_check_message.get()
            self.config.write(configfile)
            _BuildExampleMessage(self, 0)
            _TestCheckMessages(self)

    def ResetToDefaultNotGood(self):
        with open('settings.ini', 'w') as configfile:
            self.example_label1.destroy()
            self.config['STAFFCHECK']['notgoodtocheckmessage'] = "userID **Not** Good to check -- GT: xboxGT -- Reason"
            self.config.write(configfile)
            self.not_good_to_check_message.set("userID **Not** Good to check -- GT: xboxGT -- Reason")
            _BuildExampleMessage(self, 0)
            _TestCheckMessages(self)

    def kill(self):
        root.destroy()

    def ShowHelp(self):
        print("test")
        pass

root = Tk()
root.eval('tk::PlaceWindow . center')
StaffCheck(root)
root.mainloop()