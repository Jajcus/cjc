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
import logging

from cjc.ui.widget import Widget

class Split(Widget):
    def __init__(self,*children):
        if len(children)<1:
            raise ValueError,"At least 2 children must be given"
        Widget.__init__(self)
        self.children=children

class VerticalSplit(Split):
    def __init__(self,*children):
        apply(Split.__init__,[self]+list(children))
        self.divs=[]
        self.children_pos=[]
        self.widths=[]

    def set_parent(self,parent):
        Widget.set_parent(self,parent)

        self.widths=[]
        sum_width=0
        no_widths=0
        for c in self.children:
            w=c.get_width()
            self.widths.append(w)
            if w is None:
                no_widths+=1
            else:
                sum_width+=w

        width_left=self.w-(len(self.children)-1)-sum_width
        if width_left<no_widths:
            raise ValueError,"Not enough space for all widgets"

        if no_widths:
            for i in range(0,len(self.widths)):
                if self.widths[i] is None:
                    self.widths[i]=width_left/no_widths
                    width_left-=width_left/no_widths
                    no_widths-=1

        l=0
        for i in range(0,len(self.children)):
            r=l+self.widths[i]
            if i>0:
                div=curses.newwin(self.h,1,self.y,l-1)
                div.leaveok(1)
                div.bkgdset(ord("|"),curses.A_STANDOUT)
                div.erase()
                self.divs.append(div)
            self.children_pos.append(l)
            l=r+1

        for c in self.children:
            c.set_parent(self)

    def place(self,child):
        for i in range(0,len(self.children)):
            if self.children[i] is child:
                x=self.children_pos[i]
                w=self.widths[i]
                return (x,self.y,w,self.h)
        raise "%r is not a child of mine" % (child,)

    def update(self,now=1,redraw=0):
        self.screen.lock.acquire()
        try:
            if not self.screen.active:
                return
            for div in self.divs:
                div.noutrefresh()
            for c in self.children:
                c.update(0,redraw)
            if now:
                curses.doupdate()
                self.screen.cursync()
        finally:
            self.screen.lock.release()

class HorizontalSplit(Split):
    def __init__(self,*children):
        apply(Split.__init__,[self]+list(children))
        self.heights=[]
        self.children_pos=[]
        self.heights=[]

    def set_parent(self,parent):
        Widget.set_parent(self,parent)

        self.heights=[]
        sum_height=0
        no_heights=0
        for c in self.children:
            h=c.get_height()
            self.heights.append(h)
            if h is None:
                no_heights+=1
            else:
                sum_height+=h

        height_left=self.h-sum_height
        if height_left<no_heights:
            raise ValueError,"Not enough space for all widgets"

        if no_heights:
            for i in range(0,len(self.heights)):
                if self.heights[i] is None:
                    self.heights[i]=height_left/no_heights
                    height_left-=height_left/no_heights
                    no_heights-=1

        t=0
        for i in range(0,len(self.children)):
            b=t+self.heights[i]
            self.children_pos.append(t)
            t=b

        for c in self.children:
            c.set_parent(self)

    def place(self,child):
        for i in range(0,len(self.children)):
            if self.children[i] is child:
                y=self.children_pos[i]
                h=self.heights[i]
                return (self.x,y,self.w,h)
        raise "%r is not a child of mine" % (child,)

    def update(self,now=1,redraw=0):
        for c in self.children:
            c.update(now,redraw)
        self.screen.cursync()
# vi: sts=4 et sw=4
