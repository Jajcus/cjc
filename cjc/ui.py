
import sys
import locale
from types import StringType,UnicodeType,IntType
import curses
import curses.textpad
import traceback

import command_args

def debug(s):
	print >>sys.stderr,"DEBUG:",s
		
def error(s):
	print >>sys.stderr,"ERROR:",s
		
def print_exception():
	traceback.print_exc(file=sys.stderr)
	
class CommandHandler:
	def __init__(self,d=None,object=None):
		self.command_info={}
		self.command_aliases={}
		if d:
			self.register_commands(d,object)

	def register_commands(self,d,object=None):
		if object is None:
			object=self
		for name,info in d.items():
			if type(info) is StringType: # alias
				self.command_aliases[name]=info
				continue
			handler,usage,descr=info
			if type(handler) is StringType:
				handler=getattr(object,handler)
			if not callable(handler):
				raise TypeError,"Bad command handler"
			self.command_info[name]=(handler,usage,descr)

	def commands(self):
		return self.command_info.keys()+self.command_aliases.keys()

	def get_command_info(self,cmd):
		if self.command_aliases.has_key(cmd):
			cmd=self.command_aliases[cmd]
		return self.command_info[cmd]

	def command(self,cmd,args):
		if self.command_aliases.has_key(cmd):
			cmd=self.command_aliases[cmd]

		if self.command_info.has_key(cmd):
			try:
				self.command_info[cmd][0](args)
			except KeyboardInterrupt:
				raise
			except command_args.CommandError,e:
				error(u"Command '%s' failed: %s" % (cmd,e))
			except StandardError,e:
				error("Comand execution failed: "+str(e))
				print_exception()
			return 1
		else:
			return 0

class Widget:
	def __init__(self):
		self.screen=None
		self.parent=None
		
	def set_parent(self,parent):
		self.parent=parent
		self.screen=parent.screen
		self.x,self.y,self.w,self.h=self.parent.place(self)

	def get_height(self):
		return None
	
	def get_width(self):
		return None
	
	def update(self,now=1):
		pass

	def redraw(self,now=1):
		self.update()

class Buffer(CommandHandler):
	buffer_list=[]
	def __init__(self,name):
		CommandHandler.__init__(self)
		self.name=name
		self.window=None
		try:
			self.buffer_list[self.buffer_list.index(None)]=self
		except ValueError:
			self.buffer_list.append(self)

	def get_number(self):
		return self.buffer_list.index(self)
		
	def format(self,width,height):
		pass

	def update(self,now=1):
		if self.window:
			self.window.update(now)

	def redraw(self,now=1):
		if self.window:
			self.window.redraw(now)

	def user_input(self,s):
		return 0

	def keypressed(self,ch,escape):
		return 0
			
def buffer_get_by_number(n):
	try:
		return Buffer.buffer_list[n]
	except IndexError:
		return None

def buffer_activity(buffer):
	pass

