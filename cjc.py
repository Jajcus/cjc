#!/usr/bin/python -u

import libxml2
import time
import traceback
import sys
import curses
import curses.textpad
import select
import string
from types import StringType,UnicodeType

import pyxmpp

encoding="iso-8859-2"

class Exit(StandardError):
	pass

class Buffer:
	def __init__(self,w,h):
		self.h,self.w=h,w
		self.pad=curses.newpad(h,w)
		self.pad.scrollok(1)
		self.window=None

	def append(self,s,a=None):
		if type(s) is UnicodeType:
			s=s.encode(encoding,"replace")
		if a is not None:
			self.pad.addstr(s,a)
		else:
			self.pad.addstr(s)

	def append_line(self,s,a=None):
		if type(s) is UnicodeType:
			s=s.encode(encoding,"replace")
		if a is not None:
			self.pad.addstr(s+"\n",a)
		else:
			self.pad.addstr(s+"\n")

	def write(self,s):
		self.pad.addstr(s)
		self.update()

	def get_pos(self):
		y,x=self.pad.getyx()
		return y

	def update(self,now=1):
		win=self.window
		if not win:
			return
		p=self.get_pos()
		py=p-win.h+1
		if py<0:
			py=0
		px=self.w-win.w
		if px<0:
			px=0
		if now:
			self.pad.refresh(py,px,win.y,win.x,win.h-1,win.w-1)
		else:
			self.pad.noutrefresh(py,px,win.y,win.x,win.h-1,win.w-1)

class StatusBar:
	def __init__(self,x,y,l,items=[]):
		self.x,self.y,self.l=x,y,l
		self.items=items
		self.win=curses.newwin(1,l,y,x)
		self.win.bkgdset(ord(" "),curses.A_STANDOUT)
		
	def update(self,now=1):
		self.win.clear()
		self.win.move(0,0)
		for i in self.items:
			if type(i) is UnicodeType:
				s=i.encode(encoding,"replace")
			else:
				s=str(i)
			self.win.addstr(s)
		if now:
			self.win.refresh()
		else:
			self.win.noutrefresh()

class Window:
	def __init__(self,x,y,w,h,status_bar_items):
		self.x,self.y,self.w,self.h=x,y,w,h
		self.buffer=None
		self.set_buffer(None)
		self.status_bar=StatusBar(x,y+h-1,w,status_bar_items)
		
	def set_buffer(self,buf):
		if self.buffer:
			self.buffer.window=None
		if buf:
			self.buffer=buf
			self.win=None
			self.buffer.window=self
		else:
			self.buffer=None
			self.win=curses.newwin(self.h-1,self.w,self.y,self.x)

	def update(self,now=1):
		self.status_bar.update(now)
		if self.buffer:
			self.buffer.update()
		elif self.win:
			self.win.clear()
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()

class EditLine:
	def __init__(self,x,y,l,input_handler):
		self.x,self.y,self.l=x,y,l
		self.win=curses.newwin(1,l,y,x)
		self.textpad=curses.textpad.Textbox(self.win)
		self.input_handler=input_handler

	def process(self):
		c=self.win.getch()
		if c in (curses.KEY_ENTER,ord("\n"),ord("\r")):
			ret=self.textpad.gather()
			self.input_handler(unicode(ret,encoding,"replace"))
			self.win.clear()
			self.textpad=curses.textpad.Textbox(self.win)
			self.win.refresh()
		else:
			self.textpad.do_command(c)
		self.win.refresh()

	def update(self,now=1):
		self.win.cursyncup()
		if now:
			self.win.refresh()
		else:
			self.win.noutrefresh()
	
