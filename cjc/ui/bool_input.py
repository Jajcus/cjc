
import curses
import curses.textpad
import string
import keytable

from cjc import common
from input_widget import InputWidget

class BooleanInput(InputWidget):
    def __init__(self,abortable,required,default=None):
        InputWidget.__init__(self,abortable,required)
        self.content=u""
        if default==1:
            self.prompt="[Y/n]: "
        elif default==0:
            self.prompt="[y/N]: "
        else:
            self.prompt="[y/n]: "
            default=None
        self.default=default

    def set_parent(self,parent):
        InputWidget.set_parent(self,parent)
        if parent:
            keytable.activate("bool-input",self,input_window=self.win)
        else:
            keytable.deactivate("bool-input",self)

    def key_abort(self):
        if self.abortable:
            self.parent.abort_handler()
        else:
            self.screen.lock.acquire()
            try:
                curses.beep()
            finally:
                self.screen.lock.release()

    def key_enter(self):
        self.screen.lock.acquire()
        try:
            if self.default is None and self.required:
                curses.beep()
                return
            if self.default:
                self.answer_yes()
            else:
                self.answer_no()
        finally:
            self.screen.lock.release()

    def answer_yes(self):
        self.screen.lock.acquire()
        try:
            self.content=u"y"
            self.win.addstr(self.content)
            self.update()
            self.parent.input_handler(1)
        finally:
            self.screen.lock.release()

    def answer_no(self):
        self.screen.lock.acquire()
        try:
            self.content=u"n"
            self.win.addstr(self.content)
            self.update()
            self.parent.input_handler(0)
        finally:
            self.screen.lock.release()

    def update(self,now=1,refresh=0):
        self.screen.lock.acquire()
        try:
            if refresh:
                self.win.erase()
                s=self.prompt.encode(self.screen.encoding,"replace")
                self.win.addstr(0,0,s)
                s=self.content.encode(self.screen.encoding,"replace")
                self.win.addstr(s)
            else:
                self.win.move(0,len(self.prompt)+len(self.content))
            if now:
                self.win.refresh()
            else:
                self.win.noutrefresh()
        finally:
            self.screen.lock.release()

from keytable import KeyFunction
ktb=keytable.KeyTable("bool-input",50,(
        KeyFunction("accept-input",
                BooleanInput.key_enter,
                "Accept input",
                ("ENTER","\n","\r")),
        KeyFunction("abort-input",
                BooleanInput.key_abort,
                "Abort input",
                "ESCAPE"),
        KeyFunction("answer-yes",
                BooleanInput.answer_yes,
                "Answer 'yes'",
                "y"),
        KeyFunction("answer-no",
                BooleanInput.answer_no,
                "Answer 'no'",
                "n"),
        ))

keytable.install(ktb)
# vi: sts=4 et sw=4