class TextBuffer(Buffer):
	def __init__(self,theme_manager,name,length=200):
		Buffer.__init__(self,name)
		self.theme_manager=theme_manager
		self.length=length
		self.lines=[[]]
		self.pos=None
		
	def append(self,s,attr="default"):
		if type(attr) is not IntType:
			attr=self.theme_manager.attrs[attr]
		if self.window and self.pos is None:
			self.window.write(s,attr)
		else:
			buffer_activity(self)
		newl=0
		s=s.split(u"\n")
		for l in s:
			if newl:
				self.lines.append([])
			if l:
				self.lines[-1].append((attr,l))
			newl=1
		self.lines=self.lines[-self.length:]
	
	def append_line(self,s,attr="default"):
		if type(attr) is not IntType:
			attr=self.theme_manager.attrs[attr]
		self.append(s,attr)
		self.lines.append([])
		if self.window and self.pos is None:
			self.window.write(u"\n",attr)

	def append_themed(self,format,attr,params):
		for attr,s in self.theme_manager.format_string(format,attr,params):
			self.append(s,attr)

	def write(self,s):
		self.append(s)
		self.update()

	def clear(self):
		self.lines=[[]]

	def page_up(self):
		if self.pos is None:
			self.pos=offset_back(self.window.w,self.window.h-2)
			self.window.draw_buffer()
		elif self.pos==(0,0):
			return
		else:
			self.pos=offset_back(self.window.w,self.window.h-2,pos[0],pos[1])
			self.window.draw_buffer()

	def page_down(self):
		pass

	def line_length(self,line):
		ret=0
		for attr,s in line:
			ret+=len(s)
		return ret

	def offset_back(self,width,back,l=None,c=0):
		if l is None:
			if self.lines[-1]==[]:
				l=len(self.lines)-1
			else:
				l=len(self.lines)
			if l<=0:
				return 0,0
		while back>0 and l>1:
			l-=1
			line=self.lines[l]
			ln=self.line_length(line)
			h=ln/width+1
			back-=h

		if back>0:
			return 0,0
		if back==0:
			return l,0
		return l,(-back)*width

	def offset_forward(self,width,forward,l=0,c=0):

		if l>=len(self.lines):
			l=len(self.lines)-1
			if self.lines[-1]==[]:
				l-=1
			if l>0:
				return l
			else:
				return 0

		if c>0:
			left,right=self.split_line(self.lines[l],c)
			l+=1
			ln=self.line_length(right)
			forward-=ln/width+1
		
		end=len(self.lines)
		if self.lines[-1]==[]:
			end-=1

		l-=1
		while forward>0 and l<end-1:
			l+=1
			line=self.lines[l]
			ln=self.line_length(line)
			h=ln/width+1
			forward-=h

		if forward>=0:
			return l,0

		if l>0:
			return l-1,0
		else:
			return 0,0

	def cut_line(self,line,cut):
		i=0
		left=[]
		right=[]
		for attr,s in line:
			l=len(s)
			i1=i
			i+=l
			if i<cut:
				left.append((attr,s))
			elif i1<cut and i>cut:
				left.append((attr,s[:cut-i]))
				right.append((attr,s[cut-i:]))
			else:
				right.append((attr,s))
		return left,right
			
	def format(self,width,height):
		if self.pos is None:
			l,c=self.offset_back(width,height)
		else:
			l,c=self.pos

		if c:
			x,line=self.cut_line(self.lines[l],c)
			ret=[line]
			l+=1
			height-=self.line_length(line)/width+1
		else:
			ret=[]
			
		end=len(self.lines)
		if self.lines[-1]==[]:
			end-=1

		while height>0 and l<end:
			line=self.lines[l]
			ln=self.line_length(line)
			h=ln/width+1
			ret.append(line)
			height-=h
			l+=1

		if height>=0:
			if self.lines[-1]==[]:
				ret.append([])
			return ret

		cut=(-height)*width
		ret[-1],x=self.cut_line(ret[-1],cut)
		ret.append([])
		return ret

	def page_up(self):
		if self.pos is None:
			l,c=self.offset_back(self.window.w,self.window.h-2)
		else:
			l,c=self.pos

		if (l,c)==(0,0):
			self.pos=l,c
			formatted=self.format(self.window.w,self.window.h-1)
			if len(formatted)<=self.window.h-1:
				self.pos=None
			return
			
		l1,c1=self.offset_back(self.window.w,self.window.h-2,l,c)
		self.pos=l1,c1
		self.window.draw_buffer()
		self.window.update()

	def page_down(self):
		if self.pos is None:
			return

		l,c=self.pos
			
		l1,c1=self.offset_forward(self.window.w,self.window.h-2,l,c)
		self.pos=l1,c1

		formatted=self.format(self.window.w,self.window.h-1)
		if len(formatted)<=self.window.h-1:
			self.pos=None
		
		self.window.draw_buffer()
		self.window.update()

	def keypressed(self,ch,escape):
		if escape:
			return 0
		if ch==curses.KEY_PPAGE:
			self.page_up()
			return 1
		if ch==curses.KEY_NPAGE:
			self.page_down()
			return 1
		return 0
			
