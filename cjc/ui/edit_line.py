
import curses
import curses.textpad

from widget import Widget

class EditLine(Widget):
	def __init__(self):
		Widget.__init__(self)
		self.win=None
		self.capture_rest=0
		
	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.screen.lock.acquire()
		try:
			self.win=curses.newwin(self.h,self.w,self.y,self.x)
			self.textpad=curses.textpad.Textbox(self.win)
			self.screen.set_default_key_handler(self)
		finally:
			self.screen.lock.release()

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
			self.textpad.do_command(27)
		if c in (curses.KEY_ENTER,ord("\n"),ord("\r")):
			ret=self.textpad.gather()
			self.screen.user_input(unicode(ret,self.screen.encoding,"replace"))
			self.win.clear()
			self.textpad=curses.textpad.Textbox(self.win)
			self.win.refresh()
		else:
			self.textpad.do_command(c)
		self.win.refresh()

	def update(self,now=1):
		self.screen.lock.acquire()
		try:
			self.win.cursyncup()
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()

	def cursync(self):
		self.screen.lock.acquire()
		try:
			self.win.cursyncup()
			self.win.refresh()
		finally:
			self.screen.lock.release()

