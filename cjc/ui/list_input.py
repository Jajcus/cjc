
import curses
import curses.textpad
import string

from widget import Widget
from cjc import common


class ListInput:
	def __init__(self,parent,abortable,default,values):
		self.parent=parent
		self.abortable=abortable
		self.win=None
		self.capture_rest=0
		self.keys=values.keys()
		self.keys.sort()
		self.values=values
		try:
			self.choice=self.keys.index(default)
		except ValueError:
			self.choice=-1
		self.theme_manager=parent.theme_manager
		
	def set_window(self,win):
		if win:
			self.win=win
			self.h,self.w=win.getmaxyx()
			self.screen=self.parent.screen
			self.win.keypad(1)
			self.win.leaveok(0)
			self.redraw()
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
		elif c==curses.KEY_UP:
			return self.key_up()
		elif c==curses.KEY_DOWN:
			return self.key_down()
		elif c>255 or c<0:
			curses.beep()
			return
		c=chr(c)
		if c in ("\n\r"):
			self.key_enter()
		elif c==" ":
			self.key_space()
		else:
			curses.beep()

	def key_enter(self):
		if self.choice<0:
			ans=None
		else:
			ans=self.keys[self.choice]
		self.parent.input_handler(ans)

	def key_up(self):
		if self.choice<=0:
			self.choice=len(self.keys)-1
		else:
			self.choice-=1
		self.redraw()

	def key_down(self):
		if self.choice<len(self.keys)-1:
			self.choice+=1
		else:
			self.choice=0
		self.redraw()

	def update(self,now=1,refresh=0):
		self.screen.lock.acquire()
		try:
			if refresh:
				if self.choice<0:
					s=u""
				else:
					s=self.values[self.keys[self.choice]]
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