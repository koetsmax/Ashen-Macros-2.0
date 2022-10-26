# pylint: disable=E0401, E0402
import modules.submodules.start_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.execute_command import execute_command
from .functions.update_status import UpdateStatus


def elemental_commands(self):
    self.currentstate = "ElementalCommands"
    UpdateStatus(self.root, self.log, self.progressbar, "", 43.75)
    switch_channel(self, self.channel.get())
    clear_typing_bar(self)
    loghistory = ["/loghistory report ", self.user_id.get()]
    execute_command(self, loghistory[0], loghistory[1:])
    UpdateStatus(self.root, self.log, self.progressbar, "", 50)

    self.notespage = 2
    self.function_button.config(text="Add GT to Notes", command=lambda: add_note(self))
    self.kill_button.config(
        text=f"Check notes page {self.notespage}",
        command=lambda: check_notes_page(self),
    )
    self.start_button.config(
        text="Continue",
        command=lambda: modules.submodules.start_check.continue_to_next(self),
    )
    self.start_button.state(["!disabled"])
    self.function_button.state(["!disabled"])
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        "Press ONE of the buttons to do what you want to do",
        "",
    )


def add_note(self):
    """
    Adds note to specified userID and GT
    """
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    noteadd = ["/notes new", self.user_id.get(), f"GT: {self.xbox_gt.get()}"]
    clear_typing_bar(self)
    execute_command(self, noteadd[0], noteadd[1:])
    UpdateStatus(self.root, self.log, self.progressbar, "Added GT to notes!", "")
    self.function_button.state(["disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])


def check_notes_page(self):
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    notescheck = ["/notes list", self.user_id.get(), f"page_number: {self.notespage}"]
    clear_typing_bar(self)
    execute_command(self, notescheck[0], notescheck[1:])
    UpdateStatus(
        self.root,
        self.log,
        self.progressbar,
        f"Checked notes page {self.notespage}!",
        "",
    )
    self.notespage += 1
    self.kill_button.config(text=f"Check notes page {self.notespage}")
    self.function_button.state(["!disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])
