
import threading

from cjc.commands import CommandHandler
from cjc import common

buffer_list=[]
activity_handlers=[]

class Buffer(CommandHandler):
	def __init__(self,name):
		CommandHandler.__init__(self)
		self.name=name
		self.window=None
		self.lock=threading.RLock()
		try:
			buffer_list[buffer_list.index(None)]=self
		except ValueError:
			buffer_list.append(self)
		self.active=0
		for f in activity_handlers:
			f()

	def set_window(self,win):
		self.window=win
		if win:
			self.activity(0)

	def close(self):
		common.debug("Closing buffer "+self.name)
		self.active=0
		n=buffer_list.index(self)
		if self.window:
			window=self.window
			self.window=None
			common.debug("Buffer has window")
			i=n
			while i>0:
				i-=1
				if buffer_list[i]:
					common.debug("Setting window's buffer to "+`buffer_list[i]`)
					window.set_buffer(buffer_list[i])
					break
			window.update()
		buffer_list[n]=None
		for f in activity_handlers:
			f()
	
	def get_number(self):
		return buffer_list.index(self)+1
		
	def format(self,width,height):
		pass

	def update(self,now=1):
		window=self.window
		if window:
			window.update(now)

	def redraw(self,now=1):
		window=self.window
		if window:
			window.redraw(now)

	def user_input(self,s):
		return 0

	def keypressed(self,ch,escape):
		return 0

	def activity(self,val):
		if self.window and self.active>0:
			self.active=0
		elif val>self.active and not self.window:
			self.active=val
		else:
			return
		for f in activity_handlers:
			f()
		
		
def get_by_number(n):
	if n==0:
		n=10
	try:
		return buffer_list[n-1]
	except IndexError:
		return None
