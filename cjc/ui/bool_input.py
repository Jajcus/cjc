
import curses
import curses.textpad
import string

from widget import Widget
from cjc import common


class BooleanInput:
	def __init__(self,parent,abortable,default=None):
		self.parent=parent
		self.abortable=abortable
		self.win=None
		self.content=u""
		if default==1:
			self.prompt="[Y/n]: "
		elif default==0:
			self.prompt="[y/N]: "
		else:
			self.prompt="[y/n]: "
			default=None
		self.default=default
		
	def set_window(self,win):
		if win:
			self.win=win
			self.h,self.w=win.getmaxyx()
			self.screen=self.parent.screen
			self.win.keypad(1)
			self.win.leaveok(0)
			self.win.addstr(0,0,self.prompt)
		else:
			self.win=None

	def keypressed(self,c,escape):
		self.screen.lock.acquire()
		try:
			return self._keypressed(c,escape)
		finally:
			self.screen.lock.release()
		
	def _keypressed(self,c,escape):
		if c==27:
			if self.abortable:
				self.parent.abort_handler()
				return
			else:
				curses.beep()
				return
		elif c==curses.KEY_ENTER:
			return self.key_enter()
		elif c>255 or c<0:
			curses.beep()
			return
		c=chr(c)
		if c in "\n\r":
			self.key_enter()
		elif c in "Yy":
			self.answer(1)
		elif c in "Nn":
			self.answer(0)
		else:
			curses.beep()

	def key_enter(self):
		if self.default is None:
			curses.beep()
			return
		self.answer(self.default)

	def answer(self,ans):
		if ans:
			self.content=u"y"
		else:
			self.content=u"n"
		self.win.addstr(self.content)
		self.update()
		self.parent.input_handler(ans)

	def update(self,now=1,refresh=0):
		self.screen.lock.acquire()
		try:
			if refresh:
				self.win.erase()
				s=self.prompt.encode(self.screen.encoding,"replace")
				self.win.addstr(0,0,s)
				s=self.content.encode(self.screen.encoding,"replace")
				self.win.addstr(s)
			else:
				self.win.move(0,len(self.prompt)+len(self.content))
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()

	def redraw(self,now=1):
		self.update(now,1)

	def cursync(self,now=1):
		self.screen.lock.acquire()
		try:
			self.win.cursyncup()
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()
