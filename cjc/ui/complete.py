
import cmdtable

completions={}

class Completion:
	def __init__(self):
		pass
	def register(self,*args):
		for name in args:
			completions[name]=self
	def complete(self,word):
		return []
	def make_result(self,word,matches):
		longest=min([len(m) for m in matches])
		l=len(word)
		if longest==l:
			return matches
		longest_match=matches[0][:longest]
		for m in matches[1:]:
			while longest>l and m[:longest]!=longest_match:
				longest_match=longest_match[:-1]
				longest-=1
		if longest==l:
			return matches
		return [longest_match]

class CommandCompletion(Completion):
	def complete(self,word):
		matches=[]
		for t in cmdtable.command_tables:
			for cmd in t.get_commands():
				if cmd.name.startswith(word) and cmd not in matches:
					matches.append(cmd)
		if len(matches)==1:
			return [matches[0].name+" "]
		if not matches:
			return []
		return self.make_result(word,[cmd.name+" " for cmd in matches])

CommandCompletion().register("command")

class GenericCompletion(Completion):
	pass

GenericCompletion().register("text")

def complete(s):
	if s.startswith("/"):
		word=s[1:]
		head=s[:1]
		compl=CommandCompletion()
	else:
		head=""
		if s:
			word=s.split()[-1]
		else:
			word=""
		compl=GenericCompletion()
		
	ret=compl.complete(word)
	return head,ret
