
import threading

from cjc.commands import CommandHandler

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
