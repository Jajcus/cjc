import string
import curses
import os

import pyxmpp
from pyxmpp.jabber import muc,delay
from cjc import ui
from cjc.plugin import PluginBase
from cjc import common

theme_attrs=(
    ("muc.me", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("muc.to_me", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("muc.other", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
    ("muc.info", curses.COLOR_GREEN,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
    ("muc.nick","%(role?moderator:@,visitor:-,)s%(nick)s"),
    ("muc.userinfo","%(affiliation?none:, (%(affiliation)s))s%(role?participant:, (%(role)s))s%(real_jid? (JID: %(real_jid)s))s"),
    ("muc.nickinfo","%(nick)s%{@muc.userinfo}"),
    ("muc.joining","[%(T:timestamp)s] %[muc.info]* Joining MUC room %(room)s...\n"),
    ("muc.me","[%(T:timestamp)s] %[muc.me]<%{@muc.nick}>%[] %(msg)s\n"),
    ("muc.to_me","[%(T:timestamp)s] %[muc.other]<%{@muc.nick}>%[] %[muc.to_me]%(msg)s%[]\n"),
    ("muc.other","[%(T:timestamp)s] %[muc.other]<%{@muc.nick}>%[] %(msg)s\n"),
    ("muc.action","[%(T:timestamp)s] %[muc.info]* %{@muc.nick} %(msg)s\n"),
    ("muc.joined","[%(T:timestamp)s] %[muc.info]* %{@muc.nickinfo} has entered the room\n"),
    ("muc.me_joined","[%(T:timestamp)s] %[muc.info]* You%{@muc.userinfo} have entered the room\n"),
    ("muc.left","[%(T:timestamp)s] %[muc.info]* %(nick)s has left the room\n"),
    ("muc.me_left","[%(T:timestamp)s] %[muc.info]* You have left the room\n"),
    ("muc.role_changed","[%(T:timestamp)s] %[muc.info]* %(nick)s's role is now: %(role)s\n"),
    ("muc.my_role_changed","[%(T:timestamp)s] %[muc.info]* Your role is now: %(role)s\n"),
    ("muc.affiliation_changed","[%(T:timestamp)s] %[muc.info]* %(nick)s's affiliation is now: %(affiliation)s\n"),
    ("muc.my_affiliation_changed","[%(T:timestamp)s] %[muc.info]* Your affiliation is now: %(affiliation)s\n"),
    ("muc.nick_changed","[%(T:timestamp)s] %[muc.info]* %(old_nick)s is now known as: %(nick)s\n"),
    ("muc.my_nick_changed","[%(T:timestamp)s] %[muc.info]* Your are now known as: %(nick)s\n"),
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
        self.buffer.preference=plugin.settings["buffer_preference"]
        self.buffer.user_input=self.user_input
        self.buffer.get_completion_words=self.get_completion_words
        self.buffer.append_themed("muc.joining",self.fparams)
        self.buffer.update()

    def user_format_params(self,user):
        fparams=dict(self.fparams)
        fparams.update({"nick": user.nick,"jid": user.room_jid,"real_jid": user.real_jid,
                "role": user.role, "affiliation": user.affiliation})
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
            fparams["timestamp"]=d.datetime_local()
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
            format="muc.me"
        elif self.room_state.me.nick.lower() in body.lower():
            format="muc.to_me"
        else:
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
            fparams["timestamp"]=d.datetime_local()
        self.buffer.append_themed("muc.info",fparams)
        self.buffer.update()
        return

    def user_joined(self,user,stanza):
        fparams=self.user_format_params(user)
        d=delay.get_delay(stanza)
        if d:
            fparams["timestamp"]=d.datetime_local()
        if user.same_as(self.room_state.me):
            self.buffer.append_themed("muc.me_joined",fparams)
        else:
            self.buffer.append_themed("muc.joined",fparams)
        self.buffer.update()
        return

    def user_left(self,user,stanza):
        fparams=self.user_format_params(user)
        d=delay.get_delay(stanza)
        if d:
            fparams["timestamp"]=d.datetime_local()
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
            fparams["timestamp"]=d.datetime_local()
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
            fparams["timestamp"]=d.datetime_local()
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
            fparams["timestamp"]=d.datetime_local()
        if user.same_as(self.room_state.me):
            self.buffer.append_themed("muc.my_nick_changed",fparams)
        else:
            self.buffer.append_themed("muc.nick_changed",fparams)
        self.buffer.update()
        return

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

    def get_completion_words(self):
        return [nick+u":" for nick in self.room_state.users.keys()]

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
    ui.CommandAlias("topic","subject"),
    ui.Command("leave",Room.cmd_leave,
        "/leave [jid]",
        "Leave the chat room",
        ("jid",)),
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
            "log_filename": ("Where messages should be logged to",(unicode,None)),
            "log_format_in": ("Format of incoming message log entries",(unicode,None)),
            "log_format_out": ("Format of outgoing message log entries",(unicode,None)),
            "default_nick": ("Default nickname. If not give then node part of JID will be used",(unicode,None)),
            "buffer_preference": ("Preference of groupchat buffers when switching to the next active buffer. If 0 then the buffer is not even shown in active buffer list.",int),
            }
        self.settings={
                "log_filename": "%($HOME)s/.cjc/logs/chats/%(J:room:bare)s",
                "log_format_in": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
                "log_format_out": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
                "buffer_preference": 10,
                "default_nick": None,
                }
        ui.activate_cmdtable("muc",self)
        self.room_manager=None

    def cmd_join(self,args):
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
                nick=self.cjc.stream.jid.node
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
            room_handler=Room(self,room_jid,self.cjc.stream.jid)
            self.room_manager.join(room_jid,nick,room_handler)
        self.cjc.screen.display_buffer(room_handler.buffer)

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

ui.CommandTable("muc",50,(
    ui.Command("join",Plugin.cmd_join,
        "/join room_jid",
        "Join given Multi User Conference room",
        ("jid")),
    ui.Command("leave",Plugin.cmd_leave,
        "/leave room_jid",
        "Leave given Multi User Conference room",
        ("jid")),
    )).install()
# vi: sts=4 et sw=4
