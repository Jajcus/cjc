
from types import StringType,IntType,UnicodeType
import curses

from buffer import Buffer

class ListBufferError(StandardError):
	pass

class ListBuffer(Buffer):
	def __init__(self,theme_manager,name,length=200):
		Buffer.__init__(self,name)
		self.theme_manager=theme_manager
		self.keys=[]
		self.items=[]
		self.pos=0
		
	def set_window(self,win):
		Buffer.set_window(win)
		self.window.scrollok=0

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
			self.display(i)
		finally:
			self.lock.release()

	def insert_sorted(self,key,view):
		self.lock.acquire()
		try:
			if key in self.keys:
				raise ListBufferError,"Item already exists"
			view=self.clean_item(view)
			for i in range(0,len(keys)):
				if keys[i]>key:
					keys.insert(i,key)
					items.insert(i,value)
					break
			if i==len(keys):
				keys.append(key)
				items.append(value)
			self.display(i)
		finally:
			self.lock.release()

	def clean(self,view):
		ret=[]
		for s,attr in view:
			s.replace("\n"," ")
			s.replace("\r"," ")
			s.replace("\f"," ")
			s.replace("\t"," ")
			ret.append(s,attr)
		return ret

	def insert_themed(self,key,format,params):
		view=[]
		for attr,s in self.theme_manager.format_string(format,params):
			view.append(s,attr)
		self.insert_sorted(key,view)

	def clear(self):
		self.lock.acquire()
		try:
			self.keys=[]
			self.items=[]
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
			ret.append(items[i])	
		return ret
	
	def display(self,i):
		if i<self.pos:
			return
		if i>=self.pos+self.window.h:
			return
		view=self.items[i]
		self.window.write_at(0,i-self.pos,view[0][0],view[0][1])
		for s,attr in view[1:]:
			self.window.write(s,attr)

	def page_up(self):
		self.lock.acquire()
		try:
			if self.pos<=0:
				return
			self.pos-=self.window.h
			if self.pos<0:
				self.pos=0
		finally:
			self.lock.release()
		self.window.draw_buffer()
		self.window.update()

	def page_down(self):
		self.lock.acquire()
		try:
			if self.pos>=len(self.keys)-self.window.h+1:
				return
			self.pos+=self.window.h
		finally:		
			self.lock.release()
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
			
