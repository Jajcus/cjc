
import cmdtable
from cjc import common

completions={}

class Completion:
	def __init__(self):
		pass
	def register(self,*args):
		for name in args:
			completions[name]=self
	def complete(self,word):
		return "",[]
	def make_result(self,head,word,matches):
		longest=min([len(m) for m in matches])
		l=len(word)
		if longest==l:
			return head,matches
		longest_match=matches[0][:longest]
		for m in matches[1:]:
			while longest>l and m[:longest]!=longest_match:
				longest_match=longest_match[:-1]
				longest-=1
		if longest==l:
			return head,matches
		return head,[longest_match]

class CommandCompletion(Completion):
	def complete(self,word):
		matches=[]
		for t in cmdtable.command_tables:
			if not t.active:
				continue
			for cmd in t.get_commands():
				if cmd.name.startswith(word) and cmd not in matches:
					matches.append(cmd)
		if len(matches)==1:
			return "",[matches[0].name+" "]
		if not matches:
			return "",[]
		return self.make_result("",word,[cmd.name+" " for cmd in matches])

CommandCompletion().register("command")

class GenericCompletion(Completion):
	def __init__(self,words=[]):
		self.words=words
	def complete(self,word):
		matches=[]
		for w in self.words:
			if w.startswith(word):
				matches.append(w+" ")
		if len(matches)==1:
			return "",matches
		if not matches:
			return "",[]
		return self.make_result("",word,matches)

GenericCompletion().register("text")

def complete_command_args(s):
	sp=s.split(None,1)
	if len(sp)>1:
		cmd,args=sp
	else:
		cmd,args=sp[0],""
	common.debug("Command args completion: "+`(cmd,args)`)
	cmd=cmd[1:]
	try:
		cmd=cmdtable.lookup_command(cmd,1)
	except KeyError:
		common.debug("Command not found: "+`cmd`)
		return None,None,None
	if not cmd.hints:
		common.debug("No completion hints for command: "+`cmd`)
		return None,None,None
	hi=0
	if not args or args[-1].isspace():
		lastarg=""
	else:
		lastarg=args.split()[-1]
	option=None
	option_arg=None
	args=cmdtable.CommandArgs(args)
	try:
		while args.args and len(args.args)>len(lastarg):
			arg=args.shift()
			if arg is None:
				common.debug("Last argument reached")
				return None,None,None
			if option:
				common.debug("option=%r, option_arg=%r arg=%r" % (option,option_arg,arg))
				option_arg+=1
				if option_arg<len(option):
					common.debug("complete: %r is %r" 
							% (arg, option[option_arg]))
					continue
				option=None
			if arg.startswith("-"):
				hi1=hi
				while (hi1<len(cmd.hints) and cmd.hints[hi1].startswith("-")):
					hint_sp=cmd.hints[hi1].split()
					if hint_sp[0]==arg:
						option=hint_sp
						option_arg=0
						break
				if option:
					common.debug("complete: %r is %r" 
							% (arg,option[option_arg]))
					continue
			elif hi<len(cmd.hints) and cmd.hints[hi].startswith("-"):
				while (hi<len(cmd.hints) and cmd.hints[hi].startswith("-")):
					hi+=1
			if hi<len(cmd.hints):
				common.debug("complete: %r is %r" % (arg,cmd.hints[hi]))
			hi+=1
	except cmdtable.CommandError:
		if not unfinished_quoted_arg_re.match(args.args):
			common.debug("Argument parse error not on open quotes")
			return None,None,None
	if hi>=len(cmd.hints):
		common.debug("More args than hints")
		return None,None,None
	if args.args:
		head=s[:-len(args.args)]
		word=args.args
	else:
		head=s
		word=""
		
	if option:
		option_arg+=1
		if option_arg<len(option):
			hint=option[option_arg]
		else:
			hint=cmd.hints[hi]
	else:
		hint=cmd.hints[hi]
		
	if hint.startswith("-"):
		if word.startswith("-"):
			options=[]
			while (hi<len(cmd.hints) 
				and cmd.hints[hi].startswith("-")):
				options.append(cmd.hints[hi].split()[0])
				hi+=1
			compl=GenericCompletion(options)
			return head,word,compl
		else:
			while (hi<len(cmd.hints) 
				and cmd.hints[hi].startswith("-")):
				hi+=1
			if hi<len(cmd.hints):
				hint=cmd.hints[hi]
			else:
				common.debug("More args than hints")
				return None,None,None
	if hint=="opaque":
		return None,None,None
	elif not completions.has_key(hint):
		common.debug("Completion not found: "+`hint`)
		return None,None,None
	compl=completions[hint]
	return head,word,compl

def complete(s):
	if s.startswith("/"):
		if " " not in s and "\t" not in s:
			word=s[1:]
			head=s[:1]
			compl=CommandCompletion()
		else:
			head,word,compl=complete_command_args(s)
			common.debug("head=%r word=%r compl=%r" % (head,word,compl))
			if head is None:
				return s,[]
	else:
		head=""
		if s:
			word=s.split()[-1]
		else:
			word=""
		compl=GenericCompletion()
		
	chead,ret=compl.complete(word)
	return head+chead,ret
