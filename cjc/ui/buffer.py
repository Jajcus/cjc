
import threading
from types import StringType,UnicodeType

from cjc.commands import CommandHandler
from cjc import common

buffer_list=[]
activity_handlers=[]

class Buffer(CommandHandler):
	def __init__(self,info,descr_format="default_buffer_descr"):
		CommandHandler.__init__(self)
		try:
			buffer_list[buffer_list.index(None)]=self
		except ValueError:
			buffer_list.append(self)
		if type(info) in (StringType,UnicodeType):
			self.info={"buffer_name": info}
		else:
			self.info=info
		self.info["buffer_num"]=self.get_number()
		self.info["buffer_descr"]=descr_format
		self.window=None
		self.lock=threading.RLock()
		self.active=0
		for f in activity_handlers:
			f()

	def set_window(self,win):
		self.window=win
		if win:
			self.activity(0)

	def update_info(self,info):
		self.info.update(info)
		if self.window:
			self.window.update_status(self.info)

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
				if buffer_list[i] and not buffer_list[i].window:
					common.debug("Setting window's buffer to "+`buffer_list[i]`)
					window.set_buffer(buffer_list[i])
					window.update()
					window=None
					break
			if window:
				window.set_buffer(None)
				window.update()
				window=None
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
