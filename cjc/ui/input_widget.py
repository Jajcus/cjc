
import curses
import curses.textpad
import string

from cjc import common

class InputWidget:
    def __init__(self,abortable,required):
        self.abortable=abortable
        self.required=required
        self.parent=None
        self.screen=None

    def set_parent(self,parent):
        self.parent=parent
        if parent:
            self.win=parent.input_win
            self.theme_manager=parent.theme_manager
            self.h,self.w=self.win.getmaxyx()
            self.screen=self.parent.screen
            self.printable=string.digits+string.letters+string.punctuation+" "
            self.win.keypad(1)
            self.win.leaveok(0)
        else:
            self.win=None

    def redraw(self,now=1):
        if not self.screen or not self.win:
            return
        self.update(now,1)

    def cursync(self,now=1):
        if not self.screen or not self.win:
            return
        self.screen.lock.acquire()
        try:
            if now:
                self.win.refresh()
            else:
                self.win.noutrefresh()
        finally:
            self.screen.lock.release()
# vi: sts=4 et sw=4
