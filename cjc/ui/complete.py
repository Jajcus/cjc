import re

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
		if len(matches)==1:
			return head,matches
		if not matches:
			return "",[]
		longest=min([len(m[0]) for m in matches])
		l=len(word)
		if longest==l:
			return head,matches
		longest_match=matches[0][0][:longest]
		for m in matches[1:]:
			common.debug("longest=%r longest_match=%r" % (longest,longest_match))
			while longest>l and m[0][:longest]!=longest_match:
				longest_match=longest_match[:-1]
				longest-=1
		if longest==l:
			return head,matches
		return head,[[longest_match,0]]

class GenericCompletion(Completion):
	def __init__(self,words=[]):
		self.words=words
	def complete(self,word):
		matches=[]
		for w in self.words:
			if w.startswith(word):
				matches.append([w,1])
		return self.make_result("",word,matches)

GenericCompletion().register("text")

unfinished_quoted_arg_re=re.compile(r'^"(?P<arg>([^"]|(\\"))*)',re.UNICODE)

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
		return None,None,None,0
	if not cmd.hints:
		common.debug("No completion hints for command: "+`cmd`)
		return None,None,None,0
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
				return None,None,None,0
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
			return None,None,None,0
	if hi>=len(cmd.hints):
		common.debug("More args than hints")
		return None,None,None,0
	if args.args:
		head=s[:-len(args.args)]
		if args.args.startswith('"'):
			word=cmdtable.unquote(args.args[1:])
		else:
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
			return head,word,compl,0
		else:
			while (hi<len(cmd.hints) 
				and cmd.hints[hi].startswith("-")):
				hi+=1
			if hi<len(cmd.hints):
				hint=cmd.hints[hi]
			else:
				common.debug("More args than hints")
				return None,None,None,0
	if hint=="opaque":
		return None,None,None,0
	elif not completions.has_key(hint):
		common.debug("Completion not found: "+`hint`)
		return None,None,None,0
	compl=completions[hint]
	if hint!="text":
		return head,word,compl,1
	else:
		return head,word,compl,0

need_quote_re=re.compile('[ \t\\"]')

def complete(s):
	if s.startswith("/") and completions.has_key("command"):
		if " " not in s and "\t" not in s:
			word=s[1:]
			head=s[:1]
			compl=completions["command"]
			quote=0
		else:
			head,word,compl,quote=complete_command_args(s)
			common.debug("head=%r word=%r compl=%r" % (head,word,compl))
			if head is None:
				return s,[]
	else:
		head=""
		if s:
			word=s.split()[-1]
		else:
			word=""
		quote=0
		compl=GenericCompletion()
	
	chead,cret=compl.complete(word)

	common.debug("head=%r chead=%r cret=%r quote=%r" % (head,chead,cret,quote))

	if quote:
		if chead:
			if need_quote_re.search(chead):
				need_quote=1
			else:
				need_quote=0
				for r in cret:
					if need_quote_re.search(r[0][0]):
						need_quote=1
						break
			if need_quote:
				chead='"'+cmdtable.quote(chead)
				for i in range(len(cret)):
					if cret[i][1]:
						cret[i][0]=cmdtable.quote(cret[i][0])+'"'
					else:
						cret[i][0]=cmdtable.quote(cret[i][0])
		else:
			for i in range(len(cret)):
				if not need_quote_re.search(cret[i][0]):
					continue
				if cret[i][1]:
					cret[i][0]='"'+cmdtable.quote(cret[i][0])+'"'
				else:
					cret[i][0]='"'+cmdtable.quote(cret[i][0])
	
	ret=[]
	for r in cret:
		if r[1]:
			ret.append(r[0]+" ")
		else:
			ret.append(r[0])
	return head+chead,ret
