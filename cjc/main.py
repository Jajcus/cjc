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

class Exit(StandardError):
	pass

class Buffer:
	def __init__(self,length=200):
		self.length=length
		self.lines=[[]]
		self.pos=0
		self.window=None
		
	def append(self,s,attr="default"):
		if self.window:
			self.window.write(s,attr)
		newl=0
		s=s.split(u"\n")
		for l in s:
			if newl:
				self.lines.append([])
			if l:
				self.lines[-1].append((attr,l))
			newl=1
		self.lines=self.lines[-self.length:]
	
	def append_line(self,s,attr="default"):
		self.append(s,attr)
		self.lines.append([])
		if self.window:
			self.window.write(u"\n",attr)

	def write(self,s):
		self.append(s)
		self.update()

	def clear(self):
		self.lines=[[]]

	def line_length(self,n):
		ret=0
		for attr,s in self.lines[n]:
			ret+=len(s)
		return ret

	def format(self,offset,width,height):
		if self.lines[-1]==[]:
			i=2
		else:
			i=1
		ret=[]
		while height>0 and i<=len(self.lines):
			l=self.line_length(-i)
			h=l/width+1
			ret.insert(0,self.lines[-i])
			height-=h
			i+=1
			
		if height<0:
			cut=(-height)*width
			i=0
			n=0
			for attr,s in ret[0]:
				l=len(s)
				i+=l
				if i==cut:
					ret[0]=ret[0][n+1:]
					break
				elif i>cut:
					ret[0]=[(attr,s[-(cut-i):])]+ret[0][n+1:]
					break
				n+=1
		return ret

	def update(self,now=1):
		if self.window:
			self.window.update(now)

	def redraw(self,now=1):
		if self.window:
			self.window.redraw(now)

class Application(pyxmpp.Client):
	def __init__(self):
		pyxmpp.Client.__init__(self)
		self.plugin_dirs=["cjc/plugins"]
		self.plugins=[]
		self.event_handlers={}
		self.user_info={}
		self.info_handlers={}
		self.commands={
			"exit": self.cmd_quit,
			"quit": self.cmd_quit,
			"set": self.cmd_set,
			"connect": self.cmd_connect,
			"disconnect": self.cmd_disconnect,
			"save": self.cmd_save,
			"load": self.cmd_load,
			"redraw": self.cmd_redraw,
			"info": self.cmd_info,
		}

	def load_plugin(self,path):
		self.info("Loading plugin: %s" % (path,))
		try:
			from plugin import PluginBase
			gl={"PluginBase":PluginBase}
			mod=execfile(path,gl)
			plugin=gl["Plugin"](self)
			self.plugins.append(plugin)
		except:
			traceback.print_exc(file=self.status_buf)
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
				traceback.print_exc(file=self.status_buf)
				self.info("Event handler failed")

	def add_info_handler(self,var,handler):
		self.info_handlers[var]=handler

	def run(self,screen):
		self.screen=screen
		
		self.status_buf=Buffer()
		self.message_buf=Buffer()
		self.roster_buf=Buffer()

		self.top_bar=ui.StatusBar(["CJC"])
		self.status_window=ui.Window(["Status"])
		self.main_window=ui.Window(["Main"])
		self.command_line=ui.EditLine(self.user_input)
		self.bottom_bar=ui.StatusBar(["CJC"])
		self.roster_window=ui.Window(["Roster"])

		sp=ui.VerticalSplit(self.main_window,self.roster_window)
		sp=ui.HorizontalSplit(self.top_bar,self.status_window,
					sp,self.bottom_bar,
					self.command_line)
		screen.set_content(sp)
		
		self.status_window.set_buffer(self.status_buf)
		self.main_window.set_buffer(self.message_buf)
		self.roster_window.set_buffer(self.roster_buf)
		self.screen.update()
		
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
				traceback.print_exc(file=self.status_buf)
				self.info("Plugin call failed")
		self.stream.set_message_handler("error",self.message_error)
		self.stream.set_message_handler("normal",self.message_normal)
		self.stream.set_message_handler("chat",self.message_chat)

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
	
	def message_chat(self,stanza):
		self.message_buf.append_line(u"%s: %s" %
				(stanza.get_from().as_unicode(),stanza.get_body()))
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
	
	def command(self,cmd):
		if not cmd:
			return
		s=cmd.split(None,1)
		if len(s)>1:
			cmd,args=s
		else:
			cmd,args=s[0],None
		cmd=cmd.lower()
		if self.commands.has_key(cmd):
			try:
				self.commands[cmd](args)
			except (KeyboardInterrupt,SystemExit,Exit),e:
				raise
			except Exception,e:
				self.error("Comand execution failed: "+str(e))
				traceback.print_exc(file=self.status_buf)
		else:
			self.error("Unknown command: "+cmd)

	def user_input(self,s):
		if s.startswith(u"/"):
			self.command(s[1:])
		else:
			self.message_buf.append_line(s)
			self.message_buf.update()

	def loop(self,timeout):
		while 1:
			fdlist=[sys.stdin.fileno()]
			if self.stream and self.stream.socket:
				fdlist.append(self.stream.socket)
			id,od,ed=select.select(fdlist,[],fdlist,timeout)
			if sys.stdin.fileno() in id:
				self.command_line.process()
			if self.stream and self.stream.socket in id:
				self.stream.process()
			else:
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
			self.roster_buf.append(group+u":\n","default")
			for item in self.roster.items_by_group(group):
				jid=item.jid()
				name=item.name()
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