class Application(pyxmpp.Client):
	def __init__(self):
		pyxmpp.Client.__init__(self)
		self.commands={
			"exit": self.cmd_quit,
			"quit": self.cmd_quit,
			"set": self.cmd_set,
			"connect": self.cmd_connect,
			"disconnect": self.cmd_disconnect,
			"save": self.cmd_save,
			"load": self.cmd_load,
		}
		self.attrs={}

	def make_attr(self,name,fg,bg,attr,fallback):
		if not curses.has_colors() or self.next_pair>curses.COLOR_PAIRS:
			self.attrs[name]=fallback
			return
		curses.init_pair(self.next_pair,fg,bg)
		attr|=curses.color_pair(self.next_pair)
		self.next_pair+=1
		self.attrs[name]=attr

	def run(self,scr):
		self.next_pair=1
		self.make_attr("default",
				curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL,
				curses.A_NORMAL)
		self.make_attr("error",
				curses.COLOR_RED,curses.COLOR_BLACK,curses.A_BOLD,
				curses.A_STANDOUT)
		self.make_attr("warning",
				curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD,
				curses.A_UNDERLINE)
		self.make_attr("info",
				curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_NORMAL,
				curses.A_NORMAL)
		self.make_attr("debug",
				curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL,
				curses.A_DIM)
		
		scr.bkgdset(ord(" "),self.attrs["default"])
		h,w=scr.getmaxyx()
		self.top_bar=StatusBar(0,0,w,["CJC"])
		self.status_window=Window(0,1,w,10,["Status"])
		self.main_window=Window(0,12,w,h-13,["Main"])
		self.command_line=EditLine(0,h-1,w,self.user_input)
		
		self.status_buf=Buffer(w,100)
		self.status_buf.append_line("Status:")
		self.status_window.set_buffer(self.status_buf)

		self.cmd_load()
		self.redraw()

		try:
			self.loop(1)
		except Exit:
			pass

	def cmd_quit(self,args):
		raise Exit

	def cmd_connect(self,args):
		if not self.jid:
			self.error("Can't connect - jid not given")
			return
		if None in (self.jid.node,self.jid.resource):
			self.error("Can't connect - jid is not full")
			return
		if not self.password:
			self.error("Can't connect - password not given")
			return
		self.info("Connecting...")
		self.connect()
	
	def cmd_disconnect(self,args):
		self.disconnect()
	
	def cmd_set(self,args):
		if not args:
			return
		var,val=args.split(None,1)
		if var.find("=")>0:
			var,val=args.split(" ",1)
		if var=="jid":
			self.jid=pyxmpp.JID(val)
		elif var=="server":
			self.server=str(val)
		elif var=="password":
			self.password=val
		elif var=="port":
			self.port=int(val)
		elif var=="auth_methods":
			self.auth_methods=val.split()
		elif var=="node":
			if not self.jid:
				if self.server:
					self.jid=pyxmpp.JID(val,self.server,"CJC")
				else:
					self.jid=pyxmpp.JID(val,"unknown","CJC")
			else:
				self.jid.set_node(val)
		elif var=="domain":
			if not self.jid:
				self.jid=pyxmpp.JID("unknown",val,"CJC")
			else:
				self.jid.set_domain(val)
		elif var=="resource":
			if not self.jid:
				self.jid=pyxmpp.JID("unknown",self.server,val)
			else:
				self.jid.set_resource(val)
		self.redraw()

	def cmd_save(self,filename=".cjcrc"):
		try:
			f=file(".cjcrc","w")
		except IOError,e:
			self.status_buf.append("Couldn't open config file: "+str(e))
			return
		
		if self.jid:
			print >>f,"jid",self.jid.as_string()
		if self.server:
			print >>f,"server",self.server
		if self.password:
			print >>f,"password",self.password.encode("utf-8")
		if self.port:
			print >>f,"port",self.port
		if self.auth_methods:
			print >>f,"auth_methods",string.join(self.auth_methods)
			

	def cmd_load(self,filename=".cjcrc"):
		try:
			f=file(".cjcrc","r")
		except IOError,e:
			self.warning("Couldn't open config file: "+str(e))
			return
		
		for l in f.readlines():
			if not l:
				continue
			l=l.split("#",1)[0].strip()
			if not l:
				continue
			try:
				self.cmd_set(unicode(l,"utf-8"))
			except (ValueError,UnicodeError):
				self.warning(
					"Invalid config directive %r ignored" % (l,))
		f.close()
	
	def command(self,cmd):
		if not cmd:
			return
		s=cmd.split(None,1)
		if len(s)>1:
			cmd,args=s
		else:
			cmd,args=s[0],None
		cmd=cmd.lower()
		if self.commands.has_key(cmd):
			try:
				self.commands[cmd](args)
			except (KeyboardInterrupt,SystemExit,Exit),e:
				raise
			except Exception,e:
				self.error("Comand execution failed: "+str(e))
				traceback.print_exc(file=self.status_buf)
		else:
			self.error("Unknown command: "+cmd)

	def user_input(self,s):
		if s.startswith(u"/"):
			self.command(s[1:])
		else:
			self.status_buf.append_line(s)
			self.status_buf.update()

	def loop(self,timeout):
		while 1:
			fdlist=[sys.stdin.fileno()]
			if self.stream and self.stream.socket:
				fdlist.append(self.stream.socket)
			id,od,ed=select.select(fdlist,[],fdlist,timeout)
			if sys.stdin.fileno() in id:
				self.command_line.process()
			if self.stream and self.stream.socket in id:
				self.stream.process()
			else:
				self.idle()
				
	def redraw(self):
		self.top_bar.update(0)
		self.status_window.update(0)
		self.main_window.update(0)
		self.command_line.update(0)
		curses.doupdate()

	def idle(self):
		pyxmpp.Client.idle(self)
				
	def error(self,s):
		self.status_buf.append_line(s,self.attrs["error"])
		self.status_buf.update(1)
		
	def warning(self,s):
		self.status_buf.append_line(s,self.attrs["warning"])
		self.status_buf.update(1)
		
	def info(self,s):
		self.status_buf.append_line(s,self.attrs["info"])
		self.status_buf.update(1)

	def debug(self,s):
		self.status_buf.append_line(s,self.attrs["debug"])
		self.status_buf.update(1)

app=Application()

try:
	screen=curses.initscr()
	curses.start_color()
	curses.cbreak()
	curses.noecho()
	curses.nonl()
	screen.keypad(1)
	app.run(screen)
finally:
	curses.endwin()	
