# Console Jabber Client
# Copyright (C) 2004-2005  Jacek Konieczny
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

class Widget:
    def __init__(self):
        self.screen=None
        self.parent=None

    def set_parent(self,parent):
        self.parent=parent
        self.screen=parent.screen
        self.x,self.y,self.w,self.h=self.parent.place(self)

    def get_height(self):
        return None

    def get_width(self):
        return None

    def update(self,now=1,redraw=0):
        pass

    def redraw(self,now=1):
        self.update(now,1)

# vi: sts=4 et sw=4
