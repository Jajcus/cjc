# Console Jabber Client
# Copyright (C) 2004-2009  Jacek Konieczny
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

class TextInput(InputWidget):
    def __init__(self,abortable,required,default=u"",history_len=0, private=False):
        InputWidget.__init__(self,abortable,required)
        self.capture_rest=0
        self.content=default
        self.pos=0
        self.offset=0
        self.history_len=history_len
        self.history=[]
        self.history_pos=0
        self.saved_content=None
        self.completing=0
        self.private = private

    def set_parent(self,parent):
        InputWidget.set_parent(self,parent)
        if parent:
            keytable.activate("text-input",self,self.keypressed,self.win)
        else:
            keytable.deactivate("text-input",self)

    def set_content(self,s):
        self.content=s

    def set_pos(self,pos):
        self.pos=pos

    def keypressed(self,c,escape):
        cjc_globals.screen.lock.acquire()
        try:
            return self._keypressed(c,escape)
        finally:
            cjc_globals.screen.lock.release()

    def _keypressed(self,c,meta):
        if c == '\e':
            if self.abortable:
                self.parent.abort_handler()
                return
            else:
                cjc_globals.screen._beep()
                return
        elif type(c) not in (chr, unicode) or meta:
            cjc_globals.screen._beep()
            return
        if self.is_printable(c):
            self.key_char(c)
        else:
            cjc_globals.screen._beep()

    def left_scroll_mark(self):
        if self.offset>0:
            cjc_globals.screen.lock.acquire()
            try:
                if cjc_globals.screen.active:
                    self.win.addch(0,0,curses.ACS_LARROW,
                            cjc_globals.theme_manager.attrs["scroll_mark"])
            finally:
                cjc_globals.screen.lock.release()

    def right_scroll_mark(self):
        if len(self.content)-self.offset>=self.w:
            cjc_globals.screen.lock.acquire()
            try:
                if cjc_globals.screen.active:
                    self.win.insch(0,self.w-1,curses.ACS_RARROW,
                            cjc_globals.theme_manager.attrs["scroll_mark"])
            finally:
                cjc_globals.screen.lock.release()

    def scroll_right(self):
        while self.pos>self.offset+self.w-2:
            self.offset+=self.w/4
        if self.offset>len(self.content)-2:
            self.offset=len(self.content)-2
        self.redraw()

    def scroll_left(self):
        while self.pos<self.offset+1:
            self.offset-=self.w/4
        if self.offset<0:
            self.offset=0
        self.redraw()

    def after_del(self):
        if not cjc_globals.screen.active:
            return
        if len(self.content)-self.offset<self.w-1:
            self.win.move(0,self.pos-self.offset)
            return
        if self.private:
            s = "*" 
        else:
            s = self.content[self.offset+self.w-2]
        self.win.addstr(0,self.w-2,s.encode(cjc_globals.screen.encoding,"replace"))
        if len(self.content)-self.offset==self.w-1:
            self.win.clrtoeol()
        else:
            self.right_scroll_mark()
        self.win.move(0,self.pos-self.offset)

    def key_enter(self):
        self.completing=0
        if self.required and not self.content:
            cjc_globals.screen.beep()
            return
        if self.history_len:
            if self.history_pos:
                if self.content==self.history[-self.history_pos]:
                    del self.history[-self.history_pos]
                self.history_pos=0
            self.history.append(self.content)
            self.history=self.history[-self.history_len:]
        ans=self.content
        self.content=u""
        self.saved_content=None
        self.pos=0
        self.offset=0
        cjc_globals.screen.lock.acquire()
        try:
            if not cjc_globals.screen.active:
                return
            self.win.move(0,0)
            self.win.clrtoeol()
            self.win.refresh()
        finally:
            cjc_globals.screen.lock.release()
        self.parent.input_handler(ans)

    def key_kill(self):
        self.completing=0
        if not self.content:
            cjc_globals.screen.beep()
            return
        self.content=u""
        self.saved_content=None
        self.pos=0
        self.offset=0
        cjc_globals.screen.lock.acquire()
        try:
            if not cjc_globals.screen.active:
                return
            self.win.move(0,0)
            self.win.clrtoeol()
            self.win.refresh()
        finally:
            cjc_globals.screen.lock.release()

    def key_home(self):
        self.completing=0
        if self.pos<=0:
            cjc_globals.screen.beep()
            return
        self.pos=0
        if self.offset>0:
            self.scroll_left()
        else:
            cjc_globals.screen.lock.acquire()
            try:
                if not cjc_globals.screen.active:
                    return
                self.win.move(0,self.pos-self.offset)
                self.win.refresh()
            finally:
                cjc_globals.screen.lock.release()

    def key_end(self):
        self.completing=0
        if self.pos>=len(self.content):
            cjc_globals.screen.beep()
            return
        self.pos=len(self.content)
        if self.pos>self.offset+self.w-2:
            self.scroll_right()
        else:
            cjc_globals.screen.lock.acquire()
            try:
                if not cjc_globals.screen.active:
                    return
                self.win.move(0,self.pos-self.offset)
                self.win.refresh()
            finally:
                cjc_globals.screen.lock.release()

    def key_left(self):
        self.completing=0
        if self.pos<=0:
            cjc_globals.screen.beep()
            return
        self.pos-=1
        if self.pos and self.pos<self.offset+1:
            self.scroll_left()
        else:
            cjc_globals.screen.lock.acquire()
            try:
                if not cjc_globals.screen.active:
                    return
                self.win.move(0,self.pos-self.offset)
                self.win.refresh()
            finally:
                cjc_globals.screen.lock.release()

    def key_right(self):
        self.completing=0
        if self.pos>=len(self.content):
            cjc_globals.screen.beep()
            return
        self.pos+=1
        if self.pos>self.offset+self.w-2:
            self.scroll_right()
        else:
            cjc_globals.screen.lock.acquire()
            try:
                if not cjc_globals.screen.active:
                    return
                self.win.move(0,self.pos-self.offset)
                self.win.refresh()
            finally:
                cjc_globals.screen.lock.release()

    def key_bs(self):
        self.completing=0
        if self.pos<=0:
            cjc_globals.screen.beep()
            return
        self.content=self.content[:self.pos-1]+self.content[self.pos:]
        self.pos-=1
        if self.pos and self.pos<self.offset+1:
            self.scroll_left()
        else:
            cjc_globals.screen.lock.acquire()
            try:
                if not cjc_globals.screen.active:
                    return
                self.win.move(0,self.pos-self.offset)
                self.win.delch()
                self.after_del()
                self.win.refresh()
            finally:
                cjc_globals.screen.lock.release()

    def key_del(self):
        self.completing=0
        if self.pos>=len(self.content):
            cjc_globals.screen.beep()
            return
        self.content=self.content[:self.pos]+self.content[self.pos+1:]
        cjc_globals.screen.lock.acquire()
        try:
            if not cjc_globals.screen.active:
                return
            self.win.delch()
            self.after_del()
            self.win.refresh()
        finally:
            cjc_globals.screen.lock.release()

    def key_uclean(self):
        self.completing=0
        if self.pos==0:
            cjc_globals.screen.beep()
            return
        self.content=self.content[self.pos:].rstrip()
        self.pos=0
        self.redraw()

    def key_wrubout(self):
        self.completing=0
        if self.pos==0:
            cjc_globals.screen.beep()
            return
        s=self.content[:self.pos].rstrip()
        if self.pos>len(s):
            self.content=s+self.content[self.pos:]
            self.pos=len(s)

        p=self.content.rfind(" ",0,self.pos)
        if p<=0:
            self.content=self.content[self.pos:]
        else:
            self.content=self.content[:p+1]+self.content[self.pos:]
            self.pos=p+1
        self.redraw()

    def key_complete(self):
        self.completing=self.parent.complete(self.content,self.pos,self.completing)

    def key_char(self, c):
        self.completing=0
        cjc_globals.screen.lock.acquire()
        ch = c.encode(cjc_globals.screen.encoding, "replace")
        try:
            if self.pos==len(self.content):
                self.content+=c
                self.pos+=1
                if self.pos>self.offset+self.w-2:
                    self.scroll_right()
                else:
                    if cjc_globals.screen.active:
                        if self.private:
                            self.win.addstr('*')
                        else:
                            self.win.addstr(ch)
            else:
                self.content=self.content[:self.pos]+c+self.content[self.pos:]
                self.pos+=1
                if self.pos>self.offset+self.w-2:
                    self.scroll_right()
                else:
                    if cjc_globals.screen.active:
                        if self.private:
                            self.win.insstr('*')
                        else:
                            self.win.insstr(ch)
                        self.right_scroll_mark()
                        self.win.move(0,self.pos-self.offset)
            if cjc_globals.screen.active:
                self.win.refresh()
        finally:
            cjc_globals.screen.lock.release()

    def history_prev(self):
        self.completing=0
        if not self.history_len or self.history_pos>=len(self.history):
            cjc_globals.screen.beep()
            return
        if self.history_pos==0:
            self.saved_content=self.content
        self.history_pos+=1
        self.content=self.history[-self.history_pos]
        self.pos=len(self.content)
        self.offset=0
        if self.pos>self.offset+self.w-2:
            self.scroll_right()
        else:
            self.redraw()

    def history_next(self):
        self.completing=0
        if not self.history_len or self.history_pos<=0:
            cjc_globals.screen.beep()
            return
        self.history_pos-=1
        if self.history_pos==0:
            if self.saved_content:
                self.content=self.saved_content
            else:
                self.content=u""
        else:
            self.content=self.history[-self.history_pos]
            self.pos=len(self.content)
        self.pos=len(self.content)
        self.offset=0
        if self.pos>self.offset+self.w-2:
            self.scroll_right()
        else:
            self.redraw()

    def update(self,now=1,refresh=0):
        if not cjc_globals.screen:
            return
        if self.pos>len(self.content):
            self.pos=len(self.content)
        cjc_globals.screen.lock.acquire()
        try:
            if not cjc_globals.screen.active:
                return
            if self.pos<0 or (self.offset and self.pos<=self.offset):
                if self.offset:
                    self.pos=self.offset+1
                else:
                    self.pos=0
            elif self.pos>=self.offset+self.w-1:
                self.pos=self.offset+self.w-2
            if refresh:
                if self.offset>0:
                    self.left_scroll_mark()
                    if self.private:
                        s = u'*' * (self.w-1)
                    else:
                        s = self.content[self.offset+1:self.offset+self.w-1]
                    self.win.addstr(s.encode(cjc_globals.screen.encoding,"replace"))
                else:
                    if self.private:
                        s = u'*' * min(self.w - 1, len(self.content))
                    else:
                        s = self.content[:self.w-1]
                    self.win.addstr(0,0,s.encode(cjc_globals.screen.encoding,"replace"))
                self.win.clrtoeol()
                self.right_scroll_mark()
            self.win.move(0,self.pos-self.offset)
            if now:
                self.win.refresh()
            else:
                self.win.noutrefresh()
        finally:
            cjc_globals.screen.lock.release()

