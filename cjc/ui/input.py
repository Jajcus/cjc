
import curses
import curses.textpad
import string

from widget import Widget
from cjc import common
import text_input
import bool_input
import choice_input
import list_input
import complete

class InputError(StandardError):
	pass

class Input(Widget):
	def __init__(self,theme_manager):
		Widget.__init__(self)
		self.prompt_win=None
		self.input_win=None
		self.prompt=None
		self.theme_manager=theme_manager
		self.command_line=None
		self.input_widget=None
		self.question_handler=None
		self.question_abort_handler=None
		self.question_handler_arg=None
		
	def set_parent(self,parent):
		Widget.set_parent(self,parent)
		self.command_line=text_input.TextInput(self,0,u"",100)
		self.input_widget=self.command_line
		self.make_windows()
		self.screen.set_input_handler(self)

	def complete(self,s,pos):
		if self.input_widget!=self.command_line:
			self.screen.beep()
			return
		head,tails=complete.complete(s[:pos])
		common.debug("complete() returned: "+`(head,tails)`)
		if len(tails)!=1:
			self.screen.beep()
			return
		self.input_widget.set_content(head+tails[0]+s[pos:])
		self.input_widget.set_pos(len(head)+len(tails[0]))
		self.input_widget.redraw()

	def input_handler(self,answer):
		if self.input_widget==self.command_line:
			self.screen.user_input(answer)
			return
		handler=self.question_handler
		arg=self.question_handler_arg
		self.unask_question()
		if handler:
			handler(arg,answer)
			handler=None
	
	def abort_handler(self):
		if self.input_widget==self.command_line:
			return
		handler=self.question_abort_handler
		arg=self.question_handler_arg
		self.unask_question()
		if handler:
			handler(arg)
			handler=None

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
					prompt=self.prompt[:self.w/4-3]+"(...)"+self.prompt[-self.w/4+4:]
				common.debug("prompt="+`prompt`)
				l=len(prompt)
				self.prompt_win=curses.newwin(self.h,l+1,self.y,self.x)
				self.prompt_win.addstr(prompt)
				self.prompt_win.leaveok(1)
				self.input_win=curses.newwin(self.h,self.w-l-1,self.y,self.x+l+1)
			else:
				self.prompt_win=None
				self.input_win=curses.newwin(self.h,self.w,self.y,self.x)
			self.input_win.timeout(100)
			if self.input_widget:
				self.input_widget.set_parent(self)
		finally:
			self.screen.lock.release()

	def unask_question(self):
		if self.current_buffer:
			self.current_buffer.unask_question()

	def current_buffer_changed(self,buffer):
		if self.input_widget:
			self.input_widget.set_parent(None)
		if buffer and buffer.question:
			self.question_handler=buffer.question_handler
			self.question_abort_handler=buffer.question_abort_handler
			self.question_handler_arg=buffer.question_handler_arg
			self.prompt=buffer.question
			self.input_widget=buffer.input_widget
		else:
			self.question_handler=None
			self.question_abort_handler=None
			self.question_handler_arg=None
			self.prompt=None
			self.input_widget=self.command_line
			self.make_windows()
		self.current_buffer=buffer
		self.make_windows()
		self.update(1,1)

	def get_height(self):
		return 1

	def update(self,now=1,redraw=0):
		if self.prompt_win:
			self.prompt_win.noutrefresh()
		if self.input_widget:
			self.input_widget.update(0,redraw)
		if now:
			curses.doupdate()

	def cursync(self):
		if self.input_widget:
			return self.input_widget.cursync()

	def getch(self):
		if self.input_widget:
			return self.input_widget.win.getch()
