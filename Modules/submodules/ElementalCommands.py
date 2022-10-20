from submodules.functions.ClearTypingBar import _ClearTypingBar
from submodules.functions.SwitchChannel import _SwitchChannel
from submodules.functions.ExecuteCommand import _ExecuteCommand
from submodules.functions.UpdateStatus import _UpdateStatus
import submodules.functions.ContinueToNext

def _ElementalCommands(self):
    self.currentstate = "ElementalCommands"
    _UpdateStatus(self, "", 20)
    _SwitchChannel(self, self.channel.get())
    _ClearTypingBar(self)
    loghistory = ['/loghistory report ', self.userID.get()]
    print(loghistory[0], loghistory[1:])
    _ExecuteCommand(self, loghistory[0], loghistory[1:])
    _UpdateStatus(self, "", 25)

    self.notespage = 2
    self.functionbutton.config(text="Add GT to Notes", command=lambda:AddNote(self))
    self.killbutton.config(text=f"Check notes page {self.notespage}", command=lambda:CheckNotesPage(self))
    self.startbutton.config(text="Continue", command=lambda: submodules.functions.ContinueToNext._ContinueToNext(self))
    self.startbutton.state(['!disabled'])
    self.functionbutton.state(['!disabled'])
    _UpdateStatus(self, "Press ONE of the buttons to do what you want to do", "")

def AddNote(self):
        self.functionbutton.state(['disabled'])
        self.killbutton.state(['disabled'])
        self.startbutton.state(['disabled'])
        noteadd = ['/notes new', self.userID.get(), f'GT: {self.xboxGT.get()}']
        _ClearTypingBar(self)
        _ExecuteCommand(self, noteadd[0], noteadd[1:])
        _UpdateStatus(self, "Added GT to notes!", "")
        self.functionbutton.state(['disabled'])
        self.killbutton.state(['!disabled'])
        self.startbutton.state(['!disabled'])

def CheckNotesPage(self):
    self.functionbutton.state(['disabled'])
    self.killbutton.state(['disabled'])
    self.startbutton.state(['disabled'])
    notescheck = ['/notes list', self.userID.get(), f'page_number: {self.notespage}']
    _ClearTypingBar(self)
    _ExecuteCommand(self, notescheck[0], notescheck[1:])
    _UpdateStatus(self, f"Checked notes page {self.notespage}!", "")
    self.notespage += 1
    self.killbutton.config(text=f"Check notes page {self.notespage}")
    self.functionbutton.state(['!disabled'])
    self.killbutton.state(['!disabled'])
    self.startbutton.state(['!disabled'])