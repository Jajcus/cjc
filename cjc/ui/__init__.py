
import curses

from screen import Screen
from text_buffer import TextBuffer
from list_buffer import ListBuffer
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
