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

import string
import curses
import os

import pyxmpp
from pyxmpp.jabber import delay
from cjc import ui
from cjc.plugin import PluginBase
from cjc import common

theme_attrs=(
    ("chat.me", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("chat.peer", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
    ("chat.info", curses.COLOR_GREEN,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
    ("chat.started",u"[%(T:timestamp)s] %[chat.info]* Chat with %(J:peer)s started\n"),
    ("chat.me",u"[%(T:timestamp)s] %[chat.me]<%(J:me:nick)s>%[] %(msg)s\n"),
    ("chat.peer",u"[%(T:timestamp)s] %[chat.peer]<%(J:peer:nick)s>%[] %(msg)s\n"),
    ("chat.action",u"[%(T:timestamp)s] %[chat.info]* %(J:jid:nick)s %(msg)s\n"),
    ("chat.descr",u"Chat with %(J:peer:full)s [%(J:peer:show)s] %(J:peer:status)s"),
    ("chat.day_change",u"%{@day_change}"),
)

class Conversation:
    def __init__(self,plugin,me,peer,thread=None):
        self.plugin=plugin
        self.me=me
        self.peer=peer
        if thread:
            self.thread=thread
            self.thread_inuse=1
        else:
            plugin.last_thread+=1
            self.thread="chat-thread-%i" % (plugin.last_thread,)
            self.thread_inuse=0
        self.fparams={
            "peer":self.peer,
            "jid":self.me,
        }
        self.buffer=ui.TextBuffer(plugin.cjc.theme_manager,self.fparams,"chat.descr",
                "chat buffer",self)
        self.buffer.preference=plugin.settings["buffer_preference"]
        self.buffer.user_input=self.user_input
        self.buffer.append_themed("chat.started",self.fparams)
        self.buffer.update()

    def change_peer(self,peer):
        self.peer=peer
        self.fparams["peer"]=peer
        self.buffer.update_info(self.fparams)

    def add_msg(self,s,format,who,timestamp=None):
        fparams=dict(self.fparams)
        fparams["jid"]=who
        if timestamp:
            fparams["timestamp"]=timestamp
        if s.startswith(u"/me "):
            fparams["msg"]=s[4:]
            self.buffer.append_themed("chat.action",fparams)
            self.buffer.update()
            return
        fparams["msg"]=s
        self.buffer.append_themed(format,fparams)
        self.buffer.update()

    def add_sent(self,s):
        self.add_msg(s,"chat.me",self.me)

    def add_received(self,s,timestamp):
        self.add_msg(s,"chat.peer",self.peer,timestamp)

    def user_input(self,s):
        if not self.plugin.cjc.stream:
            self.buffer.append_themed("error","Not connected")
            self.buffer.update()
            return 0
        if self.plugin.settings.get("log_filename"):
            self.plugin.log_message("out",self.me,self.peer,None,s,self.thread)
        m=pyxmpp.Message(to_jid=self.peer,stanza_type="chat",body=s,thread=self.thread)
        self.plugin.cjc.stream.send(m)
        self.add_sent(s)
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
        key=self.peer.bare().as_unicode()
        if self.plugin.conversations.has_key(key):
            l=self.plugin.conversations[key]
            if self in l:
                l.remove(self)
        self.buffer.close()
        return 1

    def cmd_whois(self,args):
        self.buffer.deactivate_command_table()
        try:
            if not args.get():
                args=ui.CommandArgs(self.peer.as_unicode())
            ui.run_command("whois",args)
        finally:
            self.buffer.activate_command_table()

    def cmd_info(self,args):
        self.buffer.deactivate_command_table()
        try:
            if not args.get():
                args=ui.CommandArgs(self.peer.as_unicode())
            ui.run_command("info",args)
        finally:
            self.buffer.activate_command_table()


ui.CommandTable("chat buffer",50,(
    ui.Command("me",Conversation.cmd_me,
        "/me text",
        "Sends /me text",
        ("text",)),
    ui.Command("close",Conversation.cmd_close,
        "/close",
        "Closes current chat buffer"),
    ui.Command("whois",Conversation.cmd_whois,
        "/whois [options] [user]",
        None),
    ui.Command("info",Conversation.cmd_info,
        "/info [options] [user]",
        None),
    )).install()

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        self.conversations={}
        self.last_thread=0
        app.theme_manager.set_default_attrs(theme_attrs)
        app.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "log_filename": ("Where messages should be logged to",(str,None)),
            "log_format_in": ("Format of incoming message log entries",(str,None)),
            "log_format_out": ("Format of outgoing message log entries",(str,None)),
            "buffer_preference": ("Preference of chat buffers when switching to the next active buffer. If 0 then the buffer is not even shown in active buffer list.",int),
            "auto_popup": ("When enabled each new chat buffer is automatically made active.",bool),
            }
        self.settings={
                "log_filename": "%($HOME)s/.cjc/logs/chats/%(J:peer:bare)s",
                "log_format_in": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
                "log_format_out": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
                "buffer_preference": 100,
                "auto_popup": False,
                }
        app.add_event_handler("presence changed",self.ev_presence_changed)
        app.add_event_handler("day changed",self.ev_day_changed)
        ui.activate_cmdtable("chat",self)

    def cmd_chat(self,args):
        peer=args.shift()
        if not peer:
            self.error("/chat without arguments")
            return

        if not self.cjc.stream:
            self.error("Connect first!")
            return

        peer=self.cjc.get_best_user(peer)
        if peer is None:
            return

        conversation=Conversation(self,self.cjc.jid,peer)
        key=peer.bare().as_unicode()
        if self.conversations.has_key(key):
            self.conversations[key].append(conversation)
        else:
            self.conversations[key]=[conversation]

        text=args.all()
        if text:
            conversation.user_input(text)

        self.cjc.screen.display_buffer(conversation.buffer)

    def ev_presence_changed(self,event,arg):
        key=arg.bare().as_unicode()
        if not self.conversations.has_key(key):
            return
        for conv in self.conversations[key]:
            if conv.peer==arg or conv.peer==arg.bare():
                conv.buffer.update_info(conv.fparams)

    def ev_day_changed(self,event,arg):
        for convs in self.conversations.values():
            for conv in convs:
                conv.buffer.append_themed("chat.day_change",{},activity_level=0)
                conv.buffer.update()

    def session_started(self,stream):
        self.cjc.stream.set_message_handler("chat",self.message_chat)
        self.cjc.stream.set_message_handler("error",self.message_error,None,90)

    def message_error(self,stanza):
        fr=stanza.get_from()
        thread=stanza.get_thread()
        key=fr.bare().as_unicode()

        conv=None
        if self.conversations.has_key(key):
            convs=self.conversations[key]
            for c in convs:
                if not thread and (not c.thread or not c.thread_inuse):
                    conv=c
                    break
                if thread and thread==c.thread:
                    conv=c
                    break
            if conv and conv.thread and not thread:
                conv.thread=None
            elif conv and thread:
                conv.thread_inuse=1

        if not conv:
            return 0

        conv.error(stanza)
        return 1

    def message_chat(self,stanza):
        fr=stanza.get_from()
        thread=stanza.get_thread()
        subject=stanza.get_subject()
        body=stanza.get_body()
        if body is None:
            body=u""
        if subject:
            body=u"%s: %s" % (subject,body)
        elif not body:
            return

        d=delay.get_delay(stanza)
        if d:
            timestamp=d.get_datetime_local()
        else:
            timestamp=None
        if self.settings.get("log_filename"):
            self.log_message("in",fr,self.cjc.jid,subject,body,thread,timestamp)

        key=fr.bare().as_unicode()
        conv=None
        if self.conversations.has_key(key):
            convs=self.conversations[key]
            for c in convs:
                if not thread and (not c.thread or not c.thread_inuse):
                    conv=c
                    break
                if thread and thread==c.thread:
                    conv=c
                    break
            if conv and conv.thread and not thread:
                conv.thread=None
            elif conv and thread:
                conv.thread_inuse=1

        if not conv:
            conv=Conversation(self,self.cjc.jid,fr,thread)
            if self.conversations.has_key(key):
                self.conversations[key].append(conv)
            else:
                self.conversations[key]=[conv]
            if self.settings.get("auto_popup"):
                self.cjc.screen.display_buffer(conv.buffer)
            else:
                conv.buffer.update()
        else:
            if fr!=conv.peer:
                conv.change_peer(fr)

        self.cjc.send_event("chat message received",body)
        conv.add_received(body,timestamp)
        return 1

    def log_message(self,dir,sender,recipient,subject,body,thread,timestamp=None):
        format=self.settings["log_format_"+dir]
        filename=self.settings["log_filename"]
        d={
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "thread": thread
            }
        if timestamp:
            d["timestamp"]=timestamp
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
            self.error("Couldn't write chat log: "+str(e))

ui.CommandTable("chat",51,(
    ui.Command("chat",Plugin.cmd_chat,
        "/chat nick|jid [text]",
        "Start chat with given user",
        ("user","text")),
    )).install()
# vi: sts=4 et sw=4