class Split(Widget):
	def __init__(self,*children):
		if len(children)<1:
			raise ValueError,"At least 2 children must be given"
		Widget.__init__(self)
		self.children=children

class VerticalSplit(Split):
	def __init__(self,*children):
		apply(Split.__init__,[self]+list(children))
		self.divs=[]
		self.children_pos=[]
		self.widths=[]

	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		
		self.widths=[]
		sum_width=0
		no_widths=0
		for c in self.children:
			w=c.get_width()
			self.widths.append(w)
			if w is None:
				no_widths+=1
			else:
				sum_width+=w
				
		width_left=self.w-(len(self.children)-1)-sum_width
		if width_left<no_widths:
			raise ValueError,"Not enough space for all widgets"

		if no_widths:
			for i in range(0,len(self.widths)):
				if self.widths[i] is None:
					self.widths[i]=width_left/no_widths
					width_left-=width_left/no_widths
					no_widths-=1

		l=0
		for i in range(0,len(self.children)):
			r=l+self.widths[i]
			if i>0:
				div=curses.newwin(self.h,1,self.y,l-1)
				div.bkgdset(ord("|"),curses.A_STANDOUT)
				div.clear()
				self.divs.append(div)
			self.children_pos.append(l)
			l=r+1
			
		for c in self.children:
			c.set_parent(self)

	def place(self,child):
		for i in range(0,len(self.children)):
			if self.children[i] is child:
				x=self.children_pos[i]
				w=self.widths[i]
				return (x,self.y,w,self.h)
		raise "%r is not a child of mine" % (child,)

	def update(self,now=1):
		for div in self.divs:
			div.noutrefresh()
		for c in self.children:
			c.update(0)
		if now:
			curses.doupdate()

	def redraw(self,now=1):
		for div in self.divs:
			div.noutrefresh()
		for c in self.children:
			c.redraw(0)
		if now:
			curses.doupdate()

class HorizontalSplit(Split):
	def __init__(self,*children):
		apply(Split.__init__,[self]+list(children))
		self.heights=[]
		self.children_pos=[]
		self.heights=[]

	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		
		self.heights=[]
		sum_height=0
		no_heights=0
		for c in self.children:
			h=c.get_height()
			self.heights.append(h)
			if h is None:
				no_heights+=1
			else:
				sum_height+=h
			
		height_left=self.h-sum_height
		if height_left<no_heights:
			raise ValueError,"Not enough space for all widgets"
		
		if no_heights:
			for i in range(0,len(self.heights)):
				if self.heights[i] is None:
					self.heights[i]=height_left/no_heights
					height_left-=height_left/no_heights
					no_heights-=1

		t=0
		for i in range(0,len(self.children)):
			b=t+self.heights[i]
			self.children_pos.append(t)
			t=b

		for c in self.children:
			c.set_parent(self)

	def place(self,child):
		for i in range(0,len(self.children)):
			if self.children[i] is child:
				y=self.children_pos[i]
				h=self.heights[i]
				return (self.x,y,self.w,h)
		raise "%r is not a child of mine" % (child,)

	def update(self,now=1):
		for c in self.children:
			c.update(now)
			
	def redraw(self,now=1):
		for c in self.children:
			c.redraw(now)
			
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
		self.win=curses.newwin(self.h,self.w,self.y,self.x)
		self.win.bkgdset(ord(" "),self.theme_manager.attrs["bar"])
		
	def update(self,now=1):
		self.win.clear()
		self.win.move(0,0)
		x=0
		for attr,s in self.theme_manager.format_string(self.format,"bar",self.dict):
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
			b=buffer_get_by_number(ch-ord("0"))
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
		self.win=curses.newwin(self.h-1,self.w,self.y,self.x)
		self.win.scrollok(1)
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
		self.status_bar.update(0)
		
	def set_buffer(self,buf):
		if self.buffer:
			self.buffer.window=None
		if buf:
			if buf.window:
				buf.window.set_buffer(self.buffer)
			buf.window=self
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
		self.status_bar.update(1)

	def update(self,now=1):
		self.status_bar.update(now)
		if now:
			self.win.refresh()
		else:
			self.win.noutrefresh()

	def draw_buffer(self):
		self.win.clear()
		self.win.move(0,0)
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

	def write(self,s,attr):
		if not s:
			return
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
		self.status_bar.redraw(now)
		self.win.clear()
		if self.buffer:
			self.draw_buffer()
		if now:
			self.win.refresh()
		else:
			self.win.noutrefresh()

