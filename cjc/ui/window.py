import curses
import re

import buffer
from widget import Widget
from status_bar import StatusBar
from cjc import common

control_re=re.compile("[\x00-\x1f\x7f]",re.UNICODE)

class Window(Widget):
	def __init__(self,theme_manager,title,lock=0):
		Widget.__init__(self)
		self.buffer=None
		self.title=title
		self.win=None
		self.locked=lock
		self.active=0
		d=self.get_status_dict()
		self.status_bar=StatusBar(theme_manager,"window_status",d)

	def get_status_dict(self):
		if self.locked:
			l="!"
		else:
			l=""
		if self.active:
			a="*"
		else:
			a=""
		if self.buffer:
			bnam=self.buffer.name
			bnum=self.buffer.get_number()
		else:
			bnam=""
			bnum=""
			
		return {"active":a,"winname":self.title,"locked":l,
			"bufname":bnam,"bufnum":bnum,"bufcol":"","bufrow":""}

	def keypressed(self,ch,escape):
		if self.buffer and self.buffer.keypressed(ch,escape):
			return 1
		if self.locked:
			return 0
		if escape and ch in range(ord("0"),ord("9")+1):
			b=buffer.get_by_number(ch-ord("0"))
			if b is None:
				return 1
			old=b.window
			if old and old.locked:
				return 1
			self.set_buffer(b)
			self.update()
			if old:
				old.update()
			return 1
		return 0

	def description(self):
		if self.buffer: 
			return self.buffer.name
		else:
			return "Empty window"

	def commands(self):
		if self.buffer:
			return self.buffer.commands()
		else:
			return []
		
	def get_command_info(self,cmd):
		if self.buffer:
			return self.buffer.get_command_info(cmd)
		raise KeyError,cmd

	def command(self,cmd,args):
		if self.buffer:
			return self.buffer.command(cmd,args)
		else:
			return 0

	def user_input(self,s):
		if self.buffer:
			return self.buffer.user_input(s)
		return 0

	def place(self,child):
		if child is not self.status_bar:
			raise ValueError,"%r is not a child of mine" % (child,)
		return (self.x,self.y+self.h-1,self.w,1)

	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.iw=self.w
		self.ih=self.h-1
		self.screen.lock.acquire()
		try:
			self.win=curses.newwin(self.ih,self.iw,self.y,self.x)
			self.win.idlok(1)
			self.win.scrollok(1)
			self.win.leaveok(1)
		finally:
			self.screen.lock.release()
		self.status_bar.set_parent(self)
		if self.buffer:
			self.draw_buffer()
			
		if self not in self.screen.windows:
			self.screen.add_window(self)

	def set_active(self,yes):
		if yes:
			self.active=1
			a="*"
		else:
			self.active=0
			a=""
		d=self.status_bar.get_dict()
		d["active"]=a
		if self.screen:
			self.status_bar.update(0)
		
	def set_buffer(self,buf):
		if self.buffer:
			self.buffer.set_window(None)
		if buf:
			if buf.window:
				buf.window.set_buffer(self.buffer)
		self.buffer=buf
		d=self.get_status_dict()
		if buf:
			buf.set_window(self)
		if self.win:
			self.draw_buffer()
		if self.screen:
			self.status_bar.update(1)

	def update_status(self,d,now=1):
		self.status_bar.get_dict().update(d)
		self.status_bar.update(now)

	def draw_buffer(self):
		self.screen.lock.acquire()
		try:
			self.win.erase()
			self.win.move(0,0)
			if not self.buffer:
				return
			lines=self.buffer.format(self.iw,self.ih)
			if not lines:
				return
			eol=0
			common.debug("lines: "+`lines`)	
			for line in lines:
				if eol:
					self.win.addstr("\n")
				x=0
				for attr,s in line:
					x+=len(s)
					if x>self.iw:
						s=s[:-(x-self.iw)]
					s=s.encode(self.screen.encoding,"replace")
					self.win.addstr(s,attr)
					if x>=self.iw:
						break
				if x<self.iw:
					eol=1
				else:
					eol=0
		finally:
			self.screen.lock.release()

	def nl(self):
		self.screen.lock.acquire()
		try:
			self.win.addstr("\n")
		finally:
			self.screen.lock.release()

	def write(self,s,attr):
		if not s:
			return
		self.screen.lock.acquire()
		try:
			return self._write(s,attr)
		finally:
			self.screen.lock.release()
			
	def write_at(self,x,y,s,attr):
		if not s:
			return
		self.screen.lock.acquire()
		try:
			self.win.move(y,x)
			return self._write(s,attr)
		finally:
			self.screen.lock.release()
		
	def _write(self,s,attr):
		y,x=self.win.getyx()
		s=control_re.sub(u"\ufffd",s)
		
		if len(s)+x>self.iw:
			s=s[:self.iw-x]
		s=s.encode(self.screen.encoding,"replace")
		self.win.addstr(s,attr)
	
	def update(self,now=1,redraw=0):
		self.status_bar.update(now)
		self.screen.lock.acquire()
		try:
			if redraw:
				self.win.erase()
				if self.buffer:
					self.draw_buffer()
			self.status_bar.update(now,redraw)
			if now:
				self.win.refresh()
				self.screen.cursync()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()
