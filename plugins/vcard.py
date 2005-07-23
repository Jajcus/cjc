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


# Normative reference: JEP-0054

import os

from cjc.plugin import PluginBase
from cjc import ui
import pyxmpp
from pyxmpp.jabber import VCARD_NS,VCard

vcard_fields=("FN","N","NICKNAME","EMAIL","JABBERID")

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        ui.activate_cmdtable("vcard",self)

    def session_started(self,stream):
        #self.cjc.stream.set_iq_get_handler("query",VCARD_NS,self.vcard_get)
        #self.cjc.disco_info.add_feature(VCARD_NS)
        pass

    def cmd_whois(self,args):
        if not self.cjc.stream:
            self.error("Connect first!")
            return

        target=args.shift()
        if target:
            jids = self.cjc.get_users(target)
            if not jids:
                return
        else:
            jids = [self.cjc.jid.bare()]

        for jid in jids:
            iq=pyxmpp.Iq(to_jid=jid,stanza_type="get")
            q=iq.new_query(VCARD_NS, "vCard")
            self.cjc.stream.set_response_handlers(iq,self.vcard_response,self.vcard_error)
            self.cjc.stream.send(iq)

    def vcard_response(self,stanza):
        try:
            node=stanza.get_query()
            if node:
                vcard=VCard(node)
            else:
                vcard=None
        except (ValueError,),e:
            vcard=None
        if vcard is None:
            self.error(u"Invalid vCard received from "+stanza.get_from().as_unicode())
            return
        self.cjc.set_user_info(stanza.get_from(),"vcard",vcard)
        msg=u"vCard for %s:\n" % (stanza.get_from(),)
        for field in vcard_fields:
            if field=="FN":
                msg+=u" Full name:   %s\n" % (vcard.fn.value)
            if field=="N":
                if vcard.n.given:
                    msg+=u" Given name:  %s\n" % (vcard.n.given)
                if vcard.n.middle:
                    msg+=u" Middle name: %s\n" % (vcard.n.middle)
                if vcard.n.family:
                    msg+=u" Family name: %s\n" % (vcard.n.family)
            if field=="EMAIL":
                for email in vcard.email:
                    if "internet" in email.type:
                        msg+=u" E-Mail:      %s\n" % (email.address)
        self.info(msg)

    def vcard_error(self,stanza):
        err=stanza.get_error()
        self.error(u"vCard query error from %s: %s" % (stanza.get_from(),
                        err.get_message()))

ui.CommandTable("vcard",50,(
    ui.Command("whois",Plugin.cmd_whois,
        "/whois jid",
        "Displays information about an entity.",
        ("user",)),
    )).install()
# vi: sts=4 et sw=4
