import string
import curses
import os

import pyxmpp
from pyxmpp.jabber import muc
from cjc import ui
from cjc.plugin import PluginBase
from cjc import common

theme_attrs=(
    ("muc.me", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("muc.other", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
    ("muc.info", curses.COLOR_GREEN,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
    ("muc.joining","[%(T:timestamp)s] %[muc.info]* Joining MUC room %(room)s...\n"),
    ("muc.me","[%(T:timestamp)s] %[muc.me]<%(J:me:nick)s>%[] %(msg)s\n"),
    ("muc.other","[%(T:timestamp)s] %[muc.other]<%(J:jid:nick)s>%[] %(msg)s\n"),
    ("muc.action","[%(T:timestamp)s] %[muc.info]* %(J:jid:nick)s %(msg)s\n"),
    ("muc.info","[%(T:timestamp)s] %[muc.info]* %(msg)s\n"),
    ("muc.descr","Conference on %(J:room:bare)s"),
)

class Room(muc.MucRoomHandler):
    def __init__(self,plugin,room,me):
        muc.MucRoomHandler.__init__(self)
        self.plugin=plugin
        self.room=room
        self.me=me
        self.fparams={
            "room":self.room,
            "me":self.me,
        }
        self.buffer=ui.TextBuffer(plugin.cjc.theme_manager,self.fparams,
                "muc.descr","muc buffer",self)
        self.buffer.user_input=self.user_input
        self.buffer.append_themed("muc.joining",self.fparams)
        self.buffer.update()

    def add_msg(self,s,format,nick,room_jid):
        self.fparams["jid"]=room_jid
        self.fparams["nick"]=nick
        user=self.room_state.get_user(nick)
        if user:
            self.fparams["real_jid"]=user.real_jid
        else:
            self.fparams["real_jid"]=None
        if s.startswith(u"/me "):
            self.fparams["msg"]=s[4:]
            self.buffer.append_themed("muc.action",self.fparams)
            self.buffer.update()
            return
        self.fparams["msg"]=s
        self.buffer.append_themed(format,self.fparams)
        self.buffer.update()

    def message_received(self,nick,stanza):
        body=stanza.get_body()
        if not body:
            return
        fr=stanza.get_from()
        if not nick:
            self.fparams["msg"]=body
            self.buffer.append_themed("muc.info",self.fparams)
            self.buffer.update()
            return
        elif fr==self.room_state.room_jid:
            self.add_msg(body,"muc.me",nick,fr)
        else:
            self.add_msg(body,"muc.other",nick,fr)
            
    def user_input(self,s):
        if not self.plugin.cjc.stream:
            self.buffer.append_themed("error","Not connected")
            self.buffer.update()
            return 0
        self.room_state.send_message(s)
        return 1

    def error(self,stanza):
        err=stanza.get_error()
        emsg=err.get_message()
        msg="Error"
        if emsg:
            msg+=": %s" % emsg
        etxt=err.get_text()
        if etxt:
            msg+=" ('%s')" % etxt
        self.buffer.append_themed("error",msg)
        self.buffer.update()

    def cmd_me(self,args):
        if not args:
            return 1
        args=args.all()
        if not args:
            return 1
        self.user_input(u"/me "+args)
        return 1

    def cmd_close(self,args):
        args.finish()
        self.room_state.leave()
        self.buffer.close()
        return 1

ui.CommandTable("muc buffer",50,(
    ui.Command("me",Room.cmd_me,
        "/me text",
        "Sends /me text",
        ("text",)),
    ui.Command("close",Room.cmd_close,
        "/close",
        "Closes current chat buffer"),
    )).install()

class Plugin(PluginBase):
    def __init__(self,app):
        PluginBase.__init__(self,app)
        app.theme_manager.set_default_attrs(theme_attrs)
        app.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "log_filename": ("Where messages should be logged to",(str,None)),
            "log_format_in": ("Format of incoming message log entries",(str,None)),
            "log_format_out": ("Format of outgoing message log entries",(str,None)),
            }
        self.settings={
                "log_filename": "%($HOME)s/.cjc/logs/chats/%(J:room:bare)s",
                "log_format_in": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
                "log_format_out": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
                }
        ui.activate_cmdtable("muc",self)
        self.room_manager=None

    def cmd_join(self,args):
        room_jid=args.shift()
        if not room_jid:
            self.error("/join without arguments")
            return
        room_jid=pyxmpp.JID(room_jid)
        if room_jid.resource or not room_jid.node:
            self.error("Bad room JID")
            return

        if not self.cjc.stream:
            self.error("Connect first!")
            return

        room_handler=Room(self,room_jid,self.cjc.stream.jid)
        self.room_manager.join(room_jid,self.cjc.stream.jid.node,room_handler)
        self.cjc.screen.display_buffer(room_handler.buffer)

    def session_started(self,stream):
        if not self.room_manager:
            self.room_manager=muc.MucRoomManager(stream)
        else:
            self.room_manager.set_stream(stream)
        self.room_manager.set_handlers()

    def log_message(self,dir,sender,recipient,subject,body,thread):
        #FIXME
        return
        format=self.settings["log_format_"+dir]
        filename=self.settings["log_filename"]
        d={
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "thread": thread
            }
        if dir=="in":
            d["peer"]=sender
        else:
            d["peer"]=recipient
        filename=self.cjc.theme_manager.substitute(filename,d)
        s=self.cjc.theme_manager.substitute(format,d)
        try:
            dirname=os.path.split(filename)[0]
            if dirname and not os.path.exists(dirname):
                os.makedirs(dirname)
            f=open(filename,"a")
            try:
                f.write(s.encode("utf-8","replace"))
            finally:
                f.close()
        except (IOError,OSError),e:
            self.cjc.error("Couldn't write chat log: "+str(e))

ui.CommandTable("muc",51,(
    ui.Command("join",Plugin.cmd_join,
        "/chat room_jid",
        "Join given Multi User Conference room",
        ("jid")),
    )).install()
# vi: sts=4 et sw=4
