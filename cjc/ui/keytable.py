
import re
import curses
from cjc import common
from types import StringType,UnicodeType


class KeytableError(StandardError):
	pass

fun_re=re.compile(r"^([a-z-]+)(\((([^)]|(\\\)))*)\))?$")

class KeyBinding:
	def __init__(self,fun,keys):
		m=fun_re.match(fun)
		if not m:
			raise KeytableError,"Bad key function syntax"
		self.fun=m.group(1)
		self.arg=m.group(3)
		if keys is None:
			self.keys=None
		elif type(keys) in (StringType,UnicodeType):
			self.keys=[keyname_to_code(keys)]
		else:
			self.keys=[keyname_to_code(k) for k in keys]

class KeyFunction:
	def __init__(self,name,handler,descr,default_keys=None):
		m=fun_re.match(name)
		if not m:
			raise KeytableError,"Bad key function syntax"
		arg=m.group(3)
		if arg is not None:
			if arg:
				raise KeytableError,"Cannot use arguments in KeyFunction"
			elif default_keys:
				raise KeytableError,"Cannot assign default keybindings for function with arguments"
			self.accepts_arg=1
		else:
			self.accepts_arg=0
		if default_keys:
			self.default_binding=KeyBinding(name,default_keys)
		else:
			self.default_binding=None
		self.name=m.group(1)
		self.handler=handler
		self.descr=descr
		
	def __repr__(self):
		return "<KeyFunction %r>" % (self.name,)
		
	def invoke(self,object,arg=None):
		if self.accepts_arg and arg is None:
			raise KeytableErrot,"%s requires argument" % (self.name,)
		if self.accepts_arg:
			self.handler(object,arg)
		else:
			self.handler(object)
		
class KeyTable:
	def __init__(self,name,prio,content):
		self.name=name
		self.prio=prio
		self.keytable={}
		self.funtable={}
		for x in content:
			if isinstance(x,KeyBinding):
				binding=x
				try:
					fun=self.lookup_function(binding.fun)
				except KeyError:
					try:
						fun=lookup_function(binding.fun)
					except KeyError:
						fun=binding.fun
			elif isinstance(x,KeyFunction):
				binding=x.default_binding
				fun=x
				self.funtable[fun.name]=fun
			else:
				raise "%r is not a KeyBinding nor a KeyFunction" % (x,)
			if binding:
				for k in binding.keys:
					self.keytable[k]=(fun,binding.arg)
		self.object=None
		self.active=0
		self.default_handler=None
		self.input_window=None

	def __repr__(self):
		if self.active:
			act="active "
		else:
			act=""
		return "<KeyTable %r %sprio=%r>" % (self.name,act,self.prio)
		
	def has_key(self,c,meta):
		return self.keytable.has_key((c,meta))
	
	def lookup_key(self,c,meta):
		return self.keytable[(c,meta)]
	
	def process_key(self,c,meta):
		common.debug("%r.process_key(%r,%r); table=%r" % (self,c,meta,self.keytable))
		fun,arg=self.keytable[(c,meta)]
		if not isinstance(fun,KeyFunction):
			common.debug("funtable=%r" % (self.funtable,))
			try:
				fun=self.lookup_function(fun)
			except KeyError:
				fun=lookup_function(fun)
			self.keytable[(c,meta)]=fun,arg
		fun.invoke(self.object,arg)
		
	def lookup_function(self,name):
		return self.funtable[name]

def keyname_to_code(name):
	if name.startswith("M-") or name.startswith("m-") or name.startswith("^["):
		meta=1
		name=name[2:]
	else:
		meta=0
	if hasattr(curses,"KEY_"+name.upper()):
		return getattr(curses,"KEY_"+name.upper()),meta
	if len(name)==2 and name[0]=="^":
		c=ord(name[1].upper())
		if c=="?":
			return 0x7f,meta
		if c<64 or c>95:
			raise KeytableError,"Bad key name: "+`name`
		return c-64,meta
	if name.startswith("\\"):
		if len(name)==2:
			name=name[1]
		elif len(name)==4:
			name=chr(int(name[1:],8))
		else:
			raise KeytableError,"Bad key name: "+`name`
	if len(name)!=1:
		raise KeytableError,"Bad key name: "+`name`
	return ord(name[0]),meta

def keycode_to_name(code,meta):
	if code>=256:
		name=curses.keyname(code)
		if name.startswith("KEY_"):
			name=name[4:]
		if name.startswith("F("):
			name="F"+name[2:-1]
	elif code>=128:
		name="\\%03o" % (code,)
	else:
		name=curses.keyname(code)
	if meta:
		return "M-"+name
	else:
		return name

keytables=[]
active_input_window=None

def install(keytable):
	pos=len(keytables)
	for i in range(0,len(keytables)):
		if keytable.prio>keytables[i].prio:
			pos=i
			break
	keytables.insert(pos,keytable)

def lookup_table(name):
	for t in keytables:
		if t.name==name:
			return t
	raise KeyError,name

def find_active_input_window():
	global active_input_window
	active_input_window=None
	for t in keytables:
		if t.input_window:
			active_input_window=t.input_window
			return
			
def activate(name,object,default_handler=None,input_window=None):
	table=lookup_table(name)
	table.active=1
	table.object=object
	table.default_handler=default_handler
	table.input_window=input_window
	find_active_input_window()

def deactivate(name,object=None):
	table=lookup_table(name)
	if object and table.object!=object:
		return
	table.active=0
	table.object=None
	table.default_handler=None
	table.input_window=None

def lookup_function(name):
	for ktb in keytables:
		if not ktb.active:
			continue
		try:
			return ktb.lookup_function(name)
		except KeyError:
			pass
	raise KeyError,name

meta=0

def process_key(code):
	default_handler=None
	for t in keytables:
		if not t.active:
			continue
		if not default_handler and t.default_handler:
			default_handler=t.default_handler
		try:
			return t.process_key(code,meta)
		except KeyError:
			continue
	if default_handler:
		return default_handler(code,meta)
	else:
		try:
			common.debug("Unhandled key: "+keycode_to_name(code,meta))
			curses.beep()
		except curses.error:
			pass
		return 0

def keypressed():
	global meta
	if not active_input_window:
		raise KeytableError,"No input window set"
	ch=active_input_window.getch()
	if ch==-1:
		return 0
	if ch==27:
		if meta:
			meta=0
			try:
				process_key(27)
			except common.standard_errors,e:
				common.print_exception()
			return 1
		else:
			meta=1
			return 1
	try:
		process_key(ch)
	except common.standard_errors,e:
		common.print_exception()
	meta=0
	return 1
