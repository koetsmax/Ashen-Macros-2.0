from submodules.functions.ClearTypingBar import _ClearTypingBar
from submodules.functions.SwitchChannel import _SwitchChannel
from submodules.functions.ExecuteCommand import _ExecuteCommand
from submodules.functions.UpdateStatus import _UpdateStatus

def _AshenCommands(self):
    self.currentstate = "AshenCommands"
    _UpdateStatus(self, "", 30)
    _SwitchChannel(self, self.channel.get())
    _ClearTypingBar(self)
    search = ['/search ', f'member: {self.userID.get()}', f'gamertag: {self.xboxGT.get()}']
    print(search[0], search[1:])
    _ExecuteCommand(self, search[0], search[1:])
    _UpdateStatus(self, "", 35)
    self.startbutton.state(['!disabled'])
    _UpdateStatus(self, "Press Continue to well... continue... Duhh", "")
    self.startbutton.config(text="Continue", command=self.continuetonext)