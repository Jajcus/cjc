# Console Jabber Client
# Copyright (C) 2004-2010 Jacek Konieczny
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.


import curses
import curses.textpad
import string
import logging
import unicodedata

from cjc import common
from cjc import cjc_globals

class InputWidget:
    def __init__(self,abortable,required):
        self.abortable=abortable
        self.required=required
        self.parent=None

    def set_parent(self,parent):
        self.parent=parent
        if parent:
            self.win=parent.input_win
            self.h,self.w=self.win.getmaxyx()
            self.win.keypad(1)
            self.win.leaveok(0)
        else:
            self.win=None

    def redraw(self,now=1):
        if not cjc_globals.screen or not self.win:
            return
        self.update(now,1)

    def cursync(self,now=1):
        if not cjc_globals.screen or not self.win:
            return
        cjc_globals.screen.lock.acquire()
        try:
            if not cjc_globals.screen.active:
                return
            if now:
                self.win.refresh()
            else:
                self.win.noutrefresh()
        finally:
            cjc_globals.screen.lock.release()

    def is_printable(self, unichr):
        category = unicodedata.category(unichr)
        if category[0] == "C":
            return False
        else:
            return True

# vi: sts=4 et sw=4
