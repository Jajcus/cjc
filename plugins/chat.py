import string
from cjc import ui
import pyxmpp

class Conversation:
	def __init__(self,plugin,myname,peer,thread=None):
		self.plugin=plugin
		self.myname=myname
		self.peer=peer
		self.peername=peer.node
		if thread:
			self.thread=thread
			self.thread_inuse=1
		else:
			plugin.last_thread+=1
			self.thread="thread-%i" % (plugin.last_thread,)
			self.thread_inuse=0
		self.buffer=ui.TextBuffer(u"Chat with %s" % (peer.as_unicode(),))
		self.buffer.user_input=self.user_input
		self.add_info(u"Chat with %s started" % (peer.as_unicode(),))
		self.buffer.register_commands({"me": self.cmd_me})
		
	def add_received(self,s):
		if s.startswith(u"/me "):
			self.add_info("%s %s" % (self.peername,s[4:]))
			return
		self.buffer.append("<%s> " % (self.peername,),"warning")
		self.buffer.append_line(s,"default")
		self.buffer.update()
		
	def add_sent(self,s):
		if s.startswith(u"/me "):
			self.add_info("%s %s" % (self.myname,s[4:]))
			return
		self.buffer.append("<%s> " % (self.myname,),"error")
		self.buffer.append_line(s,"default")
		self.buffer.update()

	def add_info(self,s):
		self.buffer.append_line("* %s" % (s,),"warning")
		self.buffer.update()

	def user_input(self,s):
		if not s:
			return 0
		m=pyxmpp.Message(to=self.peer,type="chat",body=s,thread=self.thread)
		self.plugin.cjc.stream.send(m)
		self.add_sent(s)
		return 1

	def cmd_me(self,arg):
		if not arg:
			return 1
		self.user_input(u"/me "+arg)
		return 1

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		self.conversations={}
		self.last_thread=0
		app.register_commands({"chat": self.cmd_chat})

	def cmd_chat(self,args):
		if not args:
			self.error("/chat without arguments")
			return
			
		if not self.cjc.stream:
			self.error("Connect first!")
			return
			
		args=args.split(None,1)
		if args[0].find("*")>=0:
			try:
				peer=pyxmpp.JID(args[0])
			except pyxmpp.JIDError:
				peer=None
		else:
			peer=None

		if peer is None and self.cjc.roster:
			try:
				ritems=self.cjc.roster.items_by_name(args[0])
			except KeyError:
				self.error("%s not found in roster" % (args[0],))
				return
			if ritems:
				if len(ritems)>1:
					self.error("ambiguous user name")
					return
				else:
					peer=ritems[0].jid()

		conversation=Conversation(self,self.cjc.jid.node,peer)
		key=peer.bare().as_unicode()
		if self.conversations.has_key(key):
			self.conversations[key].append(conversation)
		else:
			self.conversations[key]=[conversation]

		if len(args)==2:
			conversation.user_input(args[1])
			
		self.cjc.screen.display_buffer(conversation.buffer)

	def session_started(self,stream):
		self.cjc.stream.set_message_handler("chat",self.message_chat)

	def message_chat(self,stanza):
		fr=stanza.get_from()
		thread=stanza.get_thread()
		subject=stanza.get_subject()
		body=stanza.get_body()
		if body is None:
			body=u""
		if subject:
			body=u"%s: %s" % (subject,body)

		key=fr.bare().as_unicode()

		conv=None
		if self.conversations.has_key(key):
			convs=self.conversations[key]
			for c in convs:
				if not thread and (not c.thread or not c.thread_inuse):
					conv=c
					break
				if thread and thread==c.thread:
					conv=c
					break
			if conv and conv.thread and not thread:
				conv.thread=None
			elif conv and thread:
				conv.thread_inuse=1

		if not conv:
			conv=Conversation(self,self.cjc.stream.jid.node,fr,thread)
			if self.conversations.has_key(key):
				self.conversations[key].append(conv)
			else:
				self.conversations[key]=[conv]
			self.cjc.screen.display_buffer(conv.buffer)
		
		conv.add_received(body)
