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
from types import ListType,TupleType

from cjc.ui import keytable
from cjc import common
from cjc.ui.input_widget import InputWidget

class ListInput(InputWidget):
    def __init__(self,abortable,required,default,values,multi=0):
        InputWidget.__init__(self,abortable,required)
        self.capture_rest=0
        self.multi=multi
        if type(values) in (TupleType,ListType):
            values=dict([(a,a) for a in values])
        self.keys=values.keys()
        self.keys.sort()
        self.values=values
        if not multi:
            try:
                self.choice=self.keys.index(default)
            except ValueError:
                self.choice=-1
        else:
            self.choice=0
            self.selected=[0]*len(self.keys)
            if default:
                for k in default:
                    try:
                        i=self.keys.index(k)
                    except ValueError:
                        continue
                    self.selected[i]=1

    def set_parent(self,parent):
        InputWidget.set_parent(self,parent)
        if parent:
            keytable.activate("list-input",self,input_window=self.win)
        else:
            keytable.deactivate("list-input",self)

    def key_abort(self):
        if self.abortable:
            self.parent.abort_handler()
            return
        else:
            self.screen.beep()

    def key_enter(self):
        if self.multi:
            ans=[]
            for i in range(0,len(self.selected)):
                if self.selected[i]:
                    ans.append(self.keys[i])
            if not ans and self.required:
                return self.screen.beep()
        else:
            if self.choice<0:
                if self.required:
                    return self.screen.beep()
                else:
                    ans=None
            else:
                ans=self.keys[self.choice]
        self.parent.input_handler(ans)

    def key_up(self):
        if self.choice==0 and (self.required or self.multi):
            self.choice=len(self.keys)-1
        elif self.choice<0:
            self.choice=len(self.keys)-1
        else:
            self.choice-=1
        self.redraw()

    def key_down(self):
        if self.choice<len(self.keys)-1:
            self.choice+=1
        elif self.required or self.multi:
            self.choice=0
        else:
            self.choice=-1
        self.redraw()

    def key_select(self):
        if not self.multi:
            return self.screen.beep()
        self.selected[self.choice]=not self.selected[self.choice]
        self.redraw()

    def update(self,now=1,refresh=0):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            if refresh:
                if self.choice<0:
                    s=u""
                else:
                    s=self.values[self.keys[self.choice]]
                if self.multi:
                    if self.selected[self.choice]:
                        s="+"+s
                    else:
                        s=" "+s
                if len(s)>self.w-2:
                    s=s[:self.w/2-3]+"(...)"+s[-self.w/2+4:]
                s=s.encode(self.screen.encoding,"replace")
                self.win.addch(0,0,curses.ACS_UARROW,
                        self.theme_manager.attrs["scroll_mark"])
                self.win.addstr(s,self.theme_manager.attrs["default"])
                self.win.clrtoeol()
                self.win.insch(0,self.w-1,curses.ACS_DARROW,
                        self.theme_manager.attrs["scroll_mark"])
            self.win.move(0,1)
            if now:
                self.win.refresh()
            else:
                self.win.noutrefresh()
        finally:
            self.screen.lock.release()


from keytable import KeyFunction
ktb=keytable.KeyTable("list-input",50,(
        KeyFunction("accept-input",
                ListInput.key_enter,
                "Accept input",
                ("ENTER","\n","\r")),
        KeyFunction("abort-input",
                ListInput.key_abort,
                "Abort input",
                "ESCAPE"),
        KeyFunction("next-option",
                ListInput.key_down,
                "Select the next option",
                "DOWN"),
        KeyFunction("previous-option",
                ListInput.key_up,
                "Select the previous option",
                "UP"),
        KeyFunction("select-option",
                ListInput.key_select,
                "Select current option",
                " "),
        ))
keytable.install(ktb)
# vi: sts=4 et sw=4
