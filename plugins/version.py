
# Normative reference: JEP-0092

import os

import cjc.version
from cjc.plugin import PluginBase
import pyxmpp

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		self.available_settings={
			"name": ("Client name to return in reply to jabber:iq:version query",str,None),
			"version": ("Client version to return in reply to jabber:iq:version query",str,None),
			"os": ("OS name to return in reply to jabber:iq:version query",str,None),
			}
		app.register_commands({"version": (self.cmd_version,
							"/version [jid]",
							"Queries software version of given entity"
							" or displays version of the client")
						})
		sysname,nodename,release,version,machine=os.uname()
		self.defaults={
				"version": cjc.version.version,
				"name": "Console Jabber Client",
				"os": "%s %s %s"  % (sysname,release,machine),
			}
	
	def session_started(self,stream):
		self.cjc.stream.set_iq_get_handler("query","jabber:iq:version",self.version_get)

	def version_string(self):
		d=self.defaults.copy()
		d.update(self.settings)
		return "%(name)s/%(version)s (%(os)s)" % d

	def cmd_version(self,args):
		target=args.shift()
		if not target:
			self.info(self.version_string())
			return
		
		if not self.cjc.stream:
			self.error("Connect first!")
			return
			
		jid=self.cjc.get_user(target)
		if jid is None:
			return

		if jid.node and not jid.resource:
			resources=self.cjc.get_user_info(jid,"resources")
			if resources:
				jids=[]
				for r in resources:
					jids.append(pyxmpp.JID(jid.node,jid.domain,r,check=0))
			else:
				jids=[jid]
		else:
			jids=[jid]
			
		for jid in jids:	
			iq=pyxmpp.Iq(to=jid,type="get")
			q=iq.new_query("jabber:iq:version")
			self.cjc.stream.set_response_handlers(iq,self.version_response,self.version_error)
			self.cjc.stream.send(iq)

	def version_get(self,stanza):
		iq=stanza.make_result_response()
		q=iq.new_query("jabber:iq:version")
		d=self.defaults.copy()
		d.update(self.settings)
		q.newChild(q.ns(),"name",d["name"])
		q.newChild(q.ns(),"version",d["version"])
		if d["os"]:
			q.newChild(q.ns(),"os",d["os"])
		self.cjc.stream.send(iq)

	def version_response(self,stanza):
		version_string=u"%s: " % (stanza.get_from(),)
		name=stanza.xpath_eval("v:query/v:name",{"v":"jabber:iq:version"})
		if name:
			version_string+=name[0].getContent()
		version=stanza.xpath_eval("v:query/v:version",{"v":"jabber:iq:version"})
		if version:
			version_string+=u"/"+version[0].getContent()
		os=stanza.xpath_eval("v:query/v:os",{"v":"jabber:iq:version"})
		if os:
			version_string+=u" (%s)" % (os[0].getContent(),)
		self.info(version_string)

	def version_error(self,stanza):
		self.error(u"Version query error from %s: %s" % (stanza.get_from(),
						stanza.get_error().serialize()))
