import string
from cjc.plugin import PluginBase

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		self.available_settings={
			"priority": ("Priority of current resource",int,None),
			"away_priority": ("Priority of current resource in away and xa modes",(int,None),None),
			"auto_away": ("Time in minutes after set presence should be set to 'away' (unset or 0 to disable)",(int,None),None),
			"auto_xa": ("Time in minutes after set presence should be set to 'xa' (unset or 0 to disable)",(int,None),None),
			"auto_away_msg": ("Auto-away status description",(unicode,None),None),
			"auto_xa_msg": ("Auto-away status description",(unicode,None),None),
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
		p=pyxmpp.Presence(priotity=self.settings["priority"])
		self.cjc.stream.send(p)
		self.cjc.stream.set_presence_handler("error",self.presence_error)
		self.cjc.stream.set_presence_handler(None,self.presence_available)
		self.cjc.stream.set_presence_handler("unavailable",self.presence_unavailable)

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
		else:	
			self.cjc.set_bare_user_info(fr,"presence",stanza.copy())
		
	def presence_available(self,stanza):
		fr=stanza.get_from()
		p=self.cjc.get_user_info(fr,"presence")
		if not p or p!=stanza:
			self.info(fr.as_unicode()+u" is available")
		else:
			self.debug(fr.as_unicode()+u" is unavailable")
		self.cjc.set_user_info(fr,"presence",stanza.copy())
		
	def presence_unavailable(self,stanza):
		fr=stanza.get_from()
		if self.cjc.get_user_info(fr):
			self.info(fr.as_unicode()+u" is unavailable")
		else:
			self.debug(fr.as_unicode()+u" is unavailable")
		self.cjc.set_user_info(fr,"presence",stanza.copy())