class EditLine(Widget):
	def __init__(self):
		Widget.__init__(self)
		self.win=None
		self.capture_rest=0
		
	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.win=curses.newwin(self.h,self.w,self.y,self.x)
		self.textpad=curses.textpad.Textbox(self.win)
		self.screen.set_default_key_handler(self)

	def get_height(self):
		return 1

	def keypressed(self,c,escape):
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
		self.win.cursyncup()
		if now:
			self.win.refresh()
		else:
			self.win.noutrefresh()

screen_commands={
	"next": ("focus_next",
		"/next",
		"Change active window to the next one"),
	"prev": ("focus_prev",
		"/previous",
		"Change active window to the previous one"),
}

class Screen(CommandHandler):
	def __init__(self,screen):
		CommandHandler.__init__(self,screen_commands)
		self.scr=screen
		self.screen=self
		self.children=[]
		self.attrs={}
		self.pairs={}
		self.next_pair=1
		self.content=None
		self.active_window=None
		self.windows=[]
		self.default_key_handler=None
		self.default_command_handler=None
		self.escape=0
		screen.keypad(1)
		screen.nodelay(1)
		lc,self.encoding=locale.getlocale()
		if self.encoding is None:
			self.encoding="us-ascii"

	def set_background(self,char,attr):
		self.scr.bkgdset(ord(char),attr)
		
	def size(self):
		h,w=self.scr.getmaxyx()
		return w-1,h-1

	def set_content(self,widget):
		self.content=widget
		widget.set_parent(self)
		
	def place(self,child):
		w,h=self.size()
		if child is self.content:
			return 0,0,w,h
		raise "%r is not a child of mine" % (child,)

	def update(self):
		if self.content:
			self.content.update(0)
		else:
			self.scr.clear()
		curses.doupdate()

	def redraw(self):
		if self.content:
			self.content.redraw(0)
		else:
			self.scr.clear()
		curses.doupdate()

	def set_default_key_handler(self,h):
		self.default_key_handler=h

	def set_default_command_handler(self,h):
		self.default_command_handler=h

	def add_window(self,win):
		if not self.windows:
			win.set_active(1)
			self.active_window=win
		self.windows.append(win)
		curses.doupdate()

	def focus_window(self,win):
		if not win or win is self.active_window:
			return
				
		self.active_window.set_active(0)
		win.set_active(1)
		self.active_window=win
		curses.doupdate()
				
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
				self.process_key(27)
				return 1
			else:
				self.escape=1
				return 1
		self.process_key(ch)
		self.escape=0

	def user_input(self,s):
		try:
			self.do_user_input(s)
		except KeyboardInterrupt:
			pass
		except StandardError:
			print_exception()

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
		args=command_args.CommandArgs(args)
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

def init():
	screen=curses.initscr()
	curses.start_color()
	curses.cbreak()
	curses.meta(1)
	curses.noecho()
	curses.nonl()
	return Screen(screen)

def deinit():
	curses.endwin()
