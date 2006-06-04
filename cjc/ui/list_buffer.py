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


from types import StringType,IntType,UnicodeType
import curses
import logging

from cjc import common
from cjc.ui import keytable
from cjc.ui.buffer import Buffer

class ListBufferError(StandardError):
    pass

class ListBuffer(Buffer):
    def __init__(self,theme_manager,name,command_table=None,command_table_object=None):
        Buffer.__init__(self,name,command_table=command_table,
                command_table_object=command_table_object)
        self.__logger=logging.getLogger("cjc.ui.ListBuffer")
        self.theme_manager=theme_manager
        self.keys=[]
        self.items=[]
        self.pos=0

    def set_window(self,win):
        Buffer.set_window(self,win)
        if win:
            keytable.activate("list-buffer",self)
        else:
            keytable.deactivate("list-buffer",self)

    def get_keys(self):
        return self.keys

    def has_key(self,key):
        return key in self.keys;

    def index(self,key):
        return self.keys.index(key)

    def append(self,key,view):
        self.lock.acquire()
        try:
            if key in self.keys:
                raise ListBufferError,"Item already exists"
            view=self.clean_item(view)
            i=len(self.keys)
            self.keys.append(key)
            self.items.append(view)
            self.activity(1)
            self.display(i)
        finally:
            self.lock.release()

    def insert_sorted(self,key,view):
        self.lock.acquire()
        try:
            if key in self.keys:
                raise ListBufferError,"Item already exists"
            view=self.clean_item(view)
            last=1
            for i in range(0,len(self.keys)):
                if self.keys[i]>key:
                    self.keys.insert(i,key)
                    self.items.insert(i,view)
                    last=0
                    break
            if last:
                i=len(self.keys)
                self.keys.append(key)
                self.items.append(view)
            self.activity(1)
            self.display(i,1)
        finally:
            self.lock.release()

    def update_item(self,key,view):
        self.lock.acquire()
        try:
            try:
                i=self.keys.index(key)
            except ValueError:
                raise ListBufferError,"Item not found"
            view=self.clean_item(view)
            self.items[i]=view
            self.activity(1)
            self.display(i)
        finally:
            self.lock.release()

    def remove_item(self,key):
        self.lock.acquire()
        try:
            try:
                i=self.keys.index(key)
            except ValueError:
                raise ListBufferError,"Item not found"
            del self.items[i]
            del self.keys[i]
            self.activity(1)
            self.undisplay(i)
        finally:
            self.lock.release()

    def clean_item(self,view):
        ret=[]
        for attr,s in view:
            s=s.replace("\n"," ").replace("\r"," ").replace("\f"," ").replace("\t"," ")
            ret.append((attr,s))
        return ret

    def insert_themed(self,key,format,params):
        view=[]
        for attr,s in self.theme_manager.format_string(format,params):
            view.append((attr,s))
        if self.has_key(key):
            self.update_item(key,view)
        else:
            self.insert_sorted(key,view)

    def clear(self):
        self.lock.acquire()
        try:
            self.keys=[]
            self.items=[]
            if self.window:
                self.window.clear()
        finally:
            self.lock.release()

    def format(self,width,height):
        self.lock.acquire()
        try:
            return self._format(width,height)
        finally:
            self.lock.release()

    def _format(self,width,height):
        ret=[]
        for i in range(self.pos,min(self.pos+height,len(self.keys))):
            ret.append(self.items[i])
        return ret

    def display(self, i, insert=0):
        self.lock.acquire()
        try:
            if not self.window:
                return
            self.window.screen.lock.acquire()
            try:
                if not self.window.screen.active:
                    return
                if i < self.pos:
                    return
                if i >= self.pos+self.window.ih:
                    return
                self.window.win.scrollok(0)
                self.__logger.debug("Updating item #%i" % (i,))
                if i >= len(self.items):
                    self.window.win.move(0, i - self.pos)
                    self.window.clrtoeol()
                    return
                view = self.items[i]
                attr, s = view[0]
                self.__logger.debug("Item: %r" % (view,))
                if insert:
                    self.window.insert_line(i - self.pos)
                self.window.write_at(0, i - self.pos, s, attr)
                for attr, s in view[1:]:
                    self.window.write(s, attr)
                y, x = self.window.win.getyx()
                if y == i - self.pos:
                    self.window.clrtoeol()
            finally:
                self.window.screen.lock.release()
                self.window.win.scrollok(1)
        finally:
            self.lock.release()

    def undisplay(self,i):
        self.lock.acquire()
        try:
            if not self.window:
                return
            if i<self.pos:
                return
            if i>=self.pos+self.window.ih:
                return
            self.__logger.debug("Erasing item #%i" % (i,))
            self.window.delete_line(i-self.pos)
            if len(self.items)>=self.pos+self.window.ih:
                self.display(self,self.pos+self.window.ih-1)
        finally:
            self.lock.release()

    def page_up(self):
        self.lock.acquire()
        try:
            if self.pos<=0:
                return
            self.pos-=self.window.ih
            if self.pos<0:
                self.pos=0
            self.window.draw_buffer()
            self.window.update()
        finally:
            self.lock.release()

    def page_down(self):
        self.lock.acquire()
        try:
            if self.pos>=len(self.keys)-self.window.ih+1:
                return
            self.pos+=self.window.ih
            self.window.draw_buffer()
            self.window.update()
        finally:
            self.lock.release()

    def as_string(self):
        self.lock.acquire()
        try:
            ret=""
            l=len(self.items)
            for i in range(0,l):
                for a,s in self.items[i]:
                    ret+=s
                ret+="\n"
        finally:
            self.lock.release()
        return ret

    def dump_content(self):
        self.lock.acquire()
        try:
            dump="List buffer dump of %r:\n" % (self.info["buffer_name"],)
            for i in range(0,len(self.items)):
                dump+="%5i. %r: %r\n" % (i,self.keys[i],self.items[i])
        finally:
            self.lock.release()
        self.__logger.debug("%s",dump)

from keytable import KeyFunction
ktb=keytable.KeyTable("list-buffer",30,(
        KeyFunction("page-up",
                ListBuffer.page_up,
                "Scroll buffer one page up",
                "PPAGE"),
        KeyFunction("page-down",
                ListBuffer.page_down,
                "Scroll buffer one page down",
                "NPAGE"),
        KeyFunction("dump-content",
                ListBuffer.dump_content,
                "Dump buffer content to the debug output",
                "M-d"),
        ))

keytable.install(ktb)
# vi: sts=4 et sw=4
