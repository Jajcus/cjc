
import curses
import curses.textpad
import string

from widget import Widget
from cjc import common


class EditLine(Widget):
	def __init__(self,theme_manager):
		Widget.__init__(self)
		self.win=None
		self.capture_rest=0
		self.content=u""
		self.pos=0
		self.offset=0
		self.theme_manager=theme_manager
		
	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.screen.lock.acquire()
		try:
			self.win=curses.newwin(self.h,self.w,self.y,self.x)
			self.win.keypad(1)
			self.screen.set_default_key_handler(self)
		finally:
			self.screen.lock.release()
		self.printable=string.digits+string.letters+string.punctuation+" "

	def get_height(self):
		return 1

	def keypressed(self,c,escape):
		self.screen.lock.acquire()
		try:
			return self._keypressed(c,escape)
		finally:
			self.screen.lock.release()
		
	def _keypressed(self,c,escape):
		if escape:
			return
		if c==curses.KEY_ENTER:
			return self.key_enter()
		elif c==curses.KEY_HOME:
			return self.key_home()
		elif c==curses.KEY_END:
			return self.key_end()
		elif c==curses.KEY_LEFT:
			return self.key_left()
		elif c==curses.KEY_RIGHT:
			return self.key_right()
		elif c==curses.KEY_BACKSPACE:
			return self.key_bs()
		elif c==curses.KEY_DC:
			return self.key_del()
		elif c>255 or c<0:
			curses.beep()
			return
		c=chr(c)
		if c in ("\n\r"):
			self.key_enter()
		elif c=="\b":
			self.key_bs()
		elif c=="\x7f":
			self.key_del()
		elif c in self.printable:
			self.key_char(c)
		else:
			curses.beep()

	def left_scroll_mark(self):
		if self.offset>0:
			self.win.addstr(0,0,"<",self.theme_manager.attrs["scroll_mark"])
		
	def right_scroll_mark(self):
		if len(self.content)-self.offset>=self.w:
			self.win.insstr(0,self.w-1,">",self.theme_manager.attrs["scroll_mark"])

	def scroll_right(self):
		while self.pos>self.offset+self.w-2:
			self.offset+=self.w/4
		if self.offset>len(self.content)-2:
			self.offset=len(self.content)-2
		self.redraw()

	def scroll_left(self):
		while self.pos<self.offset+1:
			self.offset-=self.w/4
		if self.offset<0:
			self.offset=0
		self.redraw()
		
	def after_del(self):
		if len(self.content)-self.offset<self.w-1:
			self.win.move(0,self.pos-self.offset)
			return
		self.win.addstr(0,self.w-2,self.content[self.offset+self.w-2])
		if len(self.content)-self.offset==self.w-1:
			self.win.clrtoeol()
		else:
			self.right_scroll_mark()
		self.win.move(0,self.pos-self.offset)

	def key_enter(self):
		self.screen.user_input(self.content)
		self.content=u""
		self.pos=0
		self.offset=0
		self.win.move(0,0)
		self.win.clrtoeol()
		self.win.refresh()

	def key_home(self):
		if self.pos<=0:
			curses.beep()
			return
		self.pos=0
		if self.offset>0:
			self.scroll_left()
		else:
			self.win.move(0,self.pos-self.offset)
			self.win.refresh()

	def key_end(self):
		if self.pos>=len(self.content):
			curses.beep()
			return
		self.pos=len(self.content)
		if self.pos>self.offset+self.w-2:
			self.scroll_right()
		else:
			self.win.move(0,self.pos-self.offset)
			self.win.refresh()

	def key_left(self):
		if self.pos<=0:
			curses.beep()
			return
		self.pos-=1
		if self.pos and self.pos<self.offset+1:
			self.scroll_left()
		else:
			self.win.move(0,self.pos-self.offset)
			self.win.refresh()

	def key_right(self):
		if self.pos>=len(self.content):
			curses.beep()
			return
		self.pos+=1
		if self.pos>self.offset+self.w-2:
			self.scroll_right()
		else:
			self.win.move(0,self.pos-self.offset)
			self.win.refresh()

	def key_bs(self):
		if self.pos<=0:
			curses.beep()
			return
		self.content=self.content[:self.pos-1]+self.content[self.pos:]
		self.pos-=1
		if self.pos and self.pos<self.offset+1:
			self.scroll_left()
		else:
			self.win.move(0,self.pos-self.offset)
			self.win.delch()
			self.after_del()
			self.win.refresh()

	def key_del(self):
		if self.pos>=len(self.content):
			curses.beep()
			return
		self.content=self.content[:self.pos]+self.content[self.pos+1:]
		self.win.delch()
		self.after_del()
		self.win.refresh()

	def key_char(self,c):
		c=unicode(c,self.screen.encoding,"replace")
		if self.pos==len(self.content):
			self.content+=c
			self.pos+=1
			if self.pos>self.offset+self.w-2:
				self.scroll_right()
			else:
				self.win.addstr(c.encode(self.screen.encoding))
		else:
			self.content=self.content[:self.pos]+c+self.content[self.pos:]
			self.pos+=1
			if self.pos>self.offset+self.w-2:
				self.scroll_right()
			else:
				self.win.insstr(c.encode(self.screen.encoding))
				self.right_scroll_mark()
				self.win.move(0,self.pos-self.offset)
		self.win.refresh()

	def update(self,now=1,refresh=0):
		self.screen.lock.acquire()
		try:
			if refresh:
				if self.offset>0:
					self.left_scroll_mark()
					self.win.addstr(self.content[self.offset+1:self.offset+self.w-1])
				else:
					self.win.addstr(0,0,self.content[:self.w-1])
				self.win.clrtoeol()
				self.right_scroll_mark()
			self.win.move(0,self.pos-self.offset)
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()

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
