
import threading
import locale
import curses

from cjc import common
from cjc import commands
import buffer

import keytable

screen_commands={
	"next": ("cmd_next",
		"/next",
		"Change active window to the next one"),
	"prev": ("cmd_prev",
		"/previous",
		"Change active window to the previous one"),
	"nextbuf": ("cmd_nextbuf",
		"/nextbuf",
		"Change buffer in active window to next available"),
	"nb": "nextbuf",
	"prevbuf": ("cmd_prevbuf",
		"/nextbuf",
		"Change buffer in active window to next available"),
	"pb": "prevbuf",
	"move": ("cmd_move",
		"/move [oldnumber] number",
		"Change buffer order"), 
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
		self.input_handler=None
		self.command_handler=None
		self.escape=0
		self.lock=threading.RLock()
		lc,self.encoding=locale.getlocale()
		if self.encoding is None:
			self.encoding="us-ascii"
		keytable.activate("screen",self,input_window=self.scr)

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
		return w,h

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

	def set_input_handler(self,h):
		self.input_handler=h

	def set_command_handler(self,h):
		self.command_handler=h

	def set_resize_handler(self,h):
		self.resize_handler=h

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
				
	def cmd_next(self,args=None):
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

	def cmd_prev(self,args=None):
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
	
	def cmd_nextbuf(self,args=None):
		if args:
			args.finish()
		if not self.active_window:
			curses.beep()
			return
		buf=self.active_window.buffer
		next=None
		wasbuf=0
		for b in buffer.buffer_list:
			if b is None:
				continue
			if b is buf:
				wasbuf=1
				continue
			if b.window:
				continue
			if not wasbuf and not next:
				next=b
				continue
			if wasbuf:
				next=b
				break
		if next:
			self.active_window.set_buffer(next)
			self.active_window.update()
		else:
			curses.beep()

	def cmd_prevbuf(self,args=None):
		if args:
			args.finish()
		if args:
			args.finish()
		if not self.active_window:
			curses.beep()
			return
		buf=self.active_window.buffer
		next=None
		wasbuf=0
		lst=list(buffer.buffer_list)
		lst.reverse()
		for b in lst:
			if b is None:
				continue
			if b is buf:
				wasbuf=1
				continue
			if b.window:
				continue
			if not wasbuf and not next:
				next=b
				continue
			if wasbuf:
				next=b
				break
		if next:
			self.active_window.set_buffer(next)
			self.active_window.update()
		else:
			curses.beep()

	def cmd_move(self,args):
		num1=args.shift()
		if not num1:
			curses.beep()
			return
		num2=args.shift()
		if num2:
			oldnum,newnum=int(num1),int(num2)
		else:
			if not self.active_window or not self.active_window.buffer:
				curses.beep()
				return
			newnum=int(num1)
			oldnum=self.active_window.buffer.get_number()
		buffer.move(oldnum,newnum)

	def cursync(self):
		if self.input_handler:
			self.input_handler.cursync()

	def user_input(self,s):
		try:
			self.do_user_input(s)
		except common.non_errors:
			raise
		except:
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
		if self.command_handler and self.command_handler(cmd,args):
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

from keytable import KeyFunction,KeyBinding
ktb=keytable.KeyTable("screen",20,(
			KeyBinding("command(next)","M-^I"),
			KeyFunction("redraw-screen",Screen.redraw,"Redraw the screen","^L"),
		))
keytable.install(ktb)
