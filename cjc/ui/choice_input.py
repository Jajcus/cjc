
import curses
import curses.textpad
import string
from types import StringType,UnicodeType,IntType,XRangeType

from widget import Widget
from cjc import common


class ChoiceInput:
	def __init__(self,parent,abortable,default,choice):
		from input import InputError
		self.single_choice=[]
		self.string_choice=[]
		self.range_choice=[]
		prompt=[]
		for c in choice:
			if type(c) in (StringType,UnicodeType):
				if len(c)==1:
					self.single_choice.append(c)
				else:
					self.string_choice.append(c)
				if c==default:
					prompt.append(c.upper())
				else:
					prompt.append(c)
			elif type(c) is IntType:
				self.range_choice.append(xrange(c,c+1))
				prompt.append(str(c))
			elif type(c) is XRangeType:
				self.range_choice.append(c)
				p="%i-%i" % (c[0],c[-1])
				if default in c:
					p+="(%i)" % (default,)
				prompt.append(p)
			else:
				raise InputError,"Bad choice value: %r" % (c,)
		self.prompt=u"[%s]: " % (string.join(prompt,"/"))
		self.parent=parent
		self.abortable=abortable
		self.win=None
		self.content=u""
		self.default=default
		self.pos=0
		self.theme_manager=parent.theme_manager
		
	def set_window(self,win):
		if win:
			self.win=win
			self.h,self.w=win.getmaxyx()
			self.screen=self.parent.screen
			self.printable=string.digits+string.letters+string.punctuation+" "
			self.win.keypad(1)
			self.win.leaveok(0)
			self.win.move(0,0)
			s=self.prompt.encode(self.screen.encoding,"replace")
			self.win.addstr(s)
		else:
			self.win=None

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
		elif c==curses.KEY_BACKSPACE:
			return self.key_bs()
		elif c>255 or c<0:
			curses.beep()
			return
		c=chr(c)
		if c in ("\n\r"):
			self.key_enter()
		elif c=="\b":
			self.key_bs()
		elif c in self.printable:
			self.key_char(c)
		else:
			curses.beep()

	def key_enter(self):
		if self.content:
			ans=self.content
		else:
			ans=self.default
		ival=None
		if ans in self.single_choice:
			return self.answer(ans)
		if ans in self.string_choice:
			return self.answer(ans)
		try:
			ival=int(ans)
		except ValueError:
			return curses.beep()
		for r in self.range_choice:
			if ival in r:
				return self.answer(ival)
		curses.beep()

	def answer(self,ans):
		if ans is not None:
			if type(ans) is UnicodeType:
				self.content=ans
			else:
				self.content=unicode(ans)
			self.redraw()
		self.parent.input_handler(ans)

	def key_bs(self):
		if self.pos<=0:
			curses.beep()
			return
		self.content=self.content[:self.pos-1]+self.content[self.pos:]
		self.pos-=1
		self.win.move(0,self.pos+len(self.prompt))
		self.win.delch()
		self.win.refresh()

	def key_char(self,c):
		c=unicode(c,self.screen.encoding,"replace")
		if not self.string_choice and c in self.single_choice:
			return self.answer(c)
		if self.pos>=self.w-len(self.prompt)-2:
			return curses.beep()
		newcontent=self.content+c
		if c in string.digits and self.range_choice:
			pass
		elif newcontent in self.single_choice:
			pass
		else:
			ok=0
			for v in self.string_choice:
				if v.startswith(newcontent):
					ok=1
					break
			if not ok:
				return curses.beep()

		self.content=newcontent
		self.pos+=1
		self.win.addstr(c.encode(self.screen.encoding))
		self.win.refresh()

	def update(self,now=1,refresh=0):
		self.screen.lock.acquire()
		try:
			if refresh:
				self.win.move(0,0)
				self.win.clrtoeol()
				s=self.prompt.encode(self.screen.encoding,"replace")
				self.win.addstr(s)
				s=self.content.encode(self.screen.encoding,"replace")
				self.win.addstr(s)
			self.win.move(0,self.pos+len(self.prompt))
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()

	def redraw(self,now=1):
		self.update(now,1)

	def cursync(self,now=1):
		self.screen.lock.acquire()
		try:
			self.win.cursyncup()
			if now:
				self.win.refresh()
			else:
				self.win.noutrefresh()
		finally:
			self.screen.lock.release()
