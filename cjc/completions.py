import ui
import ui.cmdtable
import common

class UserCompletion(ui.Completion):
	def __init__(self,app):
		self.app=app
	def complete(self,word):
		common.debug("UserCompletion.complete(self,%r)" % (word,))
		matches=[]
		if self.app.roster:
			for ri in self.app.roster.items():
				name=ri.name()
				if word==name:
					items=self.app.roster.items_by_name(name)
					if len(items)>1:
						for i in items:
							matches.append(i.jid().as_unicode())
						continue
				if name is None:
					name=ri.jid().as_unicode()
				if (name.startswith(word) 
						and name not in matches 
						and ri.jid().as_unicode() not in matches): 
					matches.append(name+" ")
		for jid in self.app.user_info.keys():
			if self.app.roster:
				try:
					name=self.app.roster.item_by_jid(jid)
					if name in matches:
						continue
				except KeyError:
					pass
			if jid.startswith(word) and jid not in matches:
				matches.append(jid+" ")
		return self.make_result("",word,matches)

class SettingCompletion(ui.Completion):
	def __init__(self,app):
		self.app=app
	def complete(self,word):
		common.debug("SettingCompletion.complete(self,%r)" % (word,))
		if "." in word:
			return self.complete_plugin(word)
		matches=[]
		for p in self.app.plugins.keys():
			if p.startswith(word):
				matches.append(p+".")
		for s in self.app.settings.keys():
			if s.startswith(word) and s not in matches:
				matches.append(s+" ")
		common.debug("word=%r matches=%r" % (word,matches))
		return self.make_result("",word,matches)
	def complete_plugin(self,word):
		if word.startswith("."):
			obj=self.app
			head="."
			word=word[1:]
		else:
			d=word.find(".")
			plugin=word[0:d]
			if not self.app.plugins.has_key(plugin):
				return "",[]
			obj=self.app.plugins[plugin]
			head=plugin+"."
			word=word[d+1:]
		matches=[]
		for s in obj.settings.keys():
			if s.startswith(word) and s+" " not in matches:
				matches.append(s+" ")
		return self.make_result(head,word,matches)

class CommandCompletion(ui.Completion):
	def __init__(self,app):
		self.app=app
	def complete(self,word):
		matches=[]
		for a in self.app.aliases.keys():
			if a.startswith(word):
				matches.append(a+" ")
		for t in ui.cmdtable.command_tables:
			if not t.active:
				continue
			for cmd in t.get_command_names():
				if cmd.startswith(word) and cmd not in matches:
					matches.append(cmd+" ")
		return self.make_result("",word,matches)
