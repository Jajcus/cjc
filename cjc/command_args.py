
import re

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

	def shift(self):
		if not self.args:
			return None
		args=self.args.lstrip()
		if not args:
			return None
		if not args.startswith('"'):
			sp=self.args.split(None,1)
			if len(sp)>1:
				ret,self.args=sp
				return ret
			self.args=None
			return sp[0]
		m=quoted_arg_re.match(args)
		if not m:
			raise CommandError,"Command arguments syntax error"
		arg=unquote(m.group("arg"))
		self.args=m.group("rest").lstrip()
		return arg
		
	def add_quoted(self,s):
		if not self.args:
			self.args=""
		else:
			self.args+=" "
		if need_quote_re.search(s):
			self.args+='"%s"' % (quote(s),)
		else:
			self.args+=s

	def add_unquoted(self,s):
		if not self.args:
			self.args=""
		else:
			self.args+=" "
		self.args+=s
