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
from types import StringType,UnicodeType,IntType,XRangeType

from cjc.ui import keytable
from cjc import common
from cjc.ui.input_widget import InputWidget

class ChoiceInput(InputWidget):
    def __init__(self,abortable,required,default,choice):
        InputWidget.__init__(self,abortable,required)
        from input import InputError
        self.single_choice=[]
        self.string_choice=[]
        self.range_choice=[]
        prompt=[]
        for c in choice:
            if type(c) in (StringType,UnicodeType):
                if len(c)==1:
                    self.single_choice.append(c)
                else:
                    self.string_choice.append(c)
                if c==default:
                    prompt.append(c.upper())
                else:
                    prompt.append(c)
            elif type(c) is IntType:
                self.range_choice.append(xrange(c,c+1))
                prompt.append(str(c))
            elif type(c) is XRangeType:
                self.range_choice.append(c)
                p="%i-%i" % (c[0],c[-1])
                if default in c:
                    p+="(%i)" % (default,)
                prompt.append(p)
            else:
                raise InputError,"Bad choice value: %r" % (c,)
        self.prompt=u" [%s]: " % (string.join(prompt,"/"))
        self.content=u""
        self.default=default
        self.pos=0

    def set_parent(self,parent):
        InputWidget.set_parent(self,parent)
        if parent:
            keytable.activate("choice-input",self,self.keypressed,self.win)
        else:
            keytable.deactivate("choice-input",self)

    def keypressed(self,c,escape):
        self.screen.lock.acquire()
        try:
            return self._keypressed(c,escape)
        finally:
            self.screen.lock.release()

    def _keypressed(self,c,escape):
        if c>255 or c<0:
            self.screen.beep()
            return
        c=chr(c)
        if c in self.printable:
            self.key_char(c)
        else:
            self.screen.beep()

    def key_abort(self):
        if self.abortable:
            self.parent.abort_handler()
            return
        else:
            self.screen.beep()
            return

    def key_enter(self):
        if self.content:
            ans=self.content
        else:
            ans=self.default
        ival=None
        if ans in self.single_choice:
            return self.answer(ans)
        if ans in self.string_choice:
            return self.answer(ans)
        if not ans:
            if not self.required:
                return self.answer(None)
            return self.screen.beep()
        try:
            ival=int(ans)
        except ValueError:
            return self.screen.beep()
        for r in self.range_choice:
            if ival in r:
                return self.answer(ival)
        self.screen.beep()

    def answer(self,ans):
        if ans is not None:
            if type(ans) is UnicodeType:
                self.content=ans
            else:
                self.content=unicode(ans)
            self.redraw()
        self.parent.input_handler(ans)

    def key_bs(self):
        if self.pos<=0:
            self.screen.beep()
            return
        self.content=self.content[:self.pos-1]+self.content[self.pos:]
        self.pos-=1
        self.screen.lock.acquire()
        try:
            if self.screen.active:
                self.win.move(0,self.pos+len(self.prompt))
                self.win.delch()
                self.win.refresh()
        finally:
            self.screen.lock.release()

    def key_char(self,c):
        c=unicode(c,self.screen.encoding,"replace")
        if not self.string_choice and c in self.single_choice:
            return self.answer(c)
        if self.pos>=self.w-len(self.prompt)-2:
            return self.screen.beep()
        newcontent=self.content+c
        if c in string.digits and self.range_choice:
            pass
        elif newcontent in self.single_choice:
            pass
        else:
            ok=0
            for v in self.string_choice:
                if v.startswith(newcontent):
                    ok=1
                    break
            if not ok:
                return self.screen.beep()

        self.content=newcontent
        self.pos+=1
        self.screen.lock.acquire()
        try:
            if self.screen.active:
                self.win.addstr(c.encode(self.screen.encoding,"replace"))
                self.win.refresh()
        finally:
            self.screen.lock.release()

    def update(self,now=1,refresh=0):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            if refresh:
                self.win.move(0,0)
                self.win.clrtoeol()
                s=self.prompt.encode(self.screen.encoding,"replace")
                self.win.addstr(s)
                s=self.content.encode(self.screen.encoding,"replace")
                self.win.addstr(s)
            self.win.move(0,self.pos+len(self.prompt))
            if now:
                self.win.refresh()
            else:
                self.win.noutrefresh()
        finally:
            self.screen.lock.release()

from keytable import KeyFunction
ktb=keytable.KeyTable("choice-input",50,(
        KeyFunction("accept-input",
                ChoiceInput.key_enter,
                "Accept input",
                ("ENTER","\n","\r")),
        KeyFunction("abort-input",
                ChoiceInput.key_abort,
                "Abort input",
                "ESCAPE"),
        KeyFunction("backward-delete-char",
                ChoiceInput.key_bs,
                "Delete previous character",
                ("BACKSPACE","^H")),
        ))
keytable.install(ktb)
# vi: sts=4 et sw=4
