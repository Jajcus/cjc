
from types import StringType,IntType,UnicodeType
import curses

from buffer import Buffer

class TextBuffer(Buffer):
	def __init__(self,theme_manager,name,length=200):
		Buffer.__init__(self,name)
		self.theme_manager=theme_manager
		self.length=length
		self.lines=[[]]
		self.pos=None
		
	def set_window(self,win):
		Buffer.set_window(self,win)
		if win:
			win.scroll_and_wrap=1
		
	def append(self,s,attr="default"):
		self.lock.acquire()
		try:
			return self._append(s,attr)
		finally:
			self.lock.release()

	def _append(self,s,attr):
		if type(attr) is not IntType:
			attr=self.theme_manager.attrs[attr]
		if self.window and self.pos is None:
			self.window.write(s,attr)
		else:
			self.activity(1)
		newl=0
		s=s.split(u"\n")
		for l in s:
			if newl:
				self.lines.append([])
			if l:
				self.lines[-1].append((attr,l))
			newl=1
		self.lines=self.lines[-self.length:]
		self.activity(1)
		
	def append_line(self,s,attr="default"):
		self.lock.acquire()
		try:
			return self._append_line(s,attr)
		finally:
			self.lock.release()
		
	def _append_line(self,s,attr):
		if type(attr) is not IntType:
			attr=self.theme_manager.attrs[attr]
		self._append(s,attr)
		self.lines.append([])
		if self.window and self.pos is None:
			self.window.write(u"\n",attr)

	def append_themed(self,format,params):
		for attr,s in self.theme_manager.format_string(format,params):
			self.append(s,attr)

	def write(self,s):
		self.lock.acquire()
		try:
			self._append(s,"default")
			self.update()
		finally:
			self.lock.release()

	def clear(self):
		self.lock.acquire()
		try:
			self.lines=[[]]
		finally:
			self.lock.release()

	def line_length(self,line):
		ret=0
		for attr,s in line:
			ret+=len(s)
		return ret

	def offset_back(self,width,back,l=None,c=0):
		if l is None or l>=len(self.lines):
			if self.lines[-1]==[]:
				l=len(self.lines)-1
			else:
				l=len(self.lines)
			if l<=0:
				return 0,0
		while back>0 and l>1:
			l-=1
			line=self.lines[l]
			ln=self.line_length(line)
			h=ln/width+1
			back-=h
		if back>0:
			return 0,0
		if back==0:
			return l,0
		return l,(-back)*width

	def offset_forward(self,width,forward,l=0,c=0):
		if l>=len(self.lines):
			l=len(self.lines)-1
			if self.lines[-1]==[]:
				l-=1
			if l>0:
				return l,0
			else:
				return 0,0

		if c>0:
			left,right=self.split_line(self.lines[l],c)
			l+=1
			ln=self.line_length(right)
			forward-=ln/width+1
		
		end=len(self.lines)
		if self.lines[-1]==[]:
			end-=1

		l-=1
		while forward>0 and l<end-1:
			l+=1
			line=self.lines[l]
			ln=self.line_length(line)
			h=ln/width+1
			forward-=h

		if forward>=0:
			return l,0

		if l>0:
			return l-1,0
		else:
			return 0,0

	def cut_line(self,line,cut):
		i=0
		left=[]
		right=[]
		for attr,s in line:
			l=len(s)
			i1=i
			i+=l
			if i<cut:
				left.append((attr,s))
			elif i1<cut and i>cut:
				left.append((attr,s[:cut-i]))
				right.append((attr,s[cut-i:]))
			else:
				right.append((attr,s))
		return left,right
			
	def format(self,width,height):
		self.lock.acquire()
		try:
			return self._format(width,height)
		finally:
			self.lock.release()
	
	def _format(self,width,height):
		if self.pos is None:
			l,c=self.offset_back(width,height)
		else:
			l,c=self.pos
		if c:
			x,line=self.cut_line(self.lines[l],c)
			ret=[line]
			l+=1
			height-=self.line_length(line)/width+1
		else:
			ret=[]
			
		end=len(self.lines)
		if self.lines[-1]==[]:
			end-=1

		while height>0 and l<end:
			line=self.lines[l]
			ln=self.line_length(line)
			h=ln/width+1
			ret.append(line)
			height-=h
			l+=1

		if height>=0:
			if self.lines[-1]==[]:
				ret.append([])
			return ret

		cut=(-height)*width
		ret[-1],x=self.cut_line(ret[-1],cut)
		ret.append([])
		return ret

	def page_up(self):
		self.lock.acquire()
		try:
			if self.pos is None:
				l,c=self.offset_back(self.window.w,self.window.h-2)
			else:
				l,c=self.pos

			if (l,c)==(0,0):
				self.pos=l,c
				formatted=self._format(self.window.w,self.window.h-1)
				if len(formatted)<=self.window.h-1:
					self.pos=None
				return
			l1,c1=self.offset_back(self.window.w,self.window.h-2,l,c)
			self.pos=l1,c1
		finally:
			self.lock.release()
		self.window.draw_buffer()
		self.window.update()

	def page_down(self):
		self.lock.acquire()
		try:
			if self.pos is None:
				return

			l,c=self.pos
				
			l1,c1=self.offset_forward(self.window.w,self.window.h-2,l,c)
			self.pos=l1,c1
			formatted=self.format(self.window.w,self.window.h-1)
			if len(formatted)<=self.window.h-1:
				self.pos=None
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
			
