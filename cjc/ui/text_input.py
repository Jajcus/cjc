
import curses
import curses.textpad
import string

from cjc import common
from input_widget import InputWidget

class TextInput(InputWidget):
	def __init__(self,abortable,required,default=u"",history_len=0):
		InputWidget.__init__(self,abortable,required)
		self.capture_rest=0
		self.content=u""
		self.pos=0
		self.offset=0
		self.history_len=history_len
		self.history=[]
		self.history_pos=0
		self.saved_content=None
		
	def keypressed(self,c,escape):
		self.screen.lock.acquire()
		try:
			return self._keypressed(c,escape)
		finally:
			self.screen.lock.release()
		
	def _keypressed(self,c,escape):
		if c==27:
			if self.abortable:
				self.parent.abort_handler()
				return
			else:
				curses.beep()
				return
		elif c==curses.KEY_ENTER:
			return self.key_enter()
		elif c==curses.KEY_HOME:
			return self.key_home()
		elif c==curses.KEY_END:
			return self.key_end()
		elif c==curses.KEY_LEFT:
			return self.key_left()
		elif c==curses.KEY_RIGHT:
			return self.key_right()
		elif c==curses.KEY_UP:
			return self.key_up()
		elif c==curses.KEY_DOWN:
			return self.key_down()
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
		elif c=="\x01": # ^A
			self.key_home()
		elif c=="\x02": # ^B
			self.key_left()
		elif c=="\x04": # ^D
			self.key_del()
		elif c=="\x05": # ^E
			self.key_end()
		elif c=="\x06": # ^F
			self.key_right()
		elif c=="\b":   # ^H
			self.key_bs()
		elif c=="\x0b": # ^K
			self.key_kill()
		elif c=="\x0e": # ^N
			self.key_down()
		elif c=="\x10": # ^P
			self.key_up()
		elif c=="\x17": # ^W
			self.key_wrubout()
		elif c=="\x15": # ^U
			self.key_uclean()
		elif c=="\x7f":
			self.key_del()
		elif c in self.printable:
			self.key_char(c)
		else:
			curses.beep()

	def left_scroll_mark(self):
		if self.offset>0:
			self.win.addch(0,0,curses.ACS_LARROW,self.theme_manager.attrs["scroll_mark"])
		
	def right_scroll_mark(self):
		if len(self.content)-self.offset>=self.w:
			self.win.insch(0,self.w-1,curses.ACS_RARROW,self.theme_manager.attrs["scroll_mark"])

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
		s=self.content[self.offset+self.w-2]
		self.win.addstr(0,self.w-2,s.encode(self.screen.encoding,"replace"))
		if len(self.content)-self.offset==self.w-1:
			self.win.clrtoeol()
		else:
			self.right_scroll_mark()
		self.win.move(0,self.pos-self.offset)

	def key_enter(self):
		if self.required and not self.content:
			return curses.beep()
		if self.history_len:
			if self.history_pos:
				if self.content==self.history[-self.history_pos]:
					del self.history[-self.history_pos]
				self.history_pos=0
			self.history.append(self.content)
			self.history=self.history[-self.history_len:]
		ans=self.content
		self.content=u""
		self.saved_content=None
		self.pos=0
		self.offset=0
		self.win.move(0,0)
		self.win.clrtoeol()
		self.win.refresh()
		self.parent.input_handler(ans)

	def key_kill(self):
		if not self.content:
			return curses.beep()
		self.content=u""
		self.saved_content=None
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

 	def key_uclean(self):
 		if self.pos==0:
			curses.beep()
			return
		self.content=self.content[self.pos:].rstrip()
                self.pos=0
		self.redraw()

	def key_wrubout(self):
		if self.pos==0:
			curses.beep()
			return
		s=self.content[:self.pos].rstrip()
		if self.pos>len(s):
			self.content=s+self.content[self.pos:]
			self.pos=len(s)
		
		p=self.content.rfind(" ",0,self.pos)
		if p<=0:
			self.content=self.content[self.pos:]
		else:
			self.content=self.content[:p+1]+self.content[self.pos:]
			self.pos=p+1
		self.redraw()

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

	def key_up(self):
		if not self.history_len or self.history_pos>=len(self.history):
			curses.beep()
			return
		if self.history_pos==0:
			self.saved_content=self.content
		self.history_pos+=1
		self.content=self.history[-self.history_pos]
		self.pos=len(self.content)
		self.offset=0
		if self.pos>self.offset+self.w-2:
			self.scroll_right()
		else:
			self.redraw()

	def key_down(self):
		if not self.history_len or self.history_pos<=0:
			curses.beep()
			return
		self.history_pos-=1
		if self.history_pos==0:
			if self.saved_content:
				self.content=self.saved_content
			else:
				self.content=u""
		else:
			self.content=self.history[-self.history_pos]
			self.pos=len(self.content)
		self.pos=len(self.content)
		self.offset=0
		if self.pos>self.offset+self.w-2:
			self.scroll_right()
		else:
			self.redraw()

	def update(self,now=1,refresh=0):
		if not self.screen:
			return
		if self.pos>len(self.content):
			self.pos=len(self.content)
		self.screen.lock.acquire()
		try:
			if self.pos<0 or (self.offset and self.pos<=self.offset):
				if self.offset:
					self.pos=self.offset+1
				else:
					self.pos=0
			elif self.pos>=self.offset+self.w-1:
				self.pos=self.offset+self.w-2
			if refresh:
				if self.offset>0:
					self.left_scroll_mark()
					s=self.content[self.offset+1:self.offset+self.w-1]
					self.win.addstr(s.encode(self.screen.encoding,"replace"))
				else:
					s=self.content[:self.w-1]
					self.win.addstr(0,0,s.encode(self.screen.encoding,"replace"))
				self.win.clrtoeol()
				self.right_scroll_mark()
			self.win.move(0,self.pos-self.offset)
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()
