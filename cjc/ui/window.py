# Console Jabber Client
# Copyright (C) 2004-2006  Jacek Konieczny
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
import re
import logging

from cjc.ui import buffer
from cjc.ui import keytable
from cjc.ui import cmdtable
from cjc.ui.widget import Widget
from cjc.ui.status_bar import StatusBar
from cjc import common

control_re=re.compile("[\x00-\x1f\x7f]",re.UNICODE)

class Window(Widget):
    def __init__(self,theme_manager,title,lock=0):
        self.__logger=logging.getLogger("cjc.ui.Window")
        Widget.__init__(self)
        self.buffer=None
        self.title=title
        self.win=None
        self.locked=lock
        self.active=0
        d=self.get_status_dict()
        self.status_bar=StatusBar(theme_manager,"window_status",d)

    def get_status_dict(self):
        if self.locked:
            l="!"
        else:
            l=""
        if self.active:
            a="*"
        else:
            a=""

        d={"active":a,"winname":self.title,"locked":l}
        if self.buffer:
            d.update(self.buffer.info)
        else:
            d["buffer_descr"]="default_buffer_descr"
            d["bufname"]=""
        return d

    def switch_to_buffer(self,n):
        n=int(n)
        b=buffer.get_by_number(n)
        if b is None:
            return 1
        old=b.window
        if old and old.locked:
            return 1
        self.set_buffer(b)
        self.update()
        if old:
            old.update()
        return 1

    def switch_to_active_buffer(self):
        bl=[(-b.preference,b.active,b.get_number(),b)
                for b in buffer.buffer_list
                if b and b.preference>0 and b.active>0]
        if not bl:
            return 1
        bl.sort()
        self.set_buffer(bl[0][3])
        self.update()
        return 1

    def cmd_clear(self,args):
        args.finish()
        if not self.win:
            return
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            self.win.erase()
            self.update()
        finally:
            self.screen.lock.release()

    def user_input(self,s):
        if self.buffer:
            return self.buffer.user_input(s)
        return 0

    def place(self,child):
        if child is not self.status_bar:
            raise ValueError,"%r is not a child of mine" % (child,)
        return (self.x,self.y+self.h-1,self.w,1)

    def set_parent(self,parent):
        Widget.set_parent(self,parent)
        self.iw=self.w
        self.ih=self.h-1
        self.screen.lock.acquire()
        try:
            self.win=curses.newwin(self.ih,self.iw,self.y,self.x)
            self.win.idlok(1)
            self.win.scrollok(1)
            self.win.leaveok(1)
        finally:
            self.screen.lock.release()
        self.status_bar.set_parent(self)
        if self.buffer:
            self.draw_buffer()

        if self not in self.screen.windows:
            self.screen.add_window(self)

    def set_active(self,yes):
        if yes:
            self.active=1
            a="*"
            keytable.activate("window",self)
            cmdtable.activate("window",self)
        else:
            self.active=0
            a=""
            keytable.deactivate("window",self)
            cmdtable.deactivate("window",self)
        d=self.status_bar.get_dict()
        d["active"]=a
        if self.screen:
            self.status_bar.update(0)
            if yes and self.screen.input_handler:
                self.screen.input_handler.current_buffer_changed(self.buffer)

    def set_buffer(self,buf):
        if self.buffer:
            self.buffer.set_window(None)
        if buf:
            if buf.window:
                buf.window.set_buffer(self.buffer)
        self.buffer=buf
        self.status_bar.dict=self.get_status_dict()
        if buf:
            buf.set_window(self)
        if self.win:
            self.draw_buffer()
        if self.screen:
            self.status_bar.update(1)
        if self.active and self.screen.input_handler:
            self.screen.input_handler.current_buffer_changed(self.buffer)

    def update_status(self,d,now=1):
        self.status_bar.get_dict().update(d)
        self.status_bar.update(now)

    def draw_buffer(self):
        lines=self.buffer.format(self.iw,self.ih)
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            self.win.erase()
            self.win.move(0,0)
            if not self.buffer:
                return
            if not lines:
                return
            eol=0
            self.__logger.debug("lines: "+`lines`)
            for line in lines:
                if eol:
                    self.win.addstr("\n")
                x=0
                for attr,s in line:
                    x+=len(s)
                    if x>self.iw:
                        s=s[:-(x-self.iw)]
                    s=s.encode(self.screen.encoding,"replace")
                    if attr is not None:
                        self.win.addstr(s,attr)
                    else:
                        self.win.addstr(s)
                    if x>=self.iw:
                        break
                if x<self.iw:
                    eol=1
                else:
                    eol=0
        finally:
            self.screen.lock.release()

    def nl(self):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            self.win.addstr("\n")
        finally:
            self.screen.lock.release()

    def delete_line(self,y):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            self.win.move(y,0)
            self.win.deleteln()
        finally:
            self.screen.lock.release()

    def insert_line(self,y):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            self.win.move(y,0)
            self.win.insertln()
        finally:
            self.screen.lock.release()

    def clear(self):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            self.win.erase()
        finally:
            self.screen.lock.release()

    def clrtoeol(self):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            self.win.clrtoeol()
        finally:
            self.screen.lock.release()

    def write(self,s,attr):
        if not s:
            return
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            return self._write(s,attr)
        finally:
            self.screen.lock.release()

    def write_at(self,x,y,s,attr):
        if not s:
            return
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            self.win.move(y,x)
            return self._write(s,attr)
        finally:
            self.screen.lock.release()

    def _write(self,s,attr):
        y,x=self.win.getyx()
        s=control_re.sub(u"\ufffd",s)

        if len(s)+x>self.iw:
            s=s[:self.iw-x]
        s=s.encode(self.screen.encoding,"replace")
        if attr is not None:
            self.win.addstr(s,attr)
        else:
            self.win.addstr(s)

    def update(self,now=1,redraw=0):
        self.status_bar.update(now)
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            if redraw:
                self.win.erase()
                if self.buffer:
                    self.draw_buffer()
            self.status_bar.update(now,redraw)
            if now:
                self.win.refresh()
                self.screen.cursync()
            else:
                self.win.noutrefresh()
        finally:
            self.screen.lock.release()

keytable.KeyTable("window",60,(
        keytable.KeyFunction("switch-to-active-buffer",
            Window.switch_to_active_buffer,
            "Switch to the first active buffer",
            "M-a"),
        keytable.KeyFunction("switch-to-buffer()",
            Window.switch_to_buffer,
            "Switch to buffer <arg>"),
        keytable.KeyBinding("switch-to-buffer(1)","M-1"),
        keytable.KeyBinding("switch-to-buffer(2)","M-2"),
        keytable.KeyBinding("switch-to-buffer(3)","M-3"),
        keytable.KeyBinding("switch-to-buffer(4)","M-4"),
        keytable.KeyBinding("switch-to-buffer(5)","M-5"),
        keytable.KeyBinding("switch-to-buffer(6)","M-6"),
        keytable.KeyBinding("switch-to-buffer(7)","M-7"),
        keytable.KeyBinding("switch-to-buffer(8)","M-8"),
        keytable.KeyBinding("switch-to-buffer(9)","M-9"),
        keytable.KeyBinding("switch-to-buffer(0)","M-0"),
    )).install()

cmdtable.CommandTable("window",80,(
    cmdtable.Command("clear",Window.cmd_clear,
        "/clear",
        "Clears current window"),
    )).install()
# vi: sts=4 et sw=4
