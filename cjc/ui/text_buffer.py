
from types import StringType,IntType,UnicodeType
import curses

from buffer import Buffer
from cjc import common

class TextBuffer(Buffer):
	def __init__(self,theme_manager,name,length=200):
		Buffer.__init__(self,name)
		self.theme_manager=theme_manager
		self.length=length
		self.lines=[[]]
		self.pos=None
		
	def set_window(self,win):
		Buffer.set_window(self,win)
		
	def append(self,s,attr="default"):
		self.lock.acquire()
		try:
			return self._append(s,attr)
		finally:
			self.lock.release()

	def _append(self,s,attr):
		if type(attr) is not IntType:
			attr=self.theme_manager.attrs[attr]
		if self.lines[-1]==[] and self.window:
			self.window.nl()
		newl=0
		s=s.split(u"\n")
		for l in s:
			if newl:
				self.lines.append([])
			if l:
				self.lines[-1].append((attr,l))
				if self.window:
					y,x=self.window.win.getyx()
					while l:
						if x+len(l)>self.window.iw:
							p,l=self.split_text(l,self.window.iw-x)
						else:
							p,l=l,None
						self.window.write(p,attr)
						x+=len(p)
						if x>=self.window.iw:
							x=0
							y+=1
							if y>=self.window.ih:
								y=self.window.ih-1
					else:
						self.window.write(l,attr)
			newl=1
		l=len(self.lines)
		if l>self.length and self.pos is None:
			self.lines=self.lines[-self.length:]
		if not self.window or self.pos is not None:
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

	def split_text(self,s,n,allow_all=0):
		return s[:n],s[n:]

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
		while height>0 and l<end:
			line=self.lines[l]
			while line is not None and height>0:
				ln=self.line_length(line)
				if ln>width:
					part,line=self.cut_line(line,width)
				else:
					part,line=line,None
				if part==[] and height==1:
					break
				ret.append(part)
				height-=1
			l+=1
		common.debug("format returning: "+`ret`)	
		return ret

	def update_pos(self):
		if self.pos:
			self.window.update_status({"bufrow":self.pos[0],"bufcol":self.pos[1]})
		else:
			self.window.update_status({"bufrow":"","bufcol":""})

	def page_up(self):
		self.lock.acquire()
		try:
			if self.pos is None:
				l,c=self.offset_back(self.window.iw,self.window.ih-1)
			else:
				l,c=self.pos

			if (l,c)==(0,0):
				self.pos=l,c
				formatted=self._format(self.window.iw,self.window.ih+1)
				if len(formatted)<=self.window.ih:
					self.pos=None
				self.update_pos()
				return
			l1,c1=self.offset_back(self.window.iw,self.window.ih-1,l,c)
			self.pos=l1,c1
		finally:
			self.lock.release()
		self.update_pos()
		self.window.draw_buffer()
		self.window.update()

	def page_down(self):
		self.lock.acquire()
		try:
			if self.pos is None:
				self.update_pos()
				return

			l,c=self.pos
				
			l1,c1=self.offset_forward(self.window.iw,self.window.ih-1,l,c)
			self.pos=l1,c1
			formatted=self.format(self.window.iw,self.window.ih+1)
			if len(formatted)<=self.window.ih:
				self.pos=None
		finally:		
			self.lock.release()
		if self.pos:
			self.window.update_status({"bufrow":self.pos[0],"bufcol":self.pos[1]})
		else:
			self.window.update_status({"bufrow":"","bufcol":""})
		self.update_pos()
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
			
