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


import os
import re
from cjc.plugin import PluginBase
from cjc import ui
import time

theme_formats=(
    ("events.event","[%(T:timestamp)s] %(event)s\n          %(command)s\n"),
)

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        app.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "event_handlers": ("Event handlers (managed with /event_add and"
                    " /event_remove commands)",list),
            }
        self.settings={
                "event_handlers": [
                        "chat message received:beep *.*",
                        "message received:beep *.*.*",
                        "groupchat message to me received:beep *.*",
                        "groupchat message received:beep *",
                        ],
                }
        app.add_event_handler("*",self.handle_event)
        ui.activate_cmdtable("events",self)

    def cmd_beep(self,args):
        arg=args.shift()
        if arg is None:
            self.cjc.screen.beep()
            return
        while arg is not None:
            for c in arg:
                if c not in " ._":
                    self.cjc.screen.beep()
                else:
                    time.sleep(0.1)
            arg=args.shift()
            if arg is not None:
                time.sleep(1)

    def cmd_add_event(self,args):
        self.error("Not implemented yet. :-(")

    def cmd_show_events(self,args):
        self.error("Not implemented yet. :-(")

    def handle_event(self,event,arg):
        handlers=self.settings.get("event_handlers",[])
        for h in handlers:
            s=h.split(":",1)
            if len(s)!=2:
                continue
            ev,command=s
            try:
                if re.match(ev,event):
                    if command:
                        ui.run_command(command)
                    return
            except re.error:
                continue

ui.CommandTable("events",95,(
    ui.Command("beep",Plugin.cmd_beep,
        "/shell [pattern...]",
        "Play a 'beep' through a terminal beeper. If patterns are given they are interpreted as"
        " a sequence of 0.1s pauses (characters ' ', '.', '_') and beeps (any other character)"
        " there is a 1s pause beetween patterns."),
    ui.Command("add_event",Plugin.cmd_add_event,
        "/add_event regexp command",
        "Add an event handler. Regexp is regular expression to match events"
        " (usually just an event name) and command is a CJC command (without"
        " leading '/') to execute on the event.",
        ("event","command")),
    ui.Command("show_events",Plugin.cmd_show_events,
        "/show_events",
        "Display active event handlers."),
    )).install()
# vi: sts=4 et sw=4
