import curses
import string
import re
import time
from types import UnicodeType,StringType

from command_args import CommandError,CommandArgs


attr_sel_re=re.compile(r"^(?P<before>[^\%]|(%%)|%\()*\%\[(?P<attr>[^]]*)\](?P<after>.*)$",re.UNICODE)

attributes_by_name={}
colors_by_val={}
colors_by_name={}

for att in dir(curses):
	if att.startswith("COLOR_"):
		name=att[6:].lower()
		colors_by_name[name]=getattr(curses,att)
		colors_by_val[getattr(curses,att)]=name
	elif att.startswith("A_"):
		name=att[2:].lower()
		attributes_by_name[name]=getattr(curses,att)

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
	return colors_by_name[name.lower()]

def color2name(color):
	return colors_by_val[color]

class ThemeManager:
	def __init__(self):
		self.attrs={}
		self.attr_defs={}
		self.formats={}
		self.pairs={}
		self.next_pair=1
	def load(self,filename):
		f=open(filename,"r")
		for l in f.xreadlines():
			command=CommandArgs(l.strip())
			self.command(command)
		f.close()
	def save(self,filename):
		f=open(filename,"w")
		for name,(fg,bg,attr,fallback) in self.attr_defs.items():
			cmd=CommandArgs("attr")
			cmd.add_quoted(name)
			cmd.add_quoted(color2name(fg))
			cmd.add_quoted(color2name(bg))
			cmd.add_quoted(attr2name(attr))
			cmd.add_quoted(attr2name(fallback))
			print >>f,cmd.all()
		for name,format in self.formats.items():
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
			self.set_attr(name,fg,bg,attr,fallback)
	def set_default_attrs(self,attrs):
		for name,fg,bg,attr,fallback in attrs:
			self.set_default_attr(name,fg,bg,attr,fallback)
	def set_format(self,name,format):
		self.formats[name]=format
	def set_default_format(self,name,format):
		if not self.formats.has_key(name):
			self.formats[name]=format
	def set_default_formats(self,formats):
		for name,format in formats:
			if not self.formats.has_key(name):
				self.formats[name]=format
	def format_string(self,fname,attr,params):
		format=self.formats[fname]
		return self.do_format_string(format,attr,params)
		
	def do_format_string(self,format,attr,params):
		m=attr_sel_re.match(format)
		if m:
			format=m.group("before")
			next_attr=m.group("attr")
			next=m.group("after")
		else: 
			next=None

		if type(params) in (UnicodeType,StringType):
			params={"msg":params}

		while 1:
			try:
				s=format % params
				break
			except TypeError:
				s=format
				break
			except KeyError,key:
				key=str(key)
				if key.startswith("T:"):
					param=key[2:]
					f=param.find(":")
					if f>0:
						tformat=param[f+1:]
						param=param[:f]
					else:
						tformat="%H:%M"
					if params.has_key(param):
						t=params[param]
					elif param=="now":
						t=time.localtime()
					else:
						format=format.replace("%%(%s)" % key,
									"%%%%(%s)" % key)
						continue
					params=params.copy()
					params[key]=time.strftime(tformat,t)
				else:
					format=format.replace("%%(%s)" % key,"%%%%(%s)" % key)
		if self.attrs.has_key(attr):
			attr=self.attrs[attr]
		else:
			attr=self.attrs["default"]
			
		ret=[]
		if s:
			ret.append((attr,s))
		if next:
			ret+=self.do_format_string(next,next_attr,params)
		return ret
