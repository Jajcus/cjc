
from types import StringType,IntType,UnicodeType
import re

import common

quoted_arg_re=re.compile(r'^"(?P<arg>([^"]|(\\"))*)"(?P<rest>.*)$',re.UNICODE)
need_quote_re=re.compile(r'[ \"\\\n\t]',re.UNICODE)
quote_re=re.compile(r'\\(.)',re.UNICODE)

def quote(s):
	s=s.replace(u'\\',u'\\\\')
	s=s.replace(u'"',u'\\"')
	s=s.replace(u'\t',u'\\t')
	s=s.replace(u'\n',u'\\n')
	return s

def unquote(s):
	s=s.replace(u'\\t',u'\t')
	s=s.replace(u'\\n',u'\n')
	s=quote_re.sub(ur"\1",s)
	return s

class CommandHandler:
	def __init__(self,d=None,object=None):
		self.command_info={}
		self.command_aliases={}
		if d:
			self.register_commands(d,object)

	def register_commands(self,d,object=None):
		if object is None:
			object=self
		for name,info in d.items():
			if type(info) is StringType: # alias
				self.command_aliases[name]=info
				continue
			handler,usage,descr=info
			if type(handler) is StringType:
				handler=getattr(object,handler)
			if not callable(handler):
				raise TypeError,"Bad command handler"
			self.command_info[name]=(handler,usage,descr)

	def commands(self):
		return self.command_info.keys()+self.command_aliases.keys()

	def get_command_info(self,cmd):
		if self.command_aliases.has_key(cmd):
			cmd=self.command_aliases[cmd]
		return self.command_info[cmd]

	def command(self,cmd,args):
		if self.command_aliases.has_key(cmd):
			cmd=self.command_aliases[cmd]

		if self.command_info.has_key(cmd):
			try:
				self.command_info[cmd][0](args)
			except KeyboardInterrupt:
				raise
			except CommandError,e:
				common.error(u"Command '%s' failed: %s" % (cmd,e))
			except common.standard_errors,e:
				common.error("Comand execution failed: "+str(e))
				common.print_exception()
			return 1
		else:
			return 0


class CommandError(ValueError):
	pass

class CommandArgs:
	def __init__(self,args=None):
		if isinstance(args,CommandArgs):
			self.args=args.args
		else:
			self.args=args

	def all(self):
		args=self.args
		self.args=""
		return args

	def finish(self):
		if self.args:
			self.args=self.args.strip()
		if self.args:
			raise CommandError,"Too many arguments"

	def get(self,remove=0):
		if not self.args:
			return None
		args=self.args.lstrip()
		if not args:
			return None
		if not args.startswith('"'):
			sp=self.args.split(None,1)
			if remove:
				if len(sp)>1:
					self.args=sp[1]
				else:
					self.args=None
			return sp[0]
		m=quoted_arg_re.match(args)
		if not m:
			raise CommandError,"Command arguments syntax error"
		arg=unquote(m.group("arg"))
		if remove:
			self.args=m.group("rest").lstrip()
		return arg
	
	def shift(self):
		return self.get(1)
		
	def add_quoted(self,s):
		if not self.args:
			self.args=""
		else:
			self.args+=" "
		if need_quote_re.search(s) or not s:
			self.args+='"%s"' % (quote(s),)
		else:
			self.args+=s

	def add_unquoted(self,s):
		if not self.args:
			self.args=""
		else:
			self.args+=" "
		self.args+=s
