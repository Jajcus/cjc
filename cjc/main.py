#!/usr/bin/python -u

import libxml2
import time
import traceback
import sys,os
import select
import string
from types import StringType,UnicodeType
import locale

import pyxmpp

import ui

logfile=open("cjc.log","a")

class Exit(Exception):
	pass

global_commands={
	"exit": "cmd_quit",
	"quit": "cmd_quit",
	"set": "cmd_set",
	"connect": "cmd_connect",
	"disconnect": "cmd_disconnect",
	"save": "cmd_save",
	"load": "cmd_load",
	"redraw": "cmd_redraw",
	"info": "cmd_info",
}

class Application(pyxmpp.Client,ui.CommandHandler):
	def __init__(self):
		pyxmpp.Client.__init__(self)
		ui.CommandHandler.__init__(self,global_commands)
		self.plugin_dirs=["cjc/plugins"]
		self.plugins=[]
		self.event_handlers={}
		self.user_info={}
		self.info_handlers={}

	def load_plugin(self,path):
		self.info("Loading plugin: %s" % (path,))
		try:
			from plugin import PluginBase
			gl={"PluginBase":PluginBase}
			mod=execfile(path,gl)
			plugin=gl["Plugin"](self)
			self.plugins.append(plugin)
		except:
			self.print_exception()
			self.info("Plugin load failed")

	def load_plugins(self):
		for path in self.plugin_dirs:
			self.info("Loading plugins from %s" % (path,))
			try:
				d=os.listdir(path)
			except (OSError,IOError),e:
				self.error("Couldn't get plugin list: %s" % (e,))
				continue
			for f in d:
				if f[0]=="." or not f.endswith(".py"):
					continue
				self.load_plugin(os.path.join(path,f))

	def add_event_handler(self,event,handler):
		if not self.event_handlers.has_key(event):
			self.event_handlers[event]=[]
		self.event_handlers[event].append(handler)

	def send_event(self,event,arg=None):
		if not self.event_handlers.has_key(event):
			return
		for h in self.event_handlers[event]:
			try:
				h(event,arg)
			except:
				self.print_exception()
				self.info("Event handler failed")

	def add_info_handler(self,var,handler):
		self.info_handlers[var]=handler

	def command(self,cmd,args):
		if not ui.CommandHandler.command(self,cmd,args):
			self.error(u"Unknown command: %s" % (cmd,))

	def run(self,screen):
		self.screen=screen
		screen.set_default_command_handler(self)
		
		self.status_buf=ui.TextBuffer("Status")
		self.message_buf=ui.TextBuffer("Messages")
		self.roster_buf=ui.TextBuffer("Roster")
		self.test_buf=ui.TextBuffer("Test")

		self.top_bar=ui.StatusBar("CJC",{})
		self.status_window=ui.Window("Status",1)
		self.main_window=ui.Window("Main")
		self.command_line=ui.EditLine()
		self.bottom_bar=ui.StatusBar("CJC",{})
		self.roster_window=ui.Window("Roster",1)

		sp=ui.VerticalSplit(self.main_window,self.roster_window)
		sp=ui.HorizontalSplit(self.top_bar,self.status_window,
					sp,self.bottom_bar,
					self.command_line)
		screen.set_content(sp)
		screen.focus_window(self.main_window)
		
		self.status_window.set_buffer(self.status_buf)
		self.main_window.set_buffer(self.message_buf)
		self.roster_window.set_buffer(self.roster_buf)
		self.screen.update()
		
		ui.error=self.error
		ui.debug=self.debug
		ui.print_exception=self.print_exception
		
		self.load_plugins()

		self.cmd_load()

		try:
			self.loop(1)
		except Exit:
			pass

	def session_started(self):
		pyxmpp.Client.session_started(self)
		for p in self.plugins:
			try:
				p.session_started(self.stream)
			except:
				self.print_exception()
				self.info("Plugin call failed")
		self.stream.set_message_handler("error",self.message_error)
		self.stream.set_message_handler("normal",self.message_normal)

	def presence_error(self,stanza):
		fr=stanza.get_from()
		if self.get_user_info(fr):
			self.warning(u"Presence error from: "+fr.as_unicode())
		else:
			self.debug(u"Presence error from: "+fr.as_unicode())
		if fr.resource:
			self.set_user_info(fr,"presence",stanza.copy())
		else:	
			self.set_bare_user_info(fr,"presence",stanza.copy())
		
	def presence_available(self,stanza):
		fr=stanza.get_from()
		if self.get_user_info(fr):
			self.info(fr.as_unicode()+u" is available")
		else:
			self.debug(fr.as_unicode()+u" is available")
		self.set_user_info(fr,"presence",stanza.copy())
		
	def presence_unavailable(self,stanza):
		fr=stanza.get_from()
		if self.get_user_info(fr):
			self.info(fr.as_unicode()+u" is unavailable")
		else:
			self.debug(fr.as_unicode()+u" is unavailable")
		self.set_bare_user_info(fr,"presence",stanza.copy())
		resources=self.get_bare_user_info(fr,"resources")
		if resources.has_key(fr.resource):
			del resources[fr.resource]

	def message_error(self,stanza):
		self.warning(u"Message error from: "+stanza.get_from().as_unicode())
		
	def message_normal(self,stanza):
		self.info(u"Message from: "+stanza.get_from().as_unicode())
		self.message_buf.append_line(u"Message from: "+stanza.get_from().as_unicode())
		self.message_buf.append_line("Subject: "+stanza.get_subject())
		self.message_buf.append_line(stanza.get_body())
		self.message_buf.update(1)
	
	def cmd_quit(self,args):
		raise Exit

	def cmd_connect(self,args):
		if not self.jid:
			self.error(u"Can't connect - jid not given")
			return
		if None in (self.jid.node,self.jid.resource):
			self.error(u"Can't connect - jid is not full")
			return
		if not self.password:
			self.error(u"Can't connect - password not given")
			return
		self.info(u"Connecting...")
		self.connect()
	
	def cmd_disconnect(self,args):
		self.disconnect()
	
	def cmd_set(self,args):
		if not args:
			return
		var,val=args.split(None,1)
		if var.find("=")>0:
			var,val=args.split(" ",1)
		if var=="jid":
			self.jid=pyxmpp.JID(val)
		elif var=="server":
			self.server=str(val)
		elif var=="password":
			self.password=val
		elif var=="port":
			self.port=int(val)
		elif var=="auth_methods":
			self.auth_methods=val.split()
		elif var=="node":
			if not self.jid:
				if self.server:
					self.jid=pyxmpp.JID(val,self.server,"CJC")
				else:
					self.jid=pyxmpp.JID(val,"unknown","CJC")
			else:
				self.jid.set_node(val)
		elif var=="domain":
			if not self.jid:
				self.jid=pyxmpp.JID("unknown",val,"CJC")
			else:
				self.jid.set_domain(val)
		elif var=="resource":
			if not self.jid:
				self.jid=pyxmpp.JID("unknown",self.server,val)
			else:
				self.jid.set_resource(val)
		self.screen.update()

	def cmd_save(self,filename=".cjcrc"):
		try:
			f=file(".cjcrc","w")
		except IOError,e:
			self.status_buf.append("Couldn't open config file: "+str(e))
			return
		
		if self.jid:
			print >>f,"jid",self.jid.as_string()
		if self.server:
			print >>f,"server",self.server
		if self.password:
			print >>f,"password",self.password.encode("utf-8")
		if self.port:
			print >>f,"port",self.port
		if self.auth_methods:
			print >>f,"auth_methods",string.join(self.auth_methods)
			

	def cmd_load(self,filename=".cjcrc"):
		try:
			f=file(".cjcrc","r")
		except IOError,e:
			self.warning("Couldn't open config file: "+str(e))
			return
		
		for l in f.readlines():
			if not l:
				continue
			l=l.split("#",1)[0].strip()
			if not l:
				continue
			try:
				self.cmd_set(unicode(l,"utf-8"))
			except (ValueError,UnicodeError):
				self.warning(
					"Invalid config directive %r ignored" % (l,))
		f.close()

	def cmd_redraw(self,args):
		self.screen.redraw()
	
	def cmd_info(self,args):
		try:
			jid=pyxmpp.JID(args)
		except pyxmpp.JIDError:
			self.error("Invalid jabber id")
		uinf=self.get_user_info(jid)
		if uinf is None:
			self.info(u"I know nothing about "+jid.as_unicode())
			return
		self.info(u"Information known about %s:" % (jid.as_unicode(),))
		for k,v in uinf.items():
			if not self.info_handlers.has_key(k):
				continue
			r=self.info_handlers[k](k,v)
			if not r:
				continue
			self.info(u"  %s: %s" % r)
	
	def loop(self,timeout):
		while 1:
			fdlist=[sys.stdin.fileno()]
			if self.stream and self.stream.socket:
				fdlist.append(self.stream.socket)
			id,od,ed=select.select(fdlist,[],fdlist,timeout)
			if sys.stdin.fileno() in id:
				while self.screen.keypressed():
					pass
			if self.stream and self.stream.socket in id:
				self.stream.process()
			if len(id)==0:
				self.idle()

	def get_bare_user_info(self,jid,var=None):
		if jid.resource:
			jid=jid.bare()
		ujid=jid.as_unicode()
		if not self.user_info.has_key(ujid):
			return None
		if var is None:
			return self.user_info[ujid]
		return self.user_info[ujid].get(var)

	def get_user_info(self,jid,var=None):
		uinf=self.get_bare_user_info(jid)
		if uinf is None or not uinf.has_key("resources"):
			return None
		if uinf["resources"].has_key(jid.resource):
			uinf.update(uinf["resources"][jid.resource])
		if var is None:
			return uinf
		return uinf.get(var)

	def set_user_info(self,jid,var,val):
		bare=jid.bare()
		ubare=bare.as_unicode()
		if self.user_info.has_key(ubare):
			uinf=self.user_info[ubare]
		else:
			uinf={"resources":{},"jid":bare}
			self.user_info[ubare]=uinf

		if uinf["resources"].has_key(jid.resource):
			fuinf=uinf["resources"][jid.resource]
		else:
			fuinf={"jid":jid}
			uinf["resources"][jid.resource]=fuinf
		fuinf[var]=val
	
	def set_bare_user_info(self,jid,var,val):
		bare=jid.bare()
		ubare=bare.as_unicode()
		if self.user_info.has_key(ubare):
			uinf=self.user_info[ubare]
		else:
			uinf={"jid":bare}
			self.user_info[ubare]=uinf
		uinf[var]=val

	def roster_updated(self):
		self.info("Got roster")
		self.roster_buf.clear()
		for group in self.roster.groups():
			if group:
				self.roster_buf.append(group+u":\n","default")
			for item in self.roster.items_by_group(group):
				jid=item.jid()
				name=item.name()
				if not name:
					name=jid.as_unicode()
				if jid.resource:
					self.set_user_info(jid,"rostername",name)
				else:
					self.set_bare_user_info(jid,"rostername",name)
				self.roster_buf.append_line(" "+name)
		self.roster_buf.redraw()
		self.send_event("roster updated")

	def idle(self):
		pyxmpp.Client.idle(self)
		self.send_event("idle")
			
	def print_exception(self):
		traceback.print_exc(file=self.status_buf)
			
	def error(self,s):
		if logfile:
			print >>logfile,time.asctime(),"ERROR",s.encode("utf-8","replace")
		self.status_buf.append_line(s,"error")
		self.status_buf.update(1)
		
	def warning(self,s):
		if logfile:
			print >>logfile,time.asctime(),"WARNING",s.encode("utf-8","replace")
		self.status_buf.append_line(s,"warning")
		self.status_buf.update(1)
		
	def info(self,s):
		if logfile:
			print >>logfile,time.asctime(),"INFO",s.encode("utf-8","replace")
		self.status_buf.append_line(s,"info")
		self.status_buf.update(1)

	def debug(self,s):
		if logfile:
			print >>logfile,time.asctime(),"DEBUG",s.encode("utf-8","replace")
		#self.status_buf.append_line(s,"debug")
		#self.status_buf.update(1)


def main():
	locale.setlocale(locale.LC_ALL,"")
	app=Application()
	try:
		screen=ui.init()
		app.run(screen)
	finally:
		ui.deinit()
