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
import version

logfile=open("cjc.log","a")

class Exit(Exception):
	pass

global_commands={
	# command: alias
	#    or
	# command: (handler, usage, description)
	#
	# handler may be method name or any callable
	"exit": ("cmd_quit",
		"/exit",
		"Exit from CJC"),
	"quit": "exit",
	"set": ("cmd_set",
		"/set [setting] [value]",
		"Change settings"),
	"connect": ("cmd_connect",
		"/connect",
		"Connect to a Jabber server"),
	"disconnect": ("cmd_disconnect",
		"/disconnect",
		"Disconnect from a Jabber server"),
	"save": ("cmd_save",
		"/save [filename]",
		"Save current settings to a file (default: .cjcrc)"),
	"load": ("cmd_load",
		"/load [filename]",
		"Load settings from a file (default: .cjcrc)"),
	"redraw": ("cmd_redraw",
		"/redraw",
		"Redraw screen"),
	"info": ("cmd_info",
		"/info jid",
		"Show information known about given jid"),
	"help": ("cmd_help",
		"/help [command]",
		"Show simple help"),
}

global_settings={
	"jid": ("Jabber ID to use.",pyxmpp.JID,".jid"),
	"password": ("Jabber ID to use.",unicode,".password"),
	"port": ("Port number to connect to",int,".port"),
	"server": ("Server address to connect to",str,".server"),
	"auth_methods": ("Authentication methods to use (e.g. 'sasl:DIGEST-MD5 digest')",list,".auth_methods"),
}

class Application(pyxmpp.Client,ui.CommandHandler):
	def __init__(self):
		pyxmpp.Client.__init__(self)
		ui.CommandHandler.__init__(self,global_commands)
		self.settings={}
		self.available_settings=global_settings
		self.plugin_dirs=["cjc/plugins"]
		self.plugins={}
		self.event_handlers={}
		self.user_info={}
		self.info_handlers={}

	def load_plugin(self,name):
		self.info("  %s" % (name,))
		try:
			mod=__import__(name)
			plugin=mod.Plugin(self)
			self.plugins[name]=plugin
		except:
			self.print_exception()
			self.info("Plugin load failed")

	def load_plugins(self):
		sys_path=sys.path
		for path in self.plugin_dirs:
			self.info("Loading plugins from %s:" % (path,))
			sys.path=[path]+sys_path
			try:
				d=os.listdir(path)
			except (OSError,IOError),e:
				self.error("Couldn't get plugin list: %s" % (e,))
				continue
			for f in d:
				if f[0]=="." or not f.endswith(".py"):
					continue
				self.load_plugin(os.path.join(f[:-3]))
		sys.path=sys_path

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

		self.top_bar=ui.StatusBar("CJC ver. %(version)s by Jacek Konieczny <jajcus@bnet.pl>",
					{"version": version.version})
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
		if not self.jid:
			self.info("")
			self.info("Quickstart:")
			self.info("/set jid your_username@your.domain/your_resource")
			self.info("/set password your_password")
			self.info("/save")
			self.info("/connect")
			self.info("/chat jajcus@jabber.bnet.pl CJC Rulez!")
			self.info("")
			self.info("press Alt-Tab (or Escape Tab) to change active window")
			self.info("PgUp/PgDown to scroll window content")

		try:
			self.loop(1)
		except Exit:
			pass

	def session_started(self):
		pyxmpp.Client.session_started(self)
		for p in self.plugins.values():
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

		fvar,val=args.split(None,1)
		if fvar.find("=")>0:
			fvar,val=args.split("=",1)

		if fvar.find(".")>0:
			plugin,var=var.split(".",1)
			try:
				obj=self.plugins[plugin]
			except KeyError:
				self.error("Unknown category: "+plugin)
				return
		else:
			obj=self
			var=fvar

		try:
			descr,type,location=obj.available_settings[var]
		except KeyError:
			self.error("Unknown setting: "+fvar)
			return
		
		try:
			if type is unicode:
				pass
			if type is list:
				val=val.split()
			else:
				val=type(val)
		except Exception,e:
			self.error("Bad value: "+str(e))
			return
		
		if location is None:
			obj.settings[var]=val
		elif location.startswith("."):
			setattr(obj,location[1:],val)
			
		self.screen.update()

	def cmd_save(self,filename=None):
		if filename is None:
			filename=".cjcrc"
		self.info(u"Saving settings to "+filename)
		try:
			f=file(filename,"w")
		except IOError,e:
			self.error(u"Couldn't open config file: "+str(e))
			return

		for plugin in [None]+self.plugins.keys():
			if plugin is None:
				obj=self
			else:
				obj=self.plugins[plugin]
			for var in obj.available_settings:
				descr,type,location=obj.available_settings[var]
				if location is None:
					val=obj.settings.get(var)
				elif location.startswith("."):
					val=getattr(obj,location[1:],None)
				else:
					continue
				if val is None:
					continue
				if plugin is not None:
					var="%s.%s" % (plugin,var)
				if type is list:
					print >>f,var,string.join(val," ")
				elif type is pyxmpp.JID:
					print >>f,var,val.as_string()
				else:
					print >>f,var,val

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

	def cmd_help(self,args):
		if not args:
			self.info("Available commands:")
			commands=self.commands()
			if commands:
				self.info("  Global commands:")
				for cmd in commands:
					self.info(u"    /"+cmd)
			commands=self.screen.commands()
			if commands:
				self.info("  Screen commands:")
				for cmd in commands:
					self.info(u"    /"+cmd)
			win=self.screen.active_window
			if not win:
				return
			commands=win.commands()
			if commands:
				self.info(u"  commands for window '%s':" % (win.description(),))
				for cmd in commands:
					self.info(u"    /"+cmd)
			return

		if args[0]=="/":
			args=args[1:]
		try:
			handler,usage,descr=self.get_command_info(args)
		except KeyError:
			try:
				handler,usage,descr=self.screen.get_command_info(args)
			except KeyError:
				if self.screen.active_window:
					win=self.screen.active_window
					try:
						handler,usage,descr=win.get_command_info(args)
					except KeyError:
						self.error(u"Unknown command: "+`args`)
						return
				else:
					self.error(u"Unknown command: "+`args`)
					return
		
		self.info("Usage:")
		self.info(u"   "+usage)
		self.info(u"  "+descr)
	
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
			if not uinf.has_key("resources"):
				uinf["resources"]={}
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
		groups=self.roster.groups()
		groups.sort()
		for group in groups:
			if group:
				self.roster_buf.append(group+u":\n","default")
			else:
				self.roster_buf.append(u"unfiled:\n","default")
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
