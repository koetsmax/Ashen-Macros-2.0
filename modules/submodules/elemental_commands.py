"""
This module executes all elemental commands.
"""
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.execute_command import execute_command


def elemental_commands(self, *args):
    """
    This function executes all elemental commands.
    """
    self.currentstate = "ElementalCommands"
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    loghistory = ["/loghistory report ", self.user_id.get()]
    execute_command(self, loghistory[0], loghistory[1:])
    self.stop_button.state(["!disabled"])
    self.function_button.state(["!disabled"])

    self.notespage = 2
    if not args:
        self.function_button.config(text="Add GT to Notes", command=lambda: add_note(self))
        self.kill_button.config(text=f"Check notes page {self.notespage}", command=lambda: check_notes_page(self))
        self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.continue_to_next(self))
        self.start_button.state(["!disabled"])
    else:
        self.function_button.config(text="Tell to link xbox", command=lambda: tell_to_link_xbox(self))
        self.kill_button.config(text="Tell to verify + link xbox", command=lambda: tell_to_verify_link_xbox(self))
        self.start_button.state(["disabled"])


def add_note(self):
    """
    Adds note to specified userID and GT if needed.
    """
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    noteadd = ["/notes new", self.user_id.get(), f"GT: {self.xbox_gt}"]
    clear_typing_bar()
    execute_command(self, noteadd[0], noteadd[1:])
    self.function_button.state(["disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])


def check_notes_page(self):
    """
    Checks additional pages of notes if needed for the specified userID.
    """
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    notescheck = ["/notes list", self.user_id.get(), f"page_number: {self.notespage}"]
    clear_typing_bar()
    execute_command(self, notescheck[0], notescheck[1:])
    self.notespage += 1
    self.kill_button.config(text=f"Check notes page {self.notespage}")
    self.function_button.state(["!disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])


def tell_to_link_xbox(self):
    """
    Tells the user to link their xbox account.
    """
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    verify = ["/verify", self.user_id.get(), "verify_type: link_xbox"]
    clear_typing_bar()
    execute_command(self, verify[0], verify[1:])
    self.function_button.state(["!disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])


def tell_to_verify_link_xbox(self):
    """
    Tells the user to verify and link their xbox account.
    """
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    verify = ["/verify", self.user_id.get(), "verify_type: both"]
    clear_typing_bar()
    execute_command(self, verify[0], verify[1:])
    self.function_button.state(["!disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])
