import string
from cjc.plugin import PluginBase
import pyxmpp
import time

theme_formats=(
	("presence.available","%[info][%(T:timestamp)s] %(J:user)s (%(J:user:rostername)s) is available\n"),
	("presence.unavailable","%[info][%(T:timestamp)s] %(J:user)s (%(J:user:rostername)s) is unavailable\n"),
)

commands={
	"online": ("cmd_online",
		"/online [reason]",
		"Set availability to 'online' with optional reason"),
	"back": "online",
	"away": ("cmd_away",
		"/away [reason]",
		"Set availability to 'away' with optional reason"),
	"xa": ("cmd_xa",
		"/xa [reason]",
		"Set availability to 'extended away' with optional reason"),
	"dnd": ("cmd_dnd",
		"/dnd [reason]",
		"Set availability to 'do not disturb' with optional reason"),
	"busy": "dnd",
	"chatready": ("cmd_chatready",
		"/chatready [reason]",
		"Set availability to 'ready for a chat' with optional reason"),
	}

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		app.theme_manager.set_default_formats(theme_formats)
		self.available_settings={
			"priority": ("Priority of current resource",int),
			"away_priority": ("Priority of current resource in away and xa modes",(int,None)),
			"auto_away": ("Time in minutes after set presence should be set to 'away' (unset or 0 to disable)",(int,None)),
			"auto_xa": ("Time in minutes after set presence should be set to 'xa' (unset or 0 to disable)",(int,None)),
			"auto_away_msg": ("Auto-away status description",(unicode,None)),
			"auto_xa_msg": ("Auto-away status description",(unicode,None)),
			}
		self.settings={
			"priority": 1,
			"auto_away": 5,
			"auto_xa": 15,
			"auto_away_msg": u"Automaticaly away after %i minutes",
			"auto_away_msg": u"Automaticaly xa after %i minutes",
			}
		app.add_info_handler("resources",self.info_resources)
		app.add_info_handler("presence",self.info_presence)
		app.add_event_handler("disconnect request",self.ev_disconnect_request)
		app.register_commands(commands,self)

	def info_resources(self,k,v):
		if not v:
			return None
		resources=[]
		for r in v.keys():
			p=v[r].get("presence")
			if p is None or (p.get_type() and p.get_type()!="available"):
				continue

			if not r:
				resources.append(u"<empty>")
			else:
				resources.append(r)
		if resources:
			return "Available resources",string.join(resources,",")

	def info_presence(self,k,v):
		if not v:
			return None

		name="Presence"
		if not v.get_type() or v.get_type()=="available":
			value="Available"
			if v.get_show():
				value+=" [%s]" % (v.get_show(),)
			if v.get_status():
				value+=" %s" % (v.get_status(),)
		elif v.get_type()=="unavailable":
			value="Not Available"
			if v.get_status():
				value+=" %s" % (v.get_status(),)
		elif v.get_type()=="error":
			value="Error"
			e=v.get_error()
			if e: 
				c=e.get_condition()
				if c:
					value+=": %s" % (c.serialize(),)
		else:
			return None
		return name,value
		
	def session_started(self,stream):
		self.cjc.stream.set_presence_handler("error",self.presence_error)
		self.cjc.stream.set_presence_handler(None,self.presence_available)
		self.cjc.stream.set_presence_handler("unavailable",self.presence_unavailable)
		self.set_presence(pyxmpp.Presence(priotity=self.settings["priority"]))

	def ev_disconnect_request(self,event,arg):
		p=pyxmpp.Presence(type="unavailable",status=arg)
		self.set_presence(p)

	def cmd_online(self,args):
		if not self.cjc.stream:
			self.error("Connect first!")
			return
		reason=args.all()
		p=pyxmpp.Presence(status=reason)
		self.set_presence(p)
		
	def cmd_away(self,args):
		if not self.cjc.stream:
			self.error("Connect first!")
			return
		reason=args.all()
		p=pyxmpp.Presence(show="away",status=reason)
		self.set_presence(p)

	def cmd_xa(self,args):
		if not self.cjc.stream:
			self.error("Connect first!")
			return
		reason=args.all()
		p=pyxmpp.Presence(show="xa",status=reason)
		self.set_presence(p)
		
	def cmd_dnd(self,args):
		if not self.cjc.stream:
			self.error("Connect first!")
			return
		reason=args.all()
		p=pyxmpp.Presence(show="dnd",status=reason)
		self.set_presence(p)
		
	def cmd_chatready(self,args):
		if not self.cjc.stream:
			self.error("Connect first!")
			return
		reason=args.all()
		p=pyxmpp.Presence(show="chat",status=reason)
		self.set_presence(p)
		
	def set_presence(self,p):
		self.cjc.stream.send(p)
		self.cjc.set_user_info(self.cjc.jid,"presence",p)
		self.compute_current_resource(self.cjc.jid.bare())
		self.cjc.send_event("presence changed",self.cjc.jid)

	def presence_error(self,stanza):
		fr=stanza.get_from()
		msg=u"Presence error from: "+fr.as_unicode()
		err=stanza.get_error()
		emsg=err.get_message()
		if emsg:
			msg+=": %s" % emsg
		etxt=err.get_text()
		if etxt:
			msg+=" ('%s')" % etxt
		self.debug(stanza.get_error().serialize())
		
		if self.cjc.get_user_info(fr):
			self.warning(msg)
		else:
			self.debug(msg)
		if fr.resource:
			self.cjc.set_user_info(fr,"presence",stanza.copy())
			self.compute_current_resource(fr.bare())
		elif not self.cjc.get_bare_user_info(fr,"resources"):
			self.cjc.set_bare_user_info(fr,"presence",stanza.copy())
		self.cjc.send_event("presence changed",fr)
		
	def presence_available(self,stanza):
		fr=stanza.get_from()
		p=self.cjc.get_user_info(fr,"presence")
		if not p or p!=stanza:
			self.cjc.status_buf.append_themed("presence.available",{"user":fr})
			self.cjc.status_buf.update()
		else:
			self.debug(fr.as_unicode()+u" is unavailable")
		self.cjc.set_user_info(fr,"presence",stanza.copy())
		self.compute_current_resource(fr.bare())
		self.cjc.send_event("presence changed",fr)
		
	def presence_unavailable(self,stanza):
		fr=stanza.get_from()
		if self.cjc.get_user_info(fr):
			self.cjc.status_buf.append_themed("presence.unavailable",{"user":fr})
			self.cjc.status_buf.update()
		else:
			self.debug(fr.as_unicode()+u" is unavailable")
		self.cjc.set_user_info(fr,"presence",stanza.copy())
		self.compute_current_resource(fr.bare())
		self.cjc.send_event("presence changed",fr)

	def compute_current_resource(self,jid):
		resources=self.cjc.get_bare_user_info(jid,"resources")
		if not resources:
			p=self.cjc.get_bare_user_info(jid,"presence")
			if p and p.get_type()!="error":
				self.cjc.set_bare_user_info(jid,"presence",None)
			return
		presence=None
		max_prio=-129
		for r,d in resources.items():
			fjid=pyxmpp.JID(jid.node,jid.domain,r,check=0)
			if not d.has_key("presence"):
				continue
			p=d["presence"]
			if not p:
				continue
			typ=p.get_type()
			if typ and p.get_type()!="available":
				continue
			prio=p.get_priority()
			if prio>max_prio:
				max_prio=prio
				presence=p
		self.cjc.set_bare_user_info(jid,"presence",presence)
