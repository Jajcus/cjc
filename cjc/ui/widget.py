class Widget:
	def __init__(self):
		self.screen=None
		self.parent=None
		
	def set_parent(self,parent):
		self.parent=parent
		self.screen=parent.screen
		self.x,self.y,self.w,self.h=self.parent.place(self)

	def get_height(self):
		return None
	
	def get_width(self):
		return None
	
	def update(self,now=1,redraw=0):
		pass

	def redraw(self,now=1):
		self.update(now,1)

