# Console Jabber Client
# Copyright (C) 2004-2010 Jacek Konieczny
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

"""Message multicastiong"""

import pyxmpp

from cjc.plugin import PluginBase
from cjc import common
from cjc import ui
import os

from roster import roster_filter_cmd_args

class Plugin(PluginBase):
    def __init__(self, app, name):
        PluginBase.__init__(self, app, name)
        ui.activate_cmdtable("multicast", self)

    def cmd_multi_message(self, args):

        if not self.cjc.roster:
            self.error("No roster available.")
            return

        roster_plugin = self.cjc.get_plugin("roster")

        first_arg = args.get()
        if not first_arg:
            self.error("Filter and message body must be provided.")
            return

        if not first_arg.startswith("-") or first_arg in ("-subject", ):
            self.error("You must give at least one filter option.")
            return
    
        items = roster_plugin.filter_roster(args, eat_all_args = False, extra_options = ["-subject"])

        if not items:
            return

        arg = args.get()
        if arg == "-subject":
            args.shift()
            subject = args.shift()
            if not subject:
                self.error("Message subject not given")
                return
        else:
            subject = None
 
        body = args.all()
        if not body:
            self.error("Message body not given")
            return

        items = [ item for item in items if item.jid.node ]

        self.info(u"Sending message to: %s", u", ".join([unicode(item.jid) for item in items]))

        for item in items:
            m = pyxmpp.Message(to_jid = item.jid, body = body, subject = subject)
            self.cjc.stream.send(m)
        
        
ui.CommandTable("multicast",50,(
    ui.Command("multi_message",Plugin.cmd_multi_message,
        "/multi_message ((-group regexp) | (-state available|unavailable|online|offline|away|xa|chat|error) | -subscription (none|to|from|both) )...  message",
        "Send message to multiple users from roster. The message will be sent"
        " to all users matching all the given conditions. At least one condition"
        " must be provided.",
        roster_filter_cmd_args + ("-subject opaque", "text", )),
    )).install()

# vi: sts=4 et sw=4
