# Console Jabber Client
# Copyright (C) 2004  Jacek Konieczny
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

from cjc.ui.widget import Widget
from cjc import common
from cjc.ui import text_input
from cjc.ui import bool_input
from cjc.ui import choice_input
from cjc.ui import list_input
from cjc.ui import complete

class InputError(StandardError):
    pass

class Input(Widget):
    def __init__(self,theme_manager):
        self.__logger=logging.getLogger("cjc.ui.Input")
        Widget.__init__(self)
        self.prompt_win=None
        self.input_win=None
        self.prompt=None
        self.theme_manager=theme_manager
        self.command_line=None
        self.input_widget=None
        self.question_handler=None
        self.question_abort_handler=None

    def set_parent(self,parent):
        Widget.set_parent(self,parent)
        self.command_line=text_input.TextInput(self,0,u"",100)
        self.input_widget=self.command_line
        self.make_windows()
        self.screen.set_input_handler(self)

    def complete(self,s,pos,again):
        if self.input_widget!=self.command_line:
            self.screen.beep()
            return 0
        head,tails=complete.complete(s[:pos])
        self.__logger.debug("complete() returned: "+`(head,tails)`)
        if len(tails)>1 and self.current_buffer:
            if again:
                def callback(response):
                    return self.complete_answer(response, s, pos, head, tails)
                def abort_callback():
                    return
                self.current_buffer.ask_question(head,"list-single",tails[0],
                    self.complete_answer,self.complete_abort,tails,1);
                return 0
            else:
                self.screen.beep()
                return 1
        if len(tails)!=1:
            self.screen.beep()
            return 0
        self.input_widget.set_content(head+tails[0]+s[pos:])
        self.input_widget.set_pos(len(head)+len(tails[0]))
        self.input_widget.redraw()
        return 0

    def complete_answer(self, answer, s, pos, head, tails):
        self.input_widget.set_content(head+answer+s[pos:])
        self.input_widget.set_pos(len(head)+len(answer))
        self.input_widget.redraw()

    def input_handler(self,answer):
        if self.input_widget==self.command_line:
            self.screen.user_input(answer)
            return
        handler=self.question_handler
        self.unask_question()
        if handler:
            handler(answer)
            handler=None

    def abort_handler(self):
        if self.input_widget==self.command_line:
            return
        handler=self.question_abort_handler
        self.unask_question()
        if handler:
            handler()
            handler=None

    def make_windows(self):
        self.prompt_win=None
        self.input_win=None
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            if self.prompt:
                l=len(self.prompt)
                if l<self.w/2:
                    prompt=self.prompt
                else:
                    prompt=self.prompt[:self.w/4-3]+"(...)"+self.prompt[-self.w/4+4:]
                self.__logger.debug("prompt="+`prompt`)
                l=len(prompt)
                self.prompt_win=curses.newwin(self.h,l+1,self.y,self.x)
                self.prompt_win.addstr(prompt)
                self.prompt_win.leaveok(1)
                self.input_win=curses.newwin(self.h,self.w-l,self.y,self.x+l)
            else:
                self.prompt_win=None
                self.input_win=curses.newwin(self.h,self.w,self.y,self.x)
            self.input_win.timeout(100)
            if self.input_widget:
                self.input_widget.set_parent(self)
        finally:
            self.screen.lock.release()

    def unask_question(self):
        if self.current_buffer:
            self.current_buffer.unask_question()

    def current_buffer_changed(self,buffer):
        if self.input_widget:
            self.input_widget.set_parent(None)
        if buffer and buffer.question:
            self.question_handler=buffer.question_handler
            self.question_abort_handler=buffer.question_abort_handler
            self.prompt=buffer.question
            self.input_widget=buffer.input_widget
        else:
            self.question_handler=None
            self.question_abort_handler=None
            self.prompt=None
            self.input_widget=self.command_line
            self.make_windows()
        self.current_buffer=buffer
        self.make_windows()
        self.update(1,1)

    def get_height(self):
        return 1

    def update(self,now=1,redraw=0):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            if self.prompt_win:
                self.prompt_win.noutrefresh()
            if self.input_widget:
                self.input_widget.update(0,redraw)
            if now:
                curses.doupdate()
        finally:
            self.screen.lock.release()

    def cursync(self):
        if self.input_widget:
            return self.input_widget.cursync()

    def getch(self):
        self.screen.lock.acquire()
        try:
            if self.screen.active and self.input_widget:
                return self.input_widget.win.getch()
        finally:
            self.screen.lock.release()
        return -1
# vi: sts=4 et sw=4
