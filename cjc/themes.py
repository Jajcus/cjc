import curses
import string

from command_args import CommandError,CommandArgs

attributes_by_name={}
attributes_by_val={}
#colors_by_val={}
colors_by_name={}

for att in dir(curses):
	if att.startswith("COLOR_"):
		name=att[6:].lower()
		colors_by_name[name]=getattr(curses,att)
		colors_by_val[getattr(curses,att)]=name
	elif att.startswith("A_"):
		name=att[2:].lower()
		attributes_by_name[name]=getattr(curses,att)
		#attributes_by_val[getattr(curses,att)]=name

def name2attr(name):
	attr=0
	name.replace("|","+")
	for a in name.split("+"):
		attr|=attributes_by_name(a.lower())
	return attr

def attr2name(attr):
	names=[]
	for name,val in attributes_by_name.items():
		if not val:
			continue
		if attr&val==val:
			attr-=val
			names.append(name)
	if not names:
		return "normal"
	return string.join(names,"+")

def name2color(name):
	return colors_by_name(name.lower())

def color2name(color):
	return colors_by_val(color)

class Theme:
	def __init__(self):
		self.attrs={}
		self.attr_defs={}
		self.formats={}
	def load(self,filename):
		f=open(filename,"r")
		for l in f.xreadlines():
			command=CommandArgs(l.strip())
			self.command(command)
		f.close()
	def save(self,filename):
		f=open(filename,"w")
		for name,(fg,bg,attr,fallback) in self.attr_defs:
			cmd=CommandArgs("attr")
			cmd.add_quoted(name)
			cmd.add_quoted(fg)
			cmd.add_quoted(bg)
			cmd.add_quoted(attr)
			cmd.add_quoted(fallback)
			print >>f,cmd.all()
		for name,format in self.formats:
			cmd=CommandArgs("format")
			cmd.add_quoted(name)
			cmd.add_quoted(format)
			print >>f,cmd.all()
		f.close()
	def command(self,args):
		cmd=args.shift()
		if cmd=="save":
			filename=args.shift()
			if not filename:
				filename=".cjc-theme"
			args.finish()
			self.save(filename)
			return
		if cmd=="load":
			filename=args.shift()
			if not filename:
				filename=".cjc-theme"
			args.finish()
			self.load(filename)
			return
	def set_attr(self,name,fg,bg,attr,fallback):
		if not curses.has_colors():
			self.attrs[name]=fallback
			self.attr_defs[name]=(fg,bg,attr,fallback)
			return
		if self.pairs.has_key((fg,bg)):
			pair=self.pair[fg,bg]
		elif self.next_pair>curses.COLOR_PAIRS:
			self.attrs[name]=fallback
			self.attr_defs[name]=(fg,bg,attr,fallback)
			return
		else:
			curses.init_pair(self.next_pair,fg,bg)
			pair=self.next_pair
			self.next_pair+=1
		attr|=curses.color_pair(pair)
		self.attrs[name]=attr
		self.attr_defs[name]=(fg,bg,attr,fallback)
	def set_default_attr(self,name,fg,bg,attr,fallback):
		if not self.attrs.has_key(name):
			set_attr(name,fg,bg,attr,fallback)
	def set_default_attrs(self,attrs):
		for name,fg,bg,attr,fallback in attrs:
			set_default_attr(name,fg,bg,attr,fallback)
	def set_format(self,name,format):
		self.formats[name]=format
	def set_default_format(self,name,format):
		if not self.formats.has_key(name):
			self.formats[name]=format
	def set_default_formats(self,formats):
		for name,format in formats:
			if not self.formats.has_key(name):
				self.formats[name]=format
	
