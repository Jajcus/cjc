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

from cjc import common
from cjc.ui.input_widget import InputWidget
from cjc.ui import keytable
from cjc import cjc_globals

class BooleanInput(InputWidget):
    def __init__(self,abortable,required,default=None):
        InputWidget.__init__(self,abortable,required)
        self.content=u""
        if default == True:
            self.prompt="[Y/n]: "
        elif default == False:
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
            cjc_globals.screen.beep()

    def key_enter(self):
        cjc_globals.screen.lock.acquire()
        try:
            if self.default is None and self.required:
                cjc_globals.screen.beep()
                return
            if self.default:
                self.answer_yes()
            else:
                self.answer_no()
        finally:
            cjc_globals.screen.lock.release()

    def answer_yes(self):
        cjc_globals.screen.lock.acquire()
        try:
            if not cjc_globals.screen.active:
                return
            self.content=u"y"
            self.win.addstr(self.content)
            self.update()
            self.parent.input_handler(True)
        finally:
            cjc_globals.screen.lock.release()

    def answer_no(self):
        cjc_globals.screen.lock.acquire()
        try:
            if not cjc_globals.screen.active:
                return
            self.content=u"n"
            self.win.addstr(self.content)
            self.update()
            self.parent.input_handler(False)
        finally:
            cjc_globals.screen.lock.release()

    def update(self, now = True, refresh = False):
        cjc_globals.screen.lock.acquire()
        try:
            if not cjc_globals.screen.active:
                return
            if refresh:
                self.win.erase()
                s=self.prompt.encode(cjc_globals.screen.encoding,"replace")
                self.win.addstr(0,0,s)
                s=self.content.encode(cjc_globals.screen.encoding,"replace")
                self.win.addstr(s)
            else:
                self.win.move(0,len(self.prompt)+len(self.content))
            if now:
                self.win.refresh()
            else:
                self.win.noutrefresh()
        finally:
            cjc_globals.screen.lock.release()

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
