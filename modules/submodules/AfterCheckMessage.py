import keyboard
import time
import modules.submodules.functions.ContinueToNext
from modules.submodules.functions.ClearTypingBar import _ClearTypingBar
from modules.submodules.functions.SwitchChannel import _SwitchChannel
from modules.submodules.functions.ExecuteCommand import _ExecuteCommand

def _AfterCheckMessage(self):
    self.reason_entry.state(['disabled'])
    self.functionbutton.config(text="Neither of these apply", command=lambda:Continue(self))
    self.killbutton.config(text="Needs to unprivate Xbox", command=lambda:UnprivateXbox(self))
    self.startbutton.config(text="Needs to join the AWR", command=lambda:JoinAWR(self))
    self.killbutton.state(['!disabled'])

def UnprivateXbox(self):
    _SwitchChannel(self, self.userID.get())
    _ClearTypingBar(self)
    keyboard.write("Hey! In order for you to play in our fleets, we require your xbox profile to be **public**. To do so, please follow the instructions below.")
    keyboard.press_and_release('shift+enter')
    keyboard.press_and_release('shift+enter')
    keyboard.write("• Go to xbox.com > xbox profile > Privacy Settings")
    keyboard.press_and_release('shift+enter')
    keyboard.write("• Others can:")
    keyboard.press_and_release('shift+enter')
    keyboard.write("- Others can see your friends list")
    keyboard.press_and_release('shift+enter')
    keyboard.write("- Others can see your game and app history")
    keyboard.press_and_release('shift+enter')
    keyboard.write("- Others can see your activity feed")
    keyboard.press_and_release('shift+enter')
    keyboard.write("- Others can see your game and app history")
    keyboard.press_and_release('shift+enter')
    keyboard.press_and_release('shift+enter')
    keyboard.write("Allow **everybody** to see the above settings and click **Submit**.")
    keyboard.press_and_release('enter')
    time.sleep(2.2)
    _SwitchChannel(self, "#on-duty-chat")
    _ClearTypingBar(self)
    keyboard.write(f"<@{self.userID.get()}> has been sent a message to unprivate their xbox - Good to remove <t:{round(time.time() + 600)}:R>")
    keyboard.press_and_release('enter')
    Continue(self)

def JoinAWR(self):
    _ClearTypingBar(self)
    _SwitchChannel(self, "#on-duty-chat")
    joinawr = ['/joinawr ', f'{self.userID.get()}']
    _ExecuteCommand(self, joinawr[0], joinawr[1:])
    keyboard.write(f"<@{self.userID.get()}> has been requested to join the <#702904587027480607> - Good to remove <t:{round(time.time() + 600)}:R>")
    keyboard.press_and_release('enter')
    Continue(self)

def Continue(self):
    modules.submodules.functions.ContinueToNext._ContinueToNext(self)