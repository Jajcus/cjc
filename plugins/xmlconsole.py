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
)

class Plugin(PluginBase):
    def __init__(self,app):
        PluginBase.__init__(self,app)
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
        app.add_event_handler("stream created",self.ev_stream_created)
        app.add_event_handler("stream closed",self.ev_stream_closed)
        ui.activate_cmdtable("xmlconsole",self)
        self.away_saved_presence=None
        self.buffer=None
        self.saved_data_in_cb=None
        self.saved_data_out_cb=None

    def ev_stream_created(self,event,arg):
        if not self.buffer:
            return
        self.setup_stream_callbacks(arg)

    def ev_stream_closed(self,event,arg):
        if not self.buffer:
            return
        self.setup_stream_callbacks(None)

    def setup_stream_callbacks(self,stream):
        if stream:
            self.saved_data_in_cb=stream.data_in
            self.saved_data_out_cb=stream.data_out
            stream.data_in=self.data_in
            stream.data_out=self.data_out
        else:
            self.saved_data_in_cb=None
            self.saved_data_out_cb=None

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
        if self.cjc.stream:
            self.setup_stream_callbacks(self.cjc.stream)
        self.cjc.screen.display_buffer(self.buffer)

    def cmd_close(self,args):
        if self.cjc.stream:
            if self.saved_data_in_cb:
                self.cjc.stream.data_in=self.saved_data_in_cb
            if self.saved_data_out_cb:
                self.cjc.stream.data_out=self.saved_data_out_cb
        self.saved_data_in_cb=None
        self.saved_data_out_cb=None
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

    def data_in(self,data):
        if self.saved_data_in_cb:
            self.saved_data_in_cb(data)
        self.show_data(data,"in")

    def data_out(self,data):
        if self.saved_data_in_cb:
            self.saved_data_out_cb(data)
        self.show_data(data,"out")

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
