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

from cjc.ui.screen import Screen
from cjc.ui.text_buffer import TextBuffer
from cjc.ui.list_buffer import ListBuffer,ListBufferError
from cjc.ui.window import Window
from cjc.ui.status_bar import StatusBar
from cjc.ui.input import Input
from cjc.ui.split import HorizontalSplit,VerticalSplit

from cjc.ui.keytable import KeytableError,KeyBinding,KeyFunction,KeyTable,keypressed,bind,unbind
from cjc.ui.keytable import install as install_keytable
from cjc.ui.keytable import activate as activate_keytable
from cjc.ui.keytable import deactivate as deactivate_keytable

from cjc.ui.cmdtable import CommandError,CommandTable,Command,CommandAlias,CommandArgs,run_command
from cjc.ui.cmdtable import install as install_cmdtable
from cjc.ui.cmdtable import uninstall as uninstall_cmdtable
from cjc.ui.cmdtable import activate as activate_cmdtable
from cjc.ui.cmdtable import deactivate as deactivate_cmdtable
from cjc.ui.cmdtable import set_default_handler as set_default_command_handler

from cjc.ui.complete import Completion

def init():
    screen=curses.initscr()
    if curses.has_colors():
        curses.start_color()
    curses.cbreak()
    curses.meta(1)
    curses.noecho()
    curses.nonl()
    curses.def_prog_mode()
    curses.endwin()
    curses.def_shell_mode()
    curses.reset_prog_mode()
    return Screen(screen)

def deinit():
    curses.endwin()
# vi: sts=4 et sw=4
