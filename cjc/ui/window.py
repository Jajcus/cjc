import curses

import buffer
from widget import Widget
from status_bar import StatusBar

class Window(Widget):
	def __init__(self,theme_manager,title,lock=0):
		Widget.__init__(self)
		self.buffer=None
		if lock:
			l="!"
		else:
			l=""
		self.status_bar=StatusBar(theme_manager,"window_status",
						{"active":"",
						 "winname":title,
						 "bufname":"",
						 "bufnum":"",
						 "locked":l})
		self.win=None
		self.newline=0
		self.locked=lock
		self.active=0

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
		self.status_bar.set_parent(self)
		self.screen.lock.acquire()
		try:
			self.win=curses.newwin(self.h-1,self.w,self.y,self.x)
			self.win.scrollok(1)
			self.win.leaveok(1)
		finally:
			self.screen.lock.release()
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
			buf.set_window(self)
		self.buffer=buf
		self.newline=0
		if self.win:
			self.draw_buffer()
		d=self.status_bar.get_dict()
		if buf:
			d["bufname"]=buf.name
			d["bufnum"]=buf.get_number()
		else:
			d["bufname"]=u""
		if self.screen:
			self.status_bar.update(1)

	def update(self,now=1):
		self.status_bar.update(now)
		self.screen.lock.acquire()
		try:
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
			self.screen.cursync()
		finally:
			self.screen.lock.release()

	def draw_buffer(self):
		self.screen.lock.acquire()
		try:
			self.win.clear()
			self.win.move(0,0)
			if not self.buffer:
				return
			lines=self.buffer.format(self.w,self.h-1)
			if not lines:
				return
			if lines[-1]==[]:
				lines=lines[:-1]
				has_eol=1
			else:
				has_eol=0
			self.newline=0
			for line in lines:
				if self.newline:
					self.win.addstr("\n")
				for attr,s in line:
					s=s.encode(self.screen.encoding,"replace")
					self.win.addstr(s,attr)
				self.newline=1
			if not has_eol:
				self.newline=0
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
		
	def _write(self,s,attr):
		y,x=self.win.getyx()
		if self.newline:
			if y==self.h-2:
				self.win.scroll(1)
				self.win.move(y,0)
			else:
				y+=1
				self.win.addstr("\n")
			self.newline=0
			x=0
			
		if s[-1]==u"\n":
			s=s[:-1]
			self.newline=1
			
		paras=s.split("\n")
		if len(paras[0])+x>self.w:
			s=paras[0][:self.w-x]
			s=s.encode(self.screen.encoding,"replace")
			self.win.addstr(s,attr)
			paras[0]=paras[0][self.w-x:]
		else:
			s=paras[0][:self.w-x]
			s=s.encode(self.screen.encoding,"replace")
			self.win.addstr(s,attr)
			if len(paras)==1:
				return

		y+=1
		lines=[]
		while len(paras):
			if len(paras[0])>self.w:
				lines.append(paras[0][:self.w])
				paras[0]=paras[0][self.w:]
			else:
				lines.append(paras.pop(0))
		
		for s in lines:	
			if y==self.h-2:
				self.win.scroll(1)
			else:
				y+=1
			s=s.encode(self.screen.encoding,"replace")
			self.win.addstr(s,attr)
	
	def redraw(self,now=1):
		self.screen.lock.acquire()
		try:
			self.status_bar.redraw(now)
			self.win.clear()
			if self.buffer:
				self.draw_buffer()
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()

