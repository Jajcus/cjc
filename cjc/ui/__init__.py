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

from screen import Screen
from text_buffer import TextBuffer
from list_buffer import ListBuffer,ListBufferError
from window import Window
from status_bar import StatusBar
from input import Input
from split import HorizontalSplit,VerticalSplit

from keytable import KeytableError,KeyBinding,KeyFunction,KeyTable,keypressed,bind,unbind
from keytable import install as install_keytable
from keytable import activate as activate_keytable
from keytable import deactivate as deactivate_keytable

from cmdtable import CommandError,CommandTable,Command,CommandAlias,CommandArgs,run_command
from cmdtable import install as install_cmdtable
from cmdtable import uninstall as uninstall_cmdtable
from cmdtable import activate as activate_cmdtable
from cmdtable import deactivate as deactivate_cmdtable
from cmdtable import set_default_handler as set_default_command_handler

from complete import Completion

def init():
    screen=curses.initscr()
    if curses.has_colors():
        curses.start_color()
    curses.cbreak()
    curses.meta(1)
    curses.noecho()
    curses.nonl()
    return Screen(screen)

def deinit():
    curses.endwin()
# vi: sts=4 et sw=4
