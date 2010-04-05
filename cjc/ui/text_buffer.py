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

import logging
from types import StringType,IntType,UnicodeType

from cjc.ui.buffer import Buffer
from cjc import common
from cjc.ui import keytable
from cjc import cjc_globals

class TextBuffer(Buffer):
    default_length = 200
    def __init__(self, info, descr_format = "default_buffer_descr",
                command_table = None, command_table_object = None, length = None):
        Buffer.__init__(self,info,descr_format,command_table,command_table_object)
        if length:
            self.length = length
        else:
            self.length = self.default_length
        self.lines=[]
        self.pos=None
        self.update_pos()

    def set_window(self,win):
        Buffer.set_window(self,win)
        if win:
            keytable.activate("text-buffer",self)
        else:
            keytable.deactivate("text-buffer",self)

    def append(self,s,attr="default",activity_level=1):
        self.lock.acquire()
        try:
            return self._append(s,attr,activity_level)
        finally:
            self.lock.release()

    def _append(self,s,attr,activity_level=1):
        if attr is not None and type(attr) is not IntType:
            attr=cjc_globals.theme_manager.attrs[attr]
        if not self.lines:
            self.lines=[[]]
        elif self.lines[-1]==[] and self.window and self.pos is None:
            self.window.nl()
        newl=0
        s=s.split(u"\n")
        ln=len(s)
        for i in range(0,ln):
            l=s[i]
            if newl:
                if i<ln-1 and self.window and self.pos is None:
                    self.window.nl()
                self.lines.append([])
            if l:
                self.lines[-1].append((attr,l))
                if self.window and self.pos is None:
                    y,x=self.window.win.getyx()
                    while l:
                        if x+len(l)>self.window.iw:
                            p,l=self.split_text(l,self.window.iw-x)
                        else:
                            p,l=l,None
                        self.window.write(p,attr)
                        x+=len(p)
                        if x>=self.window.iw:
                            x=0
                            y+=1
                            if y>=self.window.ih:
                                y=self.window.ih-1
                    else:
                        self.window.write(l,attr)
            newl=1
        l=len(self.lines)
        if l>self.length and self.pos is None:
            self.lines=self.lines[-self.length:]
        if not self.window or self.pos is not None and activity_level:
            self.activity(activity_level)

    def append_line(self,s,attr="default",activity_level=1):
        self.lock.acquire()
        try:
            return self._append_line(s,attr,activity_level)
        finally:
            self.lock.release()

    def _append_line(self,s,attr,activity_level=1):
        if type(attr) is not IntType:
            attr=cjc_globals.theme_manager.attrs[attr]
        self._append(s+u"\n",attr,activity_level)

    def append_themed(self,format,params,activity_level=1):
        for attr,s in cjc_globals.theme_manager.format_string(format,params):
            self.append(s,attr,activity_level)

    def write(self,s):
        self.lock.acquire()
        try:
            self._append(s,"default")
            self.update()
        finally:
            self.lock.release()

    def clear(self):
        self.lock.acquire()
        try:
            self.pos=None
            self.lines=[[]]
            if self.window:
                self.window.clear()
        finally:
            self.lock.release()

    def line_length(self,line):
        ret=0
        for attr,s in line:
            ret+=len(s)
        return ret

    def offset_back(self,width,back,l=None,c=0):
        if not self.lines:
            return 0,0
        if l is None or l>=len(self.lines):
            if self.lines[-1]==[]:
                l=len(self.lines)-1
            else:
                l=len(self.lines)
            if l<=0:
                return 0,0
        while back>0 and l>1:
            l-=1
            line=self.lines[l]
            ln=self.line_length(line)
            h=ln/width+1
            back-=h
        if back>0:
            return 0,0
        if back==0:
            return l,0
        return l,(-back)*width

    def offset_forward(self,width,forward,l=0,c=0):
        if l>=len(self.lines):
            l=len(self.lines)-1
            if self.lines[-1]==[]:
                l-=1
            if l>0:
                return l,0
            else:
                return 0,0

        if c>0:
            left,right=self.split_text(self.lines[l],c)
            l+=1
            ln=self.line_length(right)
            forward-=ln/width+1

        end=len(self.lines)
        if self.lines[-1]==[]:
            end-=1

        l-=1
        while forward>0 and l<end-1:
            l+=1
            line=self.lines[l]
            ln=self.line_length(line)
            h=ln/width+1
            forward-=h

        if forward>=0:
            return l,0

        if l>0:
            return l-1,0
        else:
            return 0,0

    def split_text(self,s,n,allow_all=0):
        return s[:n],s[n:]

    def cut_line(self,line,cut):
        i=0
        left=[]
        right=[]
        for attr,s in line:
            l=len(s)
            i1=i
            i+=l
            if i<cut:
                left.append((attr,s))
            elif i1<cut and i>cut:
                left.append((attr,s[:cut-i]))
                right.append((attr,s[cut-i:]))
            else:
                right.append((attr,s))
        return left,right

    def format(self,width,height):
        self.lock.acquire()
        try:
            return self._format(width,height)
        finally:
            self.lock.release()

    def _format(self,width,height):
        if self.pos is None:
            l,c=self.offset_back(width,height)
        else:
            l,c=self.pos
        if c:
            x,line=self.cut_line(self.lines[l],c)
            ret=[line]
            l+=1
            height-=self.line_length(line)/width+1
        else:
            ret=[]

        end=len(self.lines)
        if end and self.lines[-1]==[]:
            end-=1

        while height>0 and l<end:
            line=self.lines[l]
            while line is not None and height>0:
                ln=self.line_length(line)
                if ln>width:
                    part,line=self.cut_line(line,width)
                else:
                    part,line=line,None
                if part==[] and height==1:
                    break
                ret.append(part)
                height-=1
            l+=1
        return ret

    def update_pos(self):
        if self.pos:
            self.update_info({"bufrow":self.pos[0],"bufcol":self.pos[1]})
        else:
            self.update_info({"bufrow":"","bufcol":""})

    def page_up(self):
        self.lock.acquire()
        try:
            if self.pos is None:
                l,c=self.offset_back(self.window.iw,self.window.ih-1)
            else:
                l,c=self.pos

            if (l,c)==(0,0):
                self.pos=l,c
                formatted=self._format(self.window.iw,self.window.ih+1)
                if len(formatted)<=self.window.ih:
                    self.pos=None
                self.update_pos()
                return
            l1,c1=self.offset_back(self.window.iw,self.window.ih-1,l,c)
            self.pos=l1,c1
        finally:
            self.lock.release()
        self.update_pos()
        self.window.draw_buffer()
        self.window.update()

    def page_down(self):
        self.lock.acquire()
        try:
            if self.pos is None:
                self.update_pos()
                return

            l,c=self.pos

            l1,c1=self.offset_forward(self.window.iw,self.window.ih-1,l,c)
            self.pos=l1,c1
            formatted=self.format(self.window.iw,self.window.ih+1)
            if len(formatted)<=self.window.ih:
                self.pos=None
            if self.pos:
                self.window.update_status({"bufrow":self.pos[0],"bufcol":self.pos[1]})
            else:
                self.window.update_status({"bufrow":"","bufcol":""})
            self.update_pos()
            self.window.draw_buffer()
            self.window.update()
        finally:
            self.lock.release()

    def as_string(self):
        self.lock.acquire()
        try:
            ret=""
            l=len(self.lines)
            for i in range(0,l):
                for a,s in self.lines[i]:
                    ret+=s
                if i<l-1:
                    ret+="\n"
        finally:
            self.lock.release()
        return ret

from keytable import KeyFunction
ktb=keytable.KeyTable("text-buffer",30,(
        KeyFunction("page-up",
                TextBuffer.page_up,
                "Scroll buffer one page up",
                "PPAGE"),
        KeyFunction("page-down",
                TextBuffer.page_down,
                "Scroll buffer one page down",
                "NPAGE"),
        ))

keytable.install(ktb)
# vi: sts=4 et sw=4
