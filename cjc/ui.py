
import sys
import locale
from types import StringType,UnicodeType
import curses
import curses.textpad

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
			print >>sys.stderr,"Child: %i offset: %i height: %i\r" % (i,t,self.heights[i])
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
	def __init__(self,items=[]):
		Widget.__init__(self)
		self.items=items

	def get_height(self):
		return 1

	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.win=curses.newwin(self.h,self.w,self.y,self.x)
		self.win.bkgdset(ord(" "),self.screen.attrs["bar"])
		
	def update(self,now=1):
		self.win.clear()
		self.win.move(0,0)
		for i in self.items:
			if type(i) is UnicodeType:
				s=i.encode(self.screen.encoding,"replace")
			else:
				s=str(i)
			self.win.addstr(s)
		if now:
			self.win.refresh()
		else:
			self.win.noutrefresh()

class Window(Widget):
	def __init__(self,status_bar_items):
		Widget.__init__(self)
		self.buffer=None
		self.status_bar=StatusBar(status_bar_items)
		self.win=None

	def place(self,child):
		if child is not self.status_bar:
			raise ValueError,"%r is not a child of mine" % (child,)
		return (self.x,self.y+self.h-1,self.w,1)

	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.set_buffer(self.buffer)
		self.status_bar.set_parent(self)
		self.win=curses.newwin(self.h-1,self.w,self.y,self.x)
		self.win.scrollok(1)
		if self.buffer:
			self.draw_buffer()
		
	def set_buffer(self,buf):
		if self.buffer:
			self.buffer.window=None
		self.buffer=buf
		if buf:
			buf.window=self
		if self.win:
			self.draw_buffer()

	def update(self,now=1):
		self.status_bar.update(now)
		if now:
			self.win.refresh()
		else:
			self.win.noutrefresh()

	def draw_buffer(self):
		self.win.move(0,0)
		for line in self.buffer.format(0,self.w,self.h-2):
			for attr,s in line:
				s=s.encode(self.screen.encoding,"replace")
				attr=self.screen.attrs[attr]
				self.win.addstr(s,attr)
			self.win.addstr("\n")

	def write(self,s,attr):
		s=s.encode(self.screen.encoding,"replace")
		attr=self.screen.attrs[attr]
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
	def __init__(self,input_handler):
		Widget.__init__(self)
		self.input_handler=input_handler
		self.win=None
		
	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		print >>sys.stderr,`(self.h,self.w,self.y,self.x)`
		self.win=curses.newwin(self.h,self.w,self.y,self.x)
		self.textpad=curses.textpad.Textbox(self.win)

	def get_height(self):
		return 1

	def process(self):
		c=self.win.getch()
		if c in (curses.KEY_ENTER,ord("\n"),ord("\r")):
			ret=self.textpad.gather()
			self.input_handler(unicode(ret,self.screen.encoding,"replace"))
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

class Screen:
	def __init__(self,screen):
		self.scr=screen
		self.screen=self
		self.children=[]
		self.attrs={}
		self.pairs={}
		self.next_pair=1
		self.content=None
		lc,self.encoding=locale.getlocale()
		if self.encoding is None:
			self.encoding="us-ascii"
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
		self.make_attr("bar",
				curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_STANDOUT,
				curses.A_STANDOUT)
		self.make_attr("available",
				curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_NORMAL,
				curses.A_NORMAL)
		self.make_attr("unavailable",
				curses.COLOR_RED,curses.COLOR_BLACK,curses.A_NORMAL,
				curses.A_NORMAL)
		self.scr.bkgdset(ord(" "),self.attrs["default"])
		
	def size(self):
		h,w=self.scr.getmaxyx()
		return w-1,h-1

	def make_attr(self,name,fg,bg,attr,fallback):
		if not curses.has_colors():
			self.attrs[name]=fallback
			return
		if self.pairs.has_key((fg,bg)):
			pair=self.pair[fg,bg]
		elif self.next_pair>curses.COLOR_PAIRS:
			self.attrs[name]=fallback
			return
		else:
			curses.init_pair(self.next_pair,fg,bg)
			pair=self.next_pair
			self.next_pair+=1
		attr|=curses.color_pair(pair)
		self.attrs[name]=attr

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

def init():
	screen=curses.initscr()
	curses.start_color()
	curses.cbreak()
	curses.noecho()
	curses.nonl()
	screen.keypad(1)
	return Screen(screen)

def deinit():
	curses.endwin()
