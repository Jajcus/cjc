
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
			return [matches[0].name+" "]
		if not matches:
			return []
		return self.make_result("",word,[cmd.name+" " for cmd in matches])

CommandCompletion().register("command")

class GenericCompletion(Completion):
	pass

GenericCompletion().register("text")

def complete(s):
	if s.startswith("/"):
		sp=s.split(None,1)
		if len(sp)==1 and not s[-1].isspace():
			word=s[1:]
			head=s[:1]
			compl=CommandCompletion()
		else:
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
				return s,[]
			if not cmd.hints:
				common.debug("No completion hints for command: "+`cmd`)
				return s,[]
			hi=0
			if not args or args[-1].isspace():
				lastarg=""
			else:
				lastarg=args.split()[-1]
			args=cmdtable.CommandArgs(args)
			try:
				while args.args and len(args.args)>len(lastarg):
					arg=args.shift()
					if arg is None:
						common.debug("Last argument reached")
						return s,[]
					hi+=1
			except cmdtable.CommandError:
				if not unfinished_quoted_arg_re.match(args.args):
					common.debug("Argument parse error not on open quotes")
					return s,[]
			if hi>=len(cmd.hints):
				common.debug("More args than hints")
				return s,[]
			if args.args:
				head=s[:-len(args.args)]
				word=args.args
			else:
				head=s
				word=""
			hint=cmd.hints[hi]
			if hint=="opaque":
				return s,[]
			elif not completions.has_key(hint):
				common.debug("Completion not found: "+`hint`)
				return s,[]
			compl=completions[hint]
			common.debug("head=%r word=%r compl=%r" % (head,word,compl))
	else:
		head=""
		if s:
			word=s.split()[-1]
		else:
			word=""
		compl=GenericCompletion()
		
	chead,ret=compl.complete(word)
	return head+chead,ret
