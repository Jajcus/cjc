
import curses

from widget import Widget

class StatusBar(Widget):
	def __init__(self,theme_manager,format,dict):
		Widget.__init__(self)
		self.theme_manager=theme_manager
		self.format=format
		self.dict=dict

	def get_height(self):
		return 1

	def get_dict(self):
		return self.dict

	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.screen.lock.acquire()
		try:
			self.win=curses.newwin(self.h,self.w,self.y,self.x)
			self.win.leaveok(1)
			self.win.bkgdset(ord(" "),self.theme_manager.attrs["bar"])
		finally:
			self.screen.lock.release()
		
	def update(self,now=1):
		self.screen.lock.acquire()
		try:
			self.win.clear()
			self.win.move(0,0)
			x=0
			for attr,s in self.theme_manager.format_string(self.format,self.dict):
				x+=len(s)
				if x>=self.w:
					s=s[:x-self.w]
					self.win.addstr(s,attr)
					break
				self.win.addstr(s,attr)
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
			self.screen.cursync()
		finally:
			self.screen.lock.release()