from keytable import KeyFunction
ktb=keytable.KeyTable("text-input",50,(
        KeyFunction("complete",
                TextInput.key_complete,
                "Complete input",
                ("\t")),
        KeyFunction("accept-line",
                TextInput.key_enter,
                "Accept input",
                ("ENTER","\n","\r")),
        KeyFunction("beginning-of-line",
                TextInput.key_home,
                "Move to the begining",
                ("HOME","^A")),
        KeyFunction("end-of-line",
                TextInput.key_end,
                "Move to the end",
                ("END","^E")),
        KeyFunction("forward-char",
                TextInput.key_right,
                "Move right",
                ("RIGHT","^F")),
        KeyFunction("backward-char",
                TextInput.key_left,
                "Move left",
                ("LEFT","^B")),
        KeyFunction("previous-history",
                TextInput.history_prev,
                "Previous history item",
                ("UP","^P")),
        KeyFunction("next-history",
                TextInput.history_next,
                "Next history item",
                ("DOWN","^N")),
        KeyFunction("backward-delete-char",
                TextInput.key_bs,
                "Delete previous character",
                ("BACKSPACE","^H")),
        KeyFunction("delete-char",
                TextInput.key_del,
                "Delete current character",
                ("DC","^D","\x7f")),
        KeyFunction("kill-line",
                TextInput.key_kill,
                "Erase whole text",
                "^K"),
        KeyFunction("unix-word-rubout",
                TextInput.key_wrubout,
                "Kill the word behind cursor",
                "^W"),
        KeyFunction("unix-line-discard",
                TextInput.key_uclean,
                "Kill backward from cursor to the beginning of the line",
                "^U"),
        ))

keytable.install(ktb)
# vi: sts=4 et sw=4
