
from types import StringType,IntType,UnicodeType
import curses

from buffer import Buffer
from cjc import common
import keytable

class ListBufferError(StandardError):
	pass

class ListBuffer(Buffer):
	def __init__(self,theme_manager,name):
		Buffer.__init__(self,name)
		self.theme_manager=theme_manager
		self.keys=[]
		self.items=[]
		self.pos=0
				
	def set_window(self,win):
		Buffer.set_window(self,win)
		if win:
			keytable.activate("list-buffer",self)
		else:
			keytable.deactivate("list-buffer",self)

	def get_keys(self):
		return self.keys

	def has_key(self,key):
		return key in self.keys;

	def index(self,key):
		return self.keys.index(key)
		
	def append(self,key,view):
		self.lock.acquire()
		try:
			if key in self.keys:
				raise ListBufferError,"Item already exists"
			view=self.clean_item(view)
			i=len(self.keys)
			self.keys.append(key)
			self.items.append(view)
			self.activity(1)
			self.display(i)
		finally:
			self.lock.release()

	def insert_sorted(self,key,view):
		self.lock.acquire()
		try:
			if key in self.keys:
				raise ListBufferError,"Item already exists"
			view=self.clean_item(view)
			last=1
			for i in range(0,len(self.keys)):
				if self.keys[i]>key:
					self.keys.insert(i,key)
					self.items.insert(i,view)
					last=0
					break
			if last:
				i=len(self.keys)
				self.keys.append(key)
				self.items.append(view)
			self.activity(1)
			self.display(i,1)
		finally:
			self.lock.release()

	def update_item(self,key,view):
		self.lock.acquire()
		try:
			try:
				i=self.keys.index(key)
			except ValueError:
				raise ListBufferError,"Item not found"
			view=self.clean_item(view)
			self.items[i]=view
			self.activity(1)
			self.display(i)
		finally:
			self.lock.release()

	def remove_item(self,key):
		self.lock.acquire()
		try:
			try:
				i=self.keys.index(key)
			except ValueError:
				raise ListBufferError,"Item not found"
			del self.items[i]
			del self.keys[i]
			self.activity(1)
			self.undisplay(i)
		finally:
			self.lock.release()

	def clean_item(self,view):
		ret=[]
		for attr,s in view:
			s=s.replace("\n","")
			s=s.replace("\r","")
			s=s.replace("\f","")
			s=s.replace("\t","")
			ret.append((attr,s))
		return ret

	def insert_themed(self,key,format,params):
		view=[]
		for attr,s in self.theme_manager.format_string(format,params):
			view.append((attr,s))
		if self.has_key(key):
			self.update_item(key,view)
		else:
			self.insert_sorted(key,view)

	def clear(self):
		self.lock.acquire()
		try:
			self.keys=[]
			self.items=[]
			if self.window:
				self.window.clear()
		finally:
			self.lock.release()

	def format(self,width,height):
		self.lock.acquire()
		try:
			return self._format(width,height)
		finally:
			self.lock.release()
	
	def _format(self,width,height):
		ret=[]
		for i in range(self.pos,min(self.pos+height,len(self.keys))):
			ret.append(self.items[i])
		return ret
	
	def display(self,i,insert=0):
		self.lock.acquire()
		try:
			if not self.window:
				return
			if i<self.pos:
				return
			if i>=self.pos+self.window.ih:
				return
			common.debug("Updating item #%i" % (i,))
			if i>=len(self.items):
				self.window.win.move(0,i-self.pos)
				self.window.clrtoeol()
				return
			view=self.items[i]
			attr,s=view[0]
			common.debug("Item: %r" % (view,))
			if insert:
				self.window.insert_line(i-self.pos)
			self.window.write_at(0,i-self.pos,s,attr)
			for attr,s in view[1:]:
				self.window.write(s,attr)
			y,x=self.window.win.getyx()
			if x<self.window.iw-1:
				self.window.clrtoeol()
		finally:
			self.lock.release()

	def undisplay(self,i):
		self.lock.acquire()
		try:
			if not self.window:
				return
			if i<self.pos:
				return
			if i>=self.pos+self.window.ih:
				return
			common.debug("Erasing item #%i" % (i,))
			self.window.delete_line(i-self.pos)
			if len(self.items)>=self.pos+self.window.ih:
				self.display(self,self.pos+self.window.ih-1)
		finally:
			self.lock.release()

	def page_up(self):
		self.lock.acquire()
		try:
			if self.pos<=0:
				return
			self.pos-=self.window.ih
			if self.pos<0:
				self.pos=0
			self.window.draw_buffer()
			self.window.update()
		finally:
			self.lock.release()

	def page_down(self):
		self.lock.acquire()
		try:
			if self.pos>=len(self.keys)-self.window.ih+1:
				return
			self.pos+=self.window.ih
			self.window.draw_buffer()
			self.window.update()
		finally:		
			self.lock.release()

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
	
from keytable import KeyFunction
ktb=keytable.KeyTable("list-buffer",30,(
		KeyFunction("page-up",
				ListBuffer.page_up,
				"Scroll buffer one page up",
				"PPAGE"),
		KeyFunction("page-down",
				ListBuffer.page_down,
				"Scroll buffer one page down",
				"NPAGE"),
		))

keytable.install(ktb)
