import string
import curses
import os

import pyxmpp
from cjc import ui
from cjc.plugin import PluginBase
from cjc import common

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
			self.thread="chat-thread-%i" % (plugin.last_thread,)
			self.thread_inuse=0
		self.fparams={
			"peer":self.peer,
			"jid":self.me,
		}
		self.buffer=ui.TextBuffer(plugin.cjc.theme_manager,self.fparams,"chat.descr",
				"chat buffer",self)
		self.buffer.user_input=self.user_input
		self.buffer.append_themed("chat.started",self.fparams)
		self.buffer.update()

	def change_peer(self,peer):
		self.peer=peer
		self.fparams["peer"]=peer
		self.buffer.update_info(self.fparams)
		
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
		if not self.plugin.cjc.stream:
			self.buffer.append_themed("error","Not connected")
			self.buffer.update()
			return 0
		if self.plugin.settings.get("log_filename"):
			self.plugin.log_message("out",self.me,self.peer,None,s,self.thread)
		m=pyxmpp.Message(to=self.peer,type="chat",body=s,thread=self.thread)
		self.plugin.cjc.stream.send(m)
		self.add_sent(s)
		return 1

	def error(self,stanza):
		err=stanza.get_error()
		emsg=err.get_message()
		msg="Error"
		if emsg:
			msg+=": %s" % emsg
		etxt=err.get_text()
		if etxt:
			msg+=" ('%s')" % etxt
		self.buffer.append_themed("error",msg)
		self.buffer.update()

	def cmd_me(self,args):
		if not args:
			return 1
		args=args.all()
		if not args:
			return 1
		self.user_input(u"/me "+args)
		return 1

	def cmd_close(self,args):
		args.finish()
		key=self.peer.bare().as_unicode()
		if self.plugin.conversations.has_key(key):
			l=self.plugin.conversations[key]
			if self in l:
				l.remove(self)
		self.buffer.close()
		return 1

ui.CommandTable("chat buffer",50,(
	ui.Command("me",Conversation.cmd_me,
		"/me text",
		"Sends /me text",
		("text",)),
	ui.Command("close",Conversation.cmd_close,
		"/close",
		"Closes current chat buffer"),
	)).install()

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		self.conversations={}
		self.last_thread=0
		app.theme_manager.set_default_attrs(theme_attrs)
		app.theme_manager.set_default_formats(theme_formats)
		self.available_settings={
			"log_filename": ("Where messages should be logged to",(str,None)),
			"log_format_in": ("Format of incoming message log entries",(str,None)),
			"log_format_out": ("Format of outgoing message log entries",(str,None)),
			}
		self.settings={
				"log_filename": "%($HOME)s/.cjc/logs/chats/%(J:peer:bare)s",
				"log_format_in": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
				"log_format_out": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
				}
		app.add_event_handler("presence changed",self.ev_presence_changed)
		ui.activate_cmdtable("chat",self)

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

		text=args.all()
		if text:
			conversation.user_input(text)
			
		self.cjc.screen.display_buffer(conversation.buffer)

	def ev_presence_changed(self,event,arg):
		key=arg.bare().as_unicode()
		if not self.conversations.has_key(key):
			return
		for conv in self.conversations[key]:
			if conv.peer==arg or conv.peer==arg.bare():
				conv.buffer.update_info(conv.fparams)

	def session_started(self,stream):
		self.cjc.stream.set_message_handler("chat",self.message_chat)
		self.cjc.stream.set_message_handler("error",self.message_error,None,90)

	def message_error(self,stanza):
		fr=stanza.get_from()
		thread=stanza.get_thread()
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
			return 0

		conv.error(stanza)
		return 1
	
	def message_chat(self,stanza):
		fr=stanza.get_from()
		thread=stanza.get_thread()
		subject=stanza.get_subject()
		body=stanza.get_body()
		if body is None:
			body=u""
		if subject:
			body=u"%s: %s" % (subject,body)

		if self.settings.get("log_filename"):
			self.log_message("in",fr,self.cjc.jid,subject,body,thread)
			
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
		else:
			if fr!=conv.peer:
				conv.change_peer(fr)
		conv.add_received(body)
		return 1

	def log_message(self,dir,sender,recipient,subject,body,thread):
		format=self.settings["log_format_"+dir]
		filename=self.settings["log_filename"]
		d={
			"sender": sender,
			"recipient": recipient,
			"subject": subject,
			"body": body,
			"thread": thread
			}
		if dir=="in":
			d["peer"]=sender
		else:
			d["peer"]=recipient
		filename=self.cjc.theme_manager.substitute(filename,d)
		s=self.cjc.theme_manager.substitute(format,d)
		try:
			dirname=os.path.split(filename)[0]
			if dirname and not os.path.exists(dirname):
				os.makedirs(dirname)
			f=open(filename,"a")
			try:
				f.write(s.encode("utf-8","replace"))
			finally:
				f.close()
		except (IOError,OSError),e:
			self.cjc.error("Couldn't write chat log: "+str(e))

ui.CommandTable("chat",51,(
	ui.Command("chat",Plugin.cmd_chat,
		"/chat nick|jid [text]",
		"Start chat with given user",
		("user","text")),
	)).install()
