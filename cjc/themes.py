import curses
import string
import re
import time
from types import UnicodeType,StringType
import version

import pyxmpp

from commands import CommandError,CommandArgs
import ui
import common

attr_sel_re=re.compile(r"(?<!\%)\%\[([^]]*)\]",re.UNICODE)
formatted_re=re.compile(r"(?<!\%)\%\{([^]]*)\}",re.UNICODE)

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
		attr|=attributes_by_name[a.lower()]
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
	def __init__(self,app):
		self.attrs={}
		self.attr_defs={}
		self.formats={}
		self.pairs={}
		self.next_pair=1
		self.app=app
	def load(self,filename):
		f=open(filename,"r")
		for l in f.xreadlines():
			command=CommandArgs(l.strip())
			self.command(command,1)
		f.close()
		if self.app and self.app.screen:
			self.app.screen.redraw()
	def save(self,filename):
		f=open(filename,"w")
		attr_names=self.attr_defs.keys()
		attr_names1=[n for n in attr_names if n.find(".")<0]
		attr_names2=[n for n in attr_names if n.find(".")>=0]
		attr_names1.sort()
		attr_names2.sort()
		for name in attr_names1+attr_names2:
			(fg,bg,attr,fallback)=self.attr_defs[name]
			cmd=CommandArgs("attr")
			cmd.add_quoted(name)
			cmd.add_quoted(color2name(fg))
			cmd.add_quoted(color2name(bg))
			cmd.add_quoted(attr2name(attr))
			cmd.add_quoted(attr2name(fallback))
			print >>f,cmd.all()
		format_names=self.formats.keys()
		format_names1=[n for n in format_names if n.find(".")<0]
		format_names2=[n for n in format_names if n.find(".")>=0]
		format_names1.sort()
		format_names2.sort()
		for name in format_names1+format_names2:
			format=self.formats[name]
			cmd=CommandArgs("format")
			cmd.add_quoted(name)
			cmd.add_quoted(format)
			print >>f,cmd.all()
		f.close()
	def command(self,args,safe=0):
		cmd=args.shift()
		if cmd=="save" and not safe:
			filename=args.shift()
			if not filename:
				filename=".cjc-theme"
			args.finish()
			self.save(filename)
			return
		if cmd=="load" and not safe:
			filename=args.shift()
			if not filename:
				filename=".cjc-theme"
			args.finish()
			self.load(filename)
			return
		if cmd=="attr":
			name=args.shift()
			fg=name2color(args.shift())
			bg=name2color(args.shift())
			attr=name2attr(args.shift())
			fallback=name2attr(args.shift())
			args.finish()
			self.set_attr(name,fg,bg,attr,fallback)
		if cmd=="format":
			name=args.shift()
			format=args.shift()
			args.finish()
			self.set_format(name,format)
	
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
	def format_buffers(self,attr,params):
		ret=[]
		for num in range(0,len(ui.buffer.buffer_list)):
			buf=ui.buffer.buffer_list[num]
			if buf is None:
				continue
			p=params.copy()
			p["name"]=buf.name
			p["num"]=num+1
			if buf.window:
				format="buffer_visible"
			elif buf.active==1:
				format="buffer_active1"
			elif buf.active==2:
				format="buffer_active2"
			elif buf.active>2:
				format="buffer_active3"
			else:
				format="buffer_inactive"
			format=self.formats.get(format)
			if not format:
				continue
			f_buf=self.do_format_string(format,attr,p)
			if ret:
				ret.append((self.attrs.get(attr,self.attrs["default"]),","))
			ret+=f_buf
		return ret
		
	def format_string(self,fname,params):
		format=self.formats[fname]
		return self.do_format_string(format,"default",params)
		
	def do_format_string(self,format,attr,params):
		if type(params) in (UnicodeType,StringType):
			params={"msg":params}
		else:	
			params=params.copy()
		l=attr_sel_re.split(format,1)
		if len(l)==3:
			format=l[0]
			next_attr=l[1]
			if next_attr.find("%")>=0:
				next_attr=self.substitute(next_attr,params)
			next=l[2]
		else: 
			next=None

		l=formatted_re.split(format,1)
		if len(l)==3:
			before,name,after=l
			if params.has_key(name):
				val=params[name]
			else:
				val=self.find_format_param(name,params)
			if val:
				ret=[]
				if before:
					ret+=self.do_format_string(before,attr,params)
				if callable(val):
					ret+=val(attr,params)
				elif self.formats.has_key(val):
					f=self.formats[val]
					ret+=self.do_format_string(f,attr,params)
				else:
					format="%s%%%%{%s}%s" % (before,name,after)
					ret+=self.do_format_string(format,attr,params)
					before=None
					after=None
				if after:
					ret+=self.do_format_string(after,attr,params)
				if next:
					ret+=self.do_format_string(next,next_attr,params)
				return ret
			else:
				format="%s%%%%{%s}%s" % (before,name,after)

		s=self.substitute(format,params)

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

	def substitute(self,format,params):
		while 1:
			try:
				s=format % params
				break
			except (ValueError,TypeError),e:
				s="[%s: %r, %r]" % (str(e),format,params)
				break
			except KeyError,key:
				key=str(key)
				if key.find(":")>0:
					format=self.process_format_param(format,key,params)
				else:
					val=self.find_format_param(key,params)
					if not val:
						format=self.quote_format_param(format,key)
		return s
					
	def quote_format_param(self,format,key):
		return format.replace("%%(%s)" % key,"%%%%(%s)" % key)

	def find_format_param(self,key,params):
		if key in ("now","timestamp"):
			val=time.time()
		elif key in ("me","jid"):
			if self.app.stream:
				val=self.app.jid
			else:
				val=self.app.settings["jid"]
		elif key=="buffers":
			val=self.format_buffers
		elif key=="program_name":
			val="CJC"
		elif key=="program_author":
			val="Jacek Konieczny <jajcus@bnet.pl>"
		elif key=="program_version":
			val=version.version
		else:
			return None
		params[key]=val
		return val
	
	def process_format_param(self,format,key,params):
		sp=key.split(":",2)
		if len(sp)==2:
			typ,param=sp
			form=None
		else:
			typ,param,form=sp
		if params.has_key(param):
			val=params[param]
		else:
			val=self.find_format_param(param,params)
			if val is None:
				return self.quote_format_param(format,key)

		if typ=="T":
			if form:
				params[key]=time.strftime(form,time.localtime(val))
				return format
			else:
				params[key]=time.strftime("%H:%M",time.localtime(val))
				return format
		elif typ=="J":
			if not isinstance(val,pyxmpp.JID):
				try:
					val=pyxmpp.JID(val)
				except pyxmpp.JIDError:
					params[key]=""
					return format
			if form=="nick":
				rostername=self.app.get_user_info(val,"rostername")
				if rostername:
					params[key]=rostername
				else:
					params[key]=val.node
			elif form=="node":
				params[key]=val.node
			elif form=="domain":
				params[key]=val.domain
			elif form=="resource":
				params[key]=val.resource
			elif form=="bare":
				params[key]=val.bare().as_unicode()
			elif form in ("show","status"):
				common.debug("Getting presence for user "+str(val))
				pr=self.app.get_user_info(val,"presence")
				common.debug("Got: "+`pr`)
				if pr:
					common.debug("type: "+`pr.get_type()`)
					common.debug("show: "+`pr.get_show()`)
					common.debug("status: "+`pr.get_status()`)
				if form=="show":
					common.debug("Getting show")
					if pr is None or pr.get_type()=="unavailable":
						val="offline"
					else:
						val=pr.get_show()
						if not val or val=="":
							val="online"
				elif form=="status":
					common.debug("Getting status")
					if pr is None:
						val=""
					else:
						val=pr.get_status()
						if val is None:
							val=""
				common.debug("Got: "+`val`)
				params[key]=val
			elif form in ("full",None):
				params[key]=val.as_unicode()
			else:
				ival=self.app.get_user_info(val,form)
				if not ival:
					val=""
				elif ival not in (StringType,UnicodeType):
					if self.app.info_handlers.has_key(form):
						val=self.app.info_handlers[form](form,ival)[1]
					else:
						val=str(ival)
				params[key]=val
			return format
		else:
			return quote_format_param(format,key)
