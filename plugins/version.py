
# Normative reference: JEP-0092

import os

import cjc.version
from cjc.plugin import PluginBase
from cjc import ui
import pyxmpp

class Plugin(PluginBase):
    def __init__(self,app):
        PluginBase.__init__(self,app)
        self.available_settings={
            "name": ("Client name to return in reply to jabber:iq:version query",str),
            "version": ("Client version to return in reply to jabber:iq:version query",str),
            "os": ("OS name to return in reply to jabber:iq:version query",str),
            }
        sysname,nodename,release,version,machine=os.uname()
        self.defaults={
                "version": cjc.version.version,
                "name": "Console Jabber Client",
                "os": "%s %s %s"  % (sysname,release,machine),
            }
        ui.activate_cmdtable("version",self)

    def unload(self):
        try:
            if self.cjc.stream:
                self.cjc.stream.unset_iq_get_handler("query","jabber:iq:version")
            if self.cjc.disco_info:
                self.cjc.disco_info.remove_feature("jabber:iq:version")
            ui.uninstall_cmdtable("version")
        except:
            self.cjc.print_exception()
        return True

    def session_started(self,stream):
        self.cjc.stream.set_iq_get_handler("query","jabber:iq:version",self.version_get)
        self.cjc.disco_info.add_feature("jabber:iq:version")

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
        q.newTextChild(q.ns(),"name",d["name"])
        q.newTextChild(q.ns(),"version",d["version"])
        if d["os"]:
            q.newTextChild(q.ns(),"os",d["os"])
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

ui.CommandTable("version",50,(
    ui.Command("version",Plugin.cmd_version,
        "/version [jid]",
        "Queries software version of given entity"
        " or displays version of the client",
        ("user",)),
    )).install()
# vi: sts=4 et sw=4
