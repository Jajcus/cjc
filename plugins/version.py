# Console Jabber Client
# Copyright (C) 2004  Jacek Konieczny
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.


# Normative reference: JEP-0092

import os

import cjc.version
from cjc.plugin import PluginBase
from cjc import ui
import pyxmpp

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
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
        self.cjc.register_feature("jabber:iq:version")

    def unload(self):
        try:
            if self.cjc.stream:
                self.cjc.stream.unset_iq_get_handler("query","jabber:iq:version")
            self.cjc.unregister_feature("jabber:iq:version")
            ui.uninstall_cmdtable("version")
        except:
            self.cjc.print_exception()
        return True

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

        user_jids=self.cjc.get_users(target)
        if not user_jids:
            return

        for jid in user_jids:
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
                iq=pyxmpp.Iq(to_jid=jid,stanza_type="get")
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
