import string
from cjc import ui
from cjc.plugin import PluginBase
import pyxmpp
import curses

theme_attrs=(
	("chat.me", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
	("chat.peer", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
	("chat.info", curses.COLOR_GREEN,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
	("chat.started","[%(T:timestamp)s] %[chat.info]* Chat with %(peer)s started\n"),
	("chat.me","[%(T:timestamp)s] %[chat.me]<%(J:me:nick)s>%[] %(msg)s\n"),
	("chat.peer","[%(T:timestamp)s] %[chat.peer]<%(J:peer:nick)s>%[] %(msg)s\n"),
	("chat.action","[%(T:timestamp)s] %[chat.info]* %(J:jid:nick)s %(msg)s\n"),
	("chat.descr","Chat with %(J:peer:full)s [%(J:peer:show)s] %(J:peer:status)s"),
)

class Conversation:
	def __init__(self,plugin,me,peer,thread=None):
		self.plugin=plugin
		self.me=me
		self.peer=peer
		if thread:
			self.thread=thread
			self.thread_inuse=1
		else:
			plugin.last_thread+=1
			self.thread="thread-%i" % (plugin.last_thread,)
			self.thread_inuse=0
		self.fparams={
			"peer":self.peer,
			"jid":self.me,
		}
		self.buffer=ui.TextBuffer(plugin.cjc.theme_manager,self.fparams,"chat.descr")
		self.buffer.user_input=self.user_input
		self.buffer.append_themed("chat.started",self.fparams)
		self.buffer.update()
		self.buffer.register_commands({"me": (self.cmd_me,
							"/me text",
							"Sends /me text")
						,
						"close": (self.cmd_close,
							"/close",
							"Closes current chat buffer")
						})
		
	def add_msg(self,s,format,who):
		self.fparams["jid"]=who
		if s.startswith(u"/me "):
			self.fparams["msg"]=s[4:]
			self.buffer.append_themed("chat.action",self.fparams)
			self.buffer.update()
			return
		self.fparams["msg"]=s
		self.buffer.append_themed(format,self.fparams)
		self.buffer.update()

	def add_sent(self,s):
		self.add_msg(s,"chat.me",self.me)
		
	def add_received(self,s):
		self.add_msg(s,"chat.peer",self.peer)
		
	def user_input(self,s):
		if not s:
			return 0
		if not self.plugin.cjc.stream:
			self.buffer.append_themed("error","Not connected")
			self.buffer.update()
			return 0
		m=pyxmpp.Message(to=self.peer,type="chat",body=s,thread=self.thread)
		self.plugin.cjc.stream.send(m)
		self.add_sent(s)
		return 1

	def cmd_me(self,args):
		if not args:
			return 1
		self.user_input(u"/me "+args.all())
		return 1

	def cmd_close(self,args):
		args.finish()
		key=self.peer.bare().as_unicode()
		if self.plugin.conversations.has_key(key):
			l=self.plugin.conversations[key]
			if self in l:
				l.remove(self)
		self.buffer.close()

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		self.conversations={}
		self.last_thread=0
		app.theme_manager.set_default_attrs(theme_attrs)
		app.theme_manager.set_default_formats(theme_formats)
		app.register_commands({"chat": (self.cmd_chat,
					"/chat nick|jid [text]",
					"Start chat with given user")
					})
		app.add_event_handler("presence changed",self.ev_presence_changed)

	def cmd_chat(self,args):
		peer=args.shift()
		if not peer:
			self.error("/chat without arguments")
			return
			
		if not self.cjc.stream:
			self.error("Connect first!")
			return
			
		peer=self.cjc.get_user(peer)
		if peer is None:
			return

		conversation=Conversation(self,self.cjc.jid,peer)
		key=peer.bare().as_unicode()
		if self.conversations.has_key(key):
			self.conversations[key].append(conversation)
		else:
			self.conversations[key]=[conversation]

		if args.all():
			conversation.user_input(args.all())
			
		self.cjc.screen.display_buffer(conversation.buffer)

	def ev_presence_changed(self,event,arg):
		key=arg.bare().as_unicode()
		if not self.conversations.has_key(key):
			return
		for conv in self.conversations[key]:
			if conv.peer==arg or conv.peer==arg.bare():
				conv.buffer.update()

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
			conv=Conversation(self,self.cjc.jid,fr,thread)
			if self.conversations.has_key(key):
				self.conversations[key].append(conv)
			else:
				self.conversations[key]=[conv]
			self.cjc.screen.display_buffer(conv.buffer)
		
		conv.add_received(body)
