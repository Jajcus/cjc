
import threading
import locale
import curses

from cjc import common
from cjc import commands
import buffer

screen_commands={
	"next": ("focus_next",
		"/next",
		"Change active window to the next one"),
	"prev": ("focus_prev",
		"/previous",
		"Change active window to the previous one"),
}

class Screen(commands.CommandHandler):
	def __init__(self,screen):
		commands.CommandHandler.__init__(self,screen_commands)
		self.scr=screen
		self.screen=self
		self.attrs={}
		self.pairs={}
		self.next_pair=1
		self.content=None
		self.active_window=None
		self.windows=[]
		self.default_key_handler=None
		self.default_command_handler=None
		self.escape=0
		self.lock=threading.RLock()
		lc,self.encoding=locale.getlocale()
		if self.encoding is None:
			self.encoding="us-ascii"

	def set_background(self,char,attr):
		self.lock.acquire()
		try:
			self.scr.bkgdset(ord(char),attr)
		finally:
			self.lock.release()
		
	def size(self):
		self.lock.acquire()
		try:
			h,w=self.scr.getmaxyx()
		finally:
			self.lock.release()
		return w-1,h-1

	def set_content(self,widget):
		self.content=widget
		self.windows=[]
		widget.set_parent(self)
		for b in buffer.buffer_list:
			if b is None:
				continue
			if b.window and b.window not in self.windows:
				b.set_window(None)
		
	def place(self,child):
		w,h=self.size()
		if child is self.content:
			return 0,0,w,h
		raise "%r is not a child of mine" % (child,)

	def update(self,now=0,redraw=0):
		self.lock.acquire()
		try:
			if redraw:
				self.scr.clear()
				self.scr.noutrefresh()
			if self.content:
				self.content.update(0,redraw)
			elif not redraw:
				self.scr.erase()
			if now:
				curses.doupdate()
				self.screen.cursync()
		finally:
			self.lock.release()

	def redraw(self):
		self.update(1,1)

	def set_default_key_handler(self,h):
		self.default_key_handler=h
		h.win.timeout(100)

	def set_default_command_handler(self,h):
		self.default_command_handler=h

	def add_window(self,win):
		if not self.windows:
			win.set_active(1)
			self.active_window=win
		self.windows.append(win)
		self.lock.acquire()
		try:
			curses.doupdate()
		finally:
			self.lock.release()

	def focus_window(self,win):
		if not win or win is self.active_window:
			return
				
		self.active_window.set_active(0)
		win.set_active(1)
		self.active_window=win
		self.lock.acquire()
		try:
			curses.doupdate()
		finally:
			self.lock.release()
				
	def focus_next(self,args=None):
		if len(self.windows)<=1:
			return
			
		for i in range(0,len(self.windows)):
			if self.windows[i] is self.active_window:
				if i==len(self.windows)-1:
					win=self.windows[0]
				else:
					win=self.windows[i+1]
				self.focus_window(win)
				break

	def focus_prev(self,args=None):
		if len(self.windows)<=1:
			return
			
		for i in range(0,len(self.windows)):
			if self.windows[i] is self.active_window:
				if i==0:
					win=self.windows[-1]
				else:
					win=self.windows[i-1]
				self.focus_window(win)
				break
	
	def cursync(self):
		if self.default_key_handler:
			self.default_key_handler.cursync()

	def process_key(self,ch):
		if self.active_window:
			if self.active_window.keypressed(ch,self.escape):
				return
				
		if self.escape and ch==ord("\t"):
			self.focus_next()
			return
		
		if self.default_key_handler:
			if self.default_key_handler.keypressed(ch,self.escape):
				return

	def keypressed(self):
		ch=self.default_key_handler.win.getch()
		if ch==-1:
			return 0
		if ch==27:
			if self.escape:
				self.escape=0
				try:
					self.process_key(27)
				except KeyboardInterrupt:
					pass
				except common.standard_errors,e:
					common.print_exception()
				return 1
			else:
				self.escape=1
				return 1
		try:
			self.process_key(ch)
		except KeyboardInterrupt:
			pass
		except common.standard_errors,e:
			common.print_exception()
		self.escape=0
		return 1

	def user_input(self,s):
		try:
			self.do_user_input(s)
		except KeyboardInterrupt:
			pass
		except common.standard_errors,e:
			common.print_exception()

	def do_user_input(self,s):
		if not s.startswith(u"/"):
			if self.active_window and self.active_window.user_input(s):
				return
			return
		cmd=s[1:]	
		if not cmd:
			return
		s=cmd.split(None,1)
		if len(s)>1:
			cmd,args=s
		else:
			cmd,args=s[0],None
		args=commands.CommandArgs(args)
		cmd=cmd.lower()
		if self.active_window and self.active_window.command(cmd,args):
			return
		if self.command(cmd,args):
			return
		if self.default_command_handler and self.default_command_handler.command(cmd,args):
			return
			
	def display_buffer(self,buffer):
		if buffer.window:
			return buffer.window
		if self.active_window and not self.active_window.locked:
			self.active_window.set_buffer(buffer)
			self.active_window.update()
			return self.active_window
		for w in self.windows:
			if not w.locked:
				w.set_buffer(buffer)
				w.update()
				return w
		return None

