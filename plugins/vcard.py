# Console Jabber Client
# Copyright (C) 2004-2005  Jacek Konieczny
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
        msg = u"vCard for %s:\n" % (unicode(stanza.get_from()),)
        
        msg+=u" Full name:   %s\n" % (vcard.fn.value)
        if vcard.n.given:
            msg += u" Given name:  %s\n" % (vcard.n.given)
        if vcard.n.middle:
            msg += u" Middle name: %s\n" % (vcard.n.middle)
        if vcard.n.family:
            msg += u" Family name: %s\n" % (vcard.n.family)
        for title in vcard.title:
            msg += u" Title:       %s\n" % (title.value)
        for role in vcard.role:
            msg += u" Role:        %s\n" % (role.value)
        for email in vcard.email:
            if "internet" in email.type:
                msg += u" E-Mail:      %s\n" % (email.address,)
        for nick in vcard.nickname:
            msg += u" Nick:        %s\n" % (nick.value,)
        for photo in vcard.photo:
            if photo.uri:
                msg += u" Photo:       %s\n" % (photo.uri,)
            else:
                msg += u" Photo:       cannot display\n"
        for logo in vcard.logo:
            if logo.uri:
                msg += u" Logo:        %s\n" % (logo.uri,)
            else:
                msg += u" Logo:        cannot display\n"
        for bday in vcard.bday:
            msg += u" Birthday:    %s\n" % (bday,)
        for adr in vcard.adr:
            msg += u" Address (%s):\n" % (u", ".join(adr.type),)
            if adr.pobox:
                msg += u"  PO Box:     %s\n" % (adr.pobox,)
            if adr.extadr:
                msg += u"              %s\n" % (adr.extadr,)
            if adr.street:
                msg += u"  Street:     %s\n" % (adr.street,)
            if adr.locality:
                msg += u"  Locality:   %s\n" % (adr.locality,)
            if adr.region:
                msg += u"  Region:     %s\n" % (adr.region,)
            if adr.pcode:
                msg += u"  Postal code: %s\n" % (adr.pcode,)
            if adr.ctry:
                msg += u"  Country:     %s\n" % (adr.ctry,)
        for label in vcard.label:
            msg += u" Address label (%s):\n" % (u", ".join(label.type),)
            for l in label.lines:
                msg += u"  %s\n" % (l,)
        for tel in vcard.tel:
            msg += u" Phone (%s):  %s\n" % (u", ".join(tel.type), tel.number)
        for jabberid in vcard.jabberid:
            msg += u" JID:         %s\n" % (unicode(jabberid.value),)
        for mailer in vcard.mailer:
            msg += u" Mailer:      %s\n" % (mailer.value,)
        for tz in vcard.tz:
            msg += u" Time zone:   %s\n" % (tz.value,)
        for geo in vcard.geo:
            msg += u" Geolocation: %s, %s\n" % (geo.lat, geo.lon)
        for org in vcard.org:
            msg += u" Organization: %s\n" % (org.name, )
            if org.unit:
                msg += u" Org. unit:   %s\n" % (org.unit, )
        for categories in vcard.categories:
            msg += u" Categories:  %s\n" % (u", ".join(categories.keywords),)
        for note in vcard.note:
            msg += u" Note:        %s\n" % (note.value,)
        for sound in vcard.sound:
            if sound.uri:
                msg += u" Sound:       %s\n" % (sound.uri,)
            else:
                msg += u" Sound:       cannot play\n"
        for uid in vcard.uid:
            msg += u" User id:     %s\n" % (uid.value,)
        for url in vcard.url:
            msg += u" URL:         %s\n" % (url.value,)
        for desc in vcard.desc:
            msg += u" Description: %s\n" % (desc.value,)
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
