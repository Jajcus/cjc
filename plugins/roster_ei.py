# Console Jabber Client
# Copyright (C) 2004-2006  Jacek Konieczny
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

"""Roster export/import"""

import libxml2

import pyxmpp
import pyxmpp.roster

import copy

from cjc.plugin import PluginBase
from cjc import common
from cjc import ui
import os

class Plugin(PluginBase):
    def __init__(self, app, name):
        PluginBase.__init__(self, app, name)
        ui.activate_cmdtable("roster_ei", self)

    def cmd_export_roster(self, args):
        filename = args.shift()
        
        if args.all():
            self.error(u"Too many arguments.")
            return

        filename = os.path.expanduser(filename)

        if os.path.exists(filename):
            self.error(u"File exists.")
            return

        try:
            f = file(filename, "w")
            xml = self.cjc.roster.as_xml()
            f.write(xml.serialize(format=1))
            f.close()
        except IOError, e:
            self.error(u"Error writting roster: %s", unicode(e))
            return
            return

        self.info(u"Roster written: %s", unicode(filename))

    def cmd_import_roster(self, args):
        filename = args.shift()
        
        if args.all():
            self.error(u"Too many arguments.")
            return

        filename = os.path.expanduser(filename)

        try:
            xml = libxml2.parseFile(filename)
        except (IOError, libxml2.libxmlError), e:
            self.error(u"Error reading roster: %s", unicode(e))
            return
            return

        roster = pyxmpp.roster.Roster(xml.getRootElement())

        self.info(u"Roster read: %i items", len(roster.items))

        for item in roster:
            if item.jid in self.cjc.roster:
                local_item = self.cjc.roster.get_item_by_jid(item.jid)
            else:
                self.info(u"Adding entry: %s (%s)", unicode(item.jid), unicode(item.name))
                local_item = self.cjc.roster.add_item(item.jid, name = item.name, groups = item.groups)
                iq = local_item.make_roster_push()
                self.cjc.stream.send(iq)
                
            if item.subscription in ('both', 'to') and local_item.subscription in ('none', 'from'):
                self.info(u"Sending supscription request to: %s", unicode(local_item.jid))
                p = pyxmpp.Presence(stanza_type = 'subscribe', to_jid = local_item.jid)
                self.cjc.stream.send(p)

ui.CommandTable("roster_ei",50,(
    ui.Command("export_roster",Plugin.cmd_export_roster,
        "/export_roster filename",
        "Export roster as an XML file.",
        ("filename",)),
    ui.Command("import_roster",Plugin.cmd_import_roster,
        "/import_roster filename",
        "Import roster as an XML file.",
        ("filename",)),
    )).install()
# vi: sts=4 et sw=4
