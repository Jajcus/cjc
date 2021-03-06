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

import string
import curses
import os
import logging

import pyxmpp
from pyxmpp.jabber import muc,delay
from cjc import ui
from cjc.ui import CommandArgs
from cjc.ui.form_buffer import FormBuffer
from cjc.plugin import PluginBase
from cjc import common
from cjc import cjc_globals

theme_attrs=(
    ("muc.me", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("muc.to_me", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("muc.other", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
    ("muc.info", curses.COLOR_GREEN,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
    ("muc.nick",u"%(role?moderator:@,visitor:-,)s%(nick)s"),
    ("muc.userinfo",u"%(affiliation?none:, (%(affiliation)s))s%(role?participant:, (%(role)s))s%(real_jid? (JID\\: %(J\\:real_jid)s))s"),
    ("muc.nickinfo",u"%(nick)s%{@muc.userinfo}"),
    ("muc.joining",u"[%(T:timestamp)s] %[muc.info]* Joining MUC room %(room)s...\n"),
    ("muc.me",u"[%(T:timestamp)s] %[muc.me]<%{@muc.nick}>%[] %(msg)s\n"),
    ("muc.to_me",u"[%(T:timestamp)s] %[muc.other]<%{@muc.nick}>%[] %[muc.to_me]%(msg)s%[]\n"),
    ("muc.other",u"[%(T:timestamp)s] %[muc.other]<%{@muc.nick}>%[] %(msg)s\n"),
    ("muc.action",u"[%(T:timestamp)s] %[muc.info]* %{@muc.nick} %(msg)s\n"),
    ("muc.joined",u"[%(T:timestamp)s] %[muc.info]* %{@muc.nickinfo} has entered the room\n"),
    ("muc.me_joined",u"[%(T:timestamp)s] %[muc.info]* You%{@muc.userinfo} have entered the room\n"),
    ("muc.left",u"[%(T:timestamp)s] %[muc.info]* %(nick)s has left the room\n"),
    ("muc.me_left",u"[%(T:timestamp)s] %[muc.info]* You have left the room\n"),
    ("muc.role_changed",u"[%(T:timestamp)s] %[muc.info]* %(nick)s's role is now: %(role)s\n"),
    ("muc.my_role_changed",u"[%(T:timestamp)s] %[muc.info]* Your role is now: %(role)s\n"),
    ("muc.affiliation_changed",u"[%(T:timestamp)s] %[muc.info]* %(nick)s's affiliation is now: %(affiliation)s\n"),
    ("muc.my_affiliation_changed",u"[%(T:timestamp)s] %[muc.info]* Your affiliation is now: %(affiliation)s\n"),
    ("muc.nick_changed",u"[%(T:timestamp)s] %[muc.info]* %(old_nick)s is now known as: %(nick)s\n"),
    ("muc.my_nick_changed",u"[%(T:timestamp)s] %[muc.info]* Your are now known as: %(nick)s\n"),
    ("muc.presence_changed",u"[%(T:timestamp)s] %[muc.info]* %(nick)s is now: [%(show?%(show)s,online)s]%(status? %(status)s)s\n"),
    ("muc.info",u"[%(T:timestamp)s] %[muc.info]* %(msg)s\n"),
    ("muc.descr",u"Conference on %(J:room:bare)s"),
    ("muc.conf_descr",u"Configuration for conference %(J:room:bare)s"),
    ("muc.day_change",u"%{@day_change}"),
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
        self.buffer=ui.TextBuffer(self.fparams,
                "muc.descr","muc buffer",self)
        self.buffer.preference=plugin.settings["buffer_preference"]
        self.buffer.user_input=self.user_input
        self.buffer.get_completion_words=self.get_completion_words
        self.buffer.append_themed("muc.joining",self.fparams)
        self.buffer._muc_room = self
        self.buffer.update()

    def user_format_params(self,user):
        fparams=dict(self.fparams)
        fparams.update({
                "nick": user.nick,"jid": user.room_jid,
                "real_jid": user.real_jid, "role": user.role,
                "affiliation": user.affiliation,
                })
        if user.presence:
            fparams.update({
                    "show": user.presence.get_show(),
                    "status": user.presence.get_status(),
                    "available": user.presence.get_type()!="unavailable",
                    })
        else:
            fparams.update({
                    "show": u"",
                    "status": u"",
                    "available": False,
                    })
        return fparams

    def message_received(self,user,stanza):
        body=stanza.get_body()
        if not body:
            return
        if user:
            fparams=self.user_format_params(user)
        else:
            fparams=dict(self.fparams)
        d=delay.get_delay(stanza)
        if d:
            fparams["timestamp"]=d.get_datetime_local()
        if body.startswith(u"/me "):
            fparams["msg"]=body[4:]
            self.buffer.append_themed("muc.action",fparams)
            self.buffer.update()
            return
        else:
            fparams["msg"]=body
        fr=stanza.get_from()
        if user is None:
            self.buffer.append_themed("muc.info",fparams)
            self.buffer.update()
            return
        elif fr==self.room_state.room_jid:
            self.plugin.cjc.send_event("own groupchat message received",body)
            format="muc.me"
        elif self.room_state.me.nick.lower() in body.lower():
            self.plugin.cjc.send_event("groupchat message to me received",body)
            format="muc.to_me"
        else:
            self.plugin.cjc.send_event("groupchat message received",body)
            format="muc.other"
        self.buffer.append_themed(format,fparams)
        self.buffer.update()

    def subject_changed(self,user,stanza):
        if user:
            fparams=self.user_format_params(user)
        else:
            fparams=dict(self.fparams)
        if user:
            fparams["msg"]=(u"%s has changed the subject to: %s"
                    % (user.nick,self.room_state.subject))
        else:
            fparams["msg"]=(u"The subject has been changed to: %s"
                    % (self.room_state.subject,))
        d=delay.get_delay(stanza)
        if d:
            fparams["timestamp"]=d.get_datetime_local()
        self.plugin.cjc.send_event("groupchat subject changed",self.room_state.subject)
        self.buffer.append_themed("muc.info",fparams)
        self.buffer.update()
        return

    def user_joined(self, user, stanza):
        self.plugin.cjc.set_user_info(user.room_jid, "nick", user.nick)
        fparams = self.user_format_params(user)
        d = delay.get_delay(stanza)
        if d:
            fparams["timestamp"] = d.get_datetime_local()
        self.plugin.cjc.send_event("groupchat user joined", user.nick)
        if user.same_as(self.room_state.me):
            self.buffer.append_themed("muc.me_joined", fparams)
        else:
            self.buffer.append_themed("muc.joined", fparams)
        self.buffer.update()
        return

    def user_left(self,user,stanza):
        fparams=self.user_format_params(user)
        if stanza:
            d=delay.get_delay(stanza)
            if d:
                fparams["timestamp"]=d.get_datetime_local()
        self.plugin.cjc.send_event("groupchat user left",user.nick)
        if user.same_as(self.room_state.me):
            self.buffer.append_themed("muc.me_left",fparams)
        else:
            self.buffer.append_themed("muc.left",fparams)
        self.buffer.update()
        return

    def role_changed(self,user,old_role,new_role,stanza):
        fparams=self.user_format_params(user)
        d=delay.get_delay(stanza)
        if d:
            fparams["timestamp"]=d.get_datetime_local()
        if user.same_as(self.room_state.me):
            self.buffer.append_themed("muc.my_role_changed",fparams)
        else:
            self.buffer.append_themed("muc.role_changed",fparams)
        self.buffer.update()
        return

    def affiliation_changed(self,user,old_affiliation,new_affiliation,stanza):
        fparams=self.user_format_params(user)
        d=delay.get_delay(stanza)
        if d:
            fparams["timestamp"]=d.get_datetime_local()
        if user.same_as(self.room_state.me):
            self.buffer.append_themed("muc.my_affiliation_changed",fparams)
        else:
            self.buffer.append_themed("muc.affiliation_changed",fparams)
        self.buffer.update()
        return

    def nick_change(self,user,new_nick,stanza):
        self.buffer.append_themed("debug","Nick change started: %r -> %r" % (user.nick,new_nick))
        return True

    def nick_changed(self,user,old_nick,stanza):
        fparams=self.user_format_params(user)
        fparams["old_nick"]=old_nick
        d=delay.get_delay(stanza)
        if d:
            fparams["timestamp"]=d.get_datetime_local()
        if user.same_as(self.room_state.me):
            self.buffer.append_themed("muc.my_nick_changed",fparams)
        else:
            self.buffer.append_themed("muc.nick_changed",fparams)
        self.buffer.update()
        return

    def presence_changed(self,user,stanza):
        fr=stanza.get_from()
        available=stanza.get_type()!="unavailable"
        old_presence=self.plugin.cjc.get_user_info(fr,"presence")
        if available:
            self.plugin.cjc.set_user_info(fr,"presence",stanza.copy())
        else:
            self.plugin.cjc.set_user_info(fr,"presence",None)
        if not old_presence:
            return
        if (available and
                (stanza.get_show()!=old_presence.get_show()
                or stanza.get_status()!=old_presence.get_status())):
            fparams=self.user_format_params(user)
            self.buffer.append_themed("muc.presence_changed",fparams)
            self.buffer.update()

    def room_created(self, stanza):
        self.buffer.append_themed("muc.info","New room created. It must be configured before use.")
        self.buffer.update()
        self.buffer.ask_question("[C]onfigure or [A]ccept defaults", "choice", "a",
                self.initial_configuration_choice, values = ("a", "c"), required = True)

    def initial_configuration_choice(self, response):
        if response == "a":
            self.room_state.request_instant_room()
        else:
            self.room_state.request_configuration_form()

    def configuration_form_received(self, form):
        form_buffer = FormBuffer(self.fparams, "muc.conf_descr")
        form_buffer.set_form(form, self.configuration_callback)
        cjc_globals.screen.display_buffer(form_buffer)

    def configuration_callback(self, form_buffer, form):
        form_buffer.close()
        self.room_state.configure_room(form)

    def room_configured(self):
        self.buffer.append_themed("muc.info","Room configured")
        self.buffer.update()

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

    def cmd_subject(self,args):
        subj=args.all()
        if not subj:
            if self.room_state.subject:
                self.buffer.append_themed("info",u"The room subject is: %s" % (self.room_state.subject,))
            else:
                self.buffer.append_themed("info",u"The room has no subject")
            self.buffer.update()
            return 1
        self.room_state.set_subject(subj)
        return 1

    def cmd_who(self, args):
        nicks = u','.join(self.room_state.users.keys())
        self.buffer.append(nicks + u"\n")
        self.buffer.update()
        
    def cmd_nick(self,args):
        new_nick=args.all()
        if not args:
            raise CommandError,"No nickname given"
        if not self.room_state.joined:
            self.buffer.append_themed("error","You are not in the room")
            self.buffer.update()
            return 1
        self.room_state.change_nick(new_nick)
        return 1

    def cmd_query(self, args):
        nick = args.shift()
        if not nick:
            raise CommandError,"No nickname given"
        if nick not in self.room_state.users:
            self.buffer.append_themed("error", "No '%s' in this room", nick)
            self.buffer.update()
            return 1
        user = self.room_state.users[nick]
        rest = args.all()
        args = u'"%s"' % (user.room_jid.as_unicode().replace('"', '\\"'), )
        if rest:
            args = ui.CommandArgs(args + u" " + rest)
        else:
            args = ui.CommandArgs(args)
        ui.run_command("chat", args)

    def cmd_leave(self,args):
        a=args.get()
        if a:
            self.plugin.cmd_leave(args)
        else:
            args.finish()
            self.room_state.leave()

    def cmd_close(self,args):
        args.finish()
        self.room_state.leave()
        self.buffer.close()
        return 1

    def cmd_configure(self,args):
        args.finish()
        self.room_state.request_configuration_form()
        return 1

    def get_completion_words(self):
        return [nick+u":" for nick in self.room_state.users.keys()]

class MucNickCompletion(ui.Completion):
    def __init__(self, app):
        ui.Completion.__init__(self)
        self.app = app
        self.__logger=logging.getLogger("plugins.muc.MucNickCompletion")

    def complete(self, word):
        self.__logger.debug("MucNickCompletion.complete(self,%r)" % (word,))
        active_window = cjc_globals.screen.active_window
        if not active_window:
            return "", []
        active_buffer = active_window.buffer
        if not active_window.buffer:
            return "", []
        try:
            muc_room = active_buffer._muc_room
        except AttributeError:
            return "", []

        matches=[]
        for w in muc_room.room_state.users.keys():
            if w.startswith(word):
                matches.append( [w, 1] )
        return self.make_result("", word,matches)

ui.CommandTable("muc buffer",51,(
    ui.Command("me",Room.cmd_me,
        "/me text",
        "Sends /me text",
        ("text",)),
    ui.Command("subject",Room.cmd_subject,
        "/subject text",
        "Sets the subject of the room",
        ("text",)),
    ui.Command("nick",Room.cmd_nick,
        "/nick text",
        "Changes the nickname used",
        ("text",)),
    ui.Command("who",Room.cmd_who,
        "/who ",
        "Lists users in this room",
        ("text",)),
    ui.Command("query", Room.cmd_query,
        "/query nick",
        "Starts a private chat",
        ("muc_nick",)),
    ui.CommandAlias("topic","subject"),
    ui.Command("leave",Room.cmd_leave,
        "/leave [jid]",
        "Leave the chat room",
        ("jid",)),
    ui.Command("configure",Room.cmd_configure,
        "/configure",
        "Configure the room"),
    ui.Command("close",Room.cmd_close,
        "/close",
        "Closes current chat buffer"),
    )).install()

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        cjc_globals.theme_manager.set_default_attrs(theme_attrs)
        cjc_globals.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "default_nick": ("Default nickname. If not give then node part of JID will be used",(unicode,None)),
            "buffer_preference": ("Preference of groupchat buffers when switching to the next active buffer. If 0 then the buffer is not even shown in active buffer list.",int),
            "autojoin": ("List of rooms to join after connecting.",list),
            }
        self.settings={
                "buffer_preference": 10,
                "default_nick": None,
                "autojoin": None,
                }
        app.add_event_handler("day changed",self.ev_day_changed)
        app.add_event_handler("roster updated",self.autojoin)
        ui.activate_cmdtable("muc",self)
        self.room_manager=None
        MucNickCompletion(app).register("muc_nick")

    def cmd_join(self,args):
        if not self.cjc.stream:
            self.error("Connect first!")
            return
        arg1=args.shift()
        if not arg1:
            self.error("/join without arguments")
            return
        if arg1=="-nick":
            nick=args.shift()
            room_jid=args.shift()
        else:
            nick=self.settings.get("default_nick")
            if not nick:
                nick=self.cjc.stream.me.node
            room_jid=arg1
        if not room_jid:
            self.error("Room name not given")
            return
        room_jid=pyxmpp.JID(room_jid)
        if room_jid.resource or not room_jid.node:
            self.error("Bad room JID")
            return
        if not self.cjc.stream:
            self.error("Connect first!")
            return
        rs=self.room_manager.get_room_state(room_jid)
        if rs and rs.joined:
            room_handler=rs.handler
        else:
            room_handler=Room(self,room_jid,self.cjc.stream.me)
            self.room_manager.join(room_jid,nick,room_handler)
        cjc_globals.screen.display_buffer(room_handler.buffer)

    def cmd_leave(self,args):
        room_jid=args.shift()
        if not room_jid:
            self.error("/leave without arguments and current buffer is not a group chat")
            return
        room_jid=pyxmpp.JID(room_jid)
        if room_jid.resource or not room_jid.node:
            self.error("Bad room JID")
            return
        rs=self.room_manager.get_room_state(room_jid)
        if rs:
            rs.leave()
        else:
            self.error("Not in the room")

    def autojoin(self,event,arg):
        if arg is None:
            rooms=self.settings.get("autojoin")
            if rooms:
                for room in rooms:
                    room = CommandArgs(room)
                    self.cmd_join(room)

    def session_started(self,stream):
        if not self.room_manager:
            self.room_manager=muc.MucRoomManager(stream)
        else:
            self.room_manager.set_stream(stream)
        self.room_manager.set_handlers()

    def ev_day_changed(self,event,arg):
        if not self.room_manager:
            return
        for room in self.room_manager.rooms.values():
            room.handler.buffer.append_themed("muc.day_change",{},activity_level=0)
            room.handler.buffer.update()

ui.CommandTable("muc",50,(
    ui.Command("join",Plugin.cmd_join,
        "/join [-nick nick] room_jid",
        "Join given Multi User Conference room",
        ("-nick opaque","jid")),
    ui.Command("leave",Plugin.cmd_leave,
        "/leave room_jid",
        "Leave given Multi User Conference room",
        ("jid")),
    )).install()
# vi: sts=4 et sw=4
