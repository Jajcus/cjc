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

import logging

import string
from types import UnicodeType,StringType
import curses
import libxml2

import pyxmpp
from pyxmpp.utils import from_utf8,to_utf8

from cjc.plugin import PluginBase
from cjc import ui

theme_attrs=(
    ("xmlconsole.out", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("xmlconsole.in", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
    ("xmlconsole.out","%[xmlconsole.out][%(T:now)s] OUT: %(msg)s\n"),
    ("xmlconsole.in","%[xmlconsole.in][%(T:now)s] IN: %(msg)s\n"),
    ("xmlconsole.descr","Raw XML console"),
    ("xmlconsole.day_change","%{@day_change}"),
)

class DataInHandler(logging.Handler):
    def __init__(self,plugin):
        logging.Handler.__init__(self,level=logging.CRITICAL)
        self.plugin=plugin
    def emit(self,record):
        data=record.args[0]
        if not data or data in (" ","\n"):
            # skip keepalive data (but we are not sure it is keepalive)
            return
        self.plugin.show_data(record.args[0],"in")

class DataOutHandler(logging.Handler):
    def __init__(self,plugin):
        logging.Handler.__init__(self,level=logging.CRITICAL)
        self.plugin=plugin
    def emit(self,record):
        data=record.args[0]
        if not data or data in (" ","\n"):
            # skip keepalive data (but we are not sure it is keepalive)
            return
        self.plugin.show_data(record.args[0],"out")

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        app.theme_manager.set_default_formats(theme_formats)
        app.theme_manager.set_default_attrs(theme_attrs)
        self.available_settings={
            "pretty_print": ("Reformat (pretty-print) sent and received XML (doesn't work well)",int),
            "check": ("Check if the raw-XML element is valid before sending",int),
            }
        self.settings={
            "pretty_print": 0,
            "check": 1,
            }
        app.add_event_handler("day changed",self.ev_day_changed)
        ui.activate_cmdtable("xmlconsole",self)
        self.away_saved_presence=None
        self.buffer=None
        self.data_in_handler=DataInHandler(self)
        self.data_out_handler=DataOutHandler(self)
        logging.getLogger("pyxmpp.Stream.in").addHandler(self.data_in_handler)
        logging.getLogger("pyxmpp.Stream.out").addHandler(self.data_out_handler)

    def ev_day_changed(self,event,arg):
        if not self.buffer:
            return
        self.buffer.append_themed("xmlconsole.day_change",{},activity_level=0)
        self.buffer.update()

    def user_input(self,s):
        if not self.cjc.stream:
            self.error("Not connected!")
            return
        if self.settings.get("check"):
            try:
                d=libxml2.parseDoc(to_utf8(s))
            except libxml2.parserError:
                if self.buffer:
                    self.buffer.append_themed("error","XML not well-formed!")
                else:
                    self.error("XML not well-formed!")
                self.cjc.screen.redraw() # workaroud for libxml2 messing the screen
                return
            s=d.getRootElement().serialize("utf-8")
        self.cjc.stream.write_raw(s)

    def cmd_rawxml(self,args):
        if not self.cjc.stream:
            self.error("Connect first!")
            return
        s=args.all()
        self.user_input(s)

    def cmd_xmlconsole(self,args):
        args.finish()
        if self.buffer:
            self.cjc.screen.display_buffer(self.buffer)
            return
        self.buffer=ui.TextBuffer(self.cjc.theme_manager,{},"xmlconsole.descr",
                "xmlconsole buffer",self)
        self.buffer.user_input=self.user_input
        self.buffer.update()
        self.data_in_handler.setLevel(logging.DEBUG)
        self.data_out_handler.setLevel(logging.DEBUG)
        self.cjc.screen.display_buffer(self.buffer)

    def cmd_close(self,args):
        self.data_in_handler.setLevel(logging.CRITICAL)
        self.data_out_handler.setLevel(logging.CRITICAL)
        if self.buffer:
            self.buffer.close()
        self.buffer=None

    def show_data(self,data,dir):
        if self.settings.get("pretty_print") and data:
            try:
                d=libxml2.parseDoc(to_utf8(data))
            except libxml2.parserError:
                self.cjc.screen.redraw() # workaroud for libxml2 messing the screen
            except:
                raise
            else:
                data=d.getRootElement().serialize("utf-8",1)
        if type(data) is UnicodeType:
            pass
        elif type(data) is StringType:
            data=unicode(data,"utf-8","replace")
        else:
            data=`data`
        self.buffer.append_themed("xmlconsole."+dir,data)
        self.buffer.update()

    def unload(self):
        logging.getLogger("pyxmpp.Stream.in").removeHandler(self.data_in_handler)
        logging.getLogger("pyxmpp.Stream.in").removeHandler(self.data_out_handler)
        ui.uninstall_cmdtable("xmlconsole buffer")
        ui.uninstall_cmdtable("xmlconsole")
        self.cjc.remove_event_handler("stream created",self.ev_stream_created)
        self.cjc.remove_event_handler("stream closed",self.ev_stream_closed)
        self.cmd_close(None)
        return True

ui.CommandTable("xmlconsole buffer",51,(
    ui.Command("close",Plugin.cmd_close,
        "/close",
        "Closes current chat buffer"),
    )).install()

ui.CommandTable("xmlconsole",51,(
    ui.Command("xmlconsole",Plugin.cmd_xmlconsole,
        "/xmlconsole",
        "Open raw XML console"),
    ui.Command("rawxml",Plugin.cmd_rawxml,
        "/rawxml xmlstring",
        "Send raw xml element"),
    )).install()
# vi: sts=4 et sw=4
