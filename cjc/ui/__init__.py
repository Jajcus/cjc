
import curses

from cjc import commands
from screen import Screen
from text_buffer import TextBuffer
from list_buffer import ListBuffer
from window import Window
from status_bar import StatusBar
from edit_line import EditLine
from split import HorizontalSplit,VerticalSplit

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
