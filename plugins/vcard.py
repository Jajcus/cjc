
# Normative reference: JEP-0054

import os

from cjc.plugin import PluginBase
from cjc import ui
import pyxmpp
from pyxmpp.jabber import VCARD_NS,VCard

vcard_fields=("FN","N","NICKNAME","EMAIL","JABBERID")

class Plugin(PluginBase):
    def __init__(self,app):
        PluginBase.__init__(self,app)
        ui.activate_cmdtable("vcard",self)

    def session_started(self,stream):
        #self.cjc.stream.set_iq_get_handler("query",VCARD_NS,self.vcard_get)
        #self.cjc.disco_info.add_feature(VCARD_NS)
        pass

    def cmd_whois(self,args):
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

        iq=pyxmpp.Iq(to=jid,type="get")
        q=iq.new_query(VCARD_NS)
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
