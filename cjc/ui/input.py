
import curses
import curses.textpad
import string

from widget import Widget
from cjc import common
import line_input


class Input(Widget):
	def __init__(self,theme_manager):
		Widget.__init__(self)
		self.prompt_win=None
		self.input_win=None
		self.prompt=None
		self.theme_manager=theme_manager
		self.command_line=None
		self.input_widget=None
		
	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.command_line=line_input.LineInput(self,None,0,u"",100)
		self.input_widget=self.command_line
		self.make_windows()

	def input_handler(self,arg,content):
		if self.input_widget==self.command_line:
			self.screen.user_input(content)
			return
		if self.question_handler:
			self.question_handler(arg,content)
			self.question_handler=None
		self.question_abort_handler=None
		self.input_widget=self.command_line
		self.update()
	
	def abort_handler(self,arg):
		if self.input_widget==self.command_line:
			return
		if self.question_abort_handler:
			self.question_abort_handler(arg,content)
			self.question_abort_handler=None
		self.question_handler=None
		self.input_widget=self.command_line
		self.update()

	def make_windows(self):
		self.prompt_win=None
		self.input_win=None
		self.screen.lock.acquire()
		try:
			if self.prompt:
				l=len(self.prompt)
				if l<self.w/2:
					prompt=self.prompt
				else:
					prompt=self.prompt[:l/2-2]+"(...)"+self.prompt[l/2+2:]
				l=len(prompt)
				self.prompt_win=curses.newwin(self.h,l+1,self.y,self.x)
				self.prompt_win.addstr(prompt)
				self.input_win=curses.newwin(self.h,self.w-l-1,self.y,self.x+l+1)
			else:
				self.prompt_win=None
				self.input_win=curses.newwin(self.h,self.w,self.y,self.x)
			if self.input_widget:
				self.input_widget.set_window(self.input_win)
				self.screen.set_default_key_handler(self.input_widget)
		finally:
			self.screen.lock.release()

	def ask_question(question,type,default,handler,abort_handler,arg):
		if type=="text":
			self.input_widget=line_input.LineInput(self,arg,1,default,0)
		else:
			raise InputError,"Unknown input type: "+type
		self.question_handler=handler
		self.question_abort=handler=abort_handler
		self.prompt=question
		self.make_windows()
	
	def get_height(self):
		return 1

	def update(self,now=1,redraw=0):
		if self.prompt_win:
			self.prompt_win.noutrefresh()
		if self.input_widget:
			self.input_widget.update(0,redraw)
		if now:
			curses.doupdate()
