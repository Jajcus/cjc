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

import string
import curses
import os
import locale
import tempfile
import re

import pyxmpp
from cjc import ui
from cjc.plugin import PluginBase
from cjc import common
from pyxmpp.jabber import delay

theme_attrs=(
    ("message.date", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("message.subject", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("message.sender", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("message.body", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
    ("message.received",
u"""------------------
%[message.date]Date:    %(T:timestamp:%c)s
%[message.sender]From:    %(J:from)s
%[message.subject]Subject: %(subject)s

%[message.body]%(body)s
------------------
"""),
    ("message.sent",
u"""------------------
%[message.date]Date:    %(T:timestamp:%c)s
%[message.sender]To:      %(J:to)s
%[message.subject]Subject: %(subject)s

%[message.body]%(body)s
------------------
"""),
    ("message.composing",
u"""------------------
%[message.date]Date:    %(T:timestamp:%c)s
%[message.sender]To:      %(J:from)s
%[message.subject]Subject: %(subject)s

%[message.body]%(body)s
------------------
"""),
    ("message.descr-per-user","Messages from %(J:peer:full)s [%(J:peer:show)s] %(J:peer:status)s"),
    ("message.descr","Messages"),
    ("message.composer_descr","Composed message"),
    ("message.day_change",""),
)

class Composer(ui.TextBuffer):
    message_template=u"""To: %(recipient)s
Subject: %(subject)s

%(body)s
"""
    hdr_nocont_re=re.compile("\r?\n(?![ \t])")
    def __init__(self,plugin):
        self.buffer=ui.TextBuffer(plugin.cjc.theme_manager,{},
                "message.composer_descr")
        self.plugin=plugin
        self.tmpfile_name=None
        self.recipient=None
        self.subject=None
        self.body=None

    def __del__(self):
        if self.buffer:
            self.buffer.close()
        if self.tmpfile_name:
            try:
                os.unlink(self.tmpfile_name)
            except OSError:
                pass

    def fill_template(self,recipient,subject,body):
        if not recipient:
            recipient=u""
        else:
            recipient=unicode(recipient)
        if not subject:
            subject=u""
        else:
            subject=self.hdr_nocont_re.sub("\t\n",subject)
        if not body:
            body=u""
        template=self.message_template % {
                "recipient":recipient,
                "subject":subject,
                "body":body}
        return template

    def start(self,recipient,subject,body):
        template=self.fill_template(recipient,subject,body)
        editor_encoding=self.plugin.settings.get("editor_encoding",
                locale.getlocale()[1])
        try:
            template=template.encode(editor_encoding,"strict")
        except UnicodeError:
            self.plugin.error(u"Cannot encode message or address to the editor encoding.")
            return False

        try:
            (tmpfd,self.tmpfile_name)=tempfile.mkstemp(
                    prefix="cjc-",suffix=".txt")
        except (IOError,OSError),e:
            self.plugin.error(u"Cannot create a temporary file: %s" % (e,))
            return False
        try:
            tmpfile=os.fdopen(tmpfd,"w+b")
            tmpfile.write(template)
            tmpfile.close()
        except (IOError,OSError),e:
            self.plugin.error(u"Cannot write the temporary file %r (fd: %i): %s"
                    % (self.tmpfile_name,tmpfd,e))
            return False
        return self.edit_message()

    def edit_message(self):
        self.buffer.clear()
        editor=self.plugin.settings.get("editor",os.environ.get("EDITOR","vi"))
        command="%s %s" % (editor,self.tmpfile_name)
        ok=True
        try:
            self.plugin.cjc.screen.shell_mode()
            try:
                ret=os.system(command)
            finally:
                self.plugin.cjc.screen.prog_mode()
        except (OSError,),e:
            self.error(u"Couldn't start the editor: %s" % (e,))
            ok=False
        if ret:
            es=os.WEXITSTATUS(ret)
            if not os.WIFEXITED(ret):
                self.error(u"Editor exited abnormally")
            elif es:
                self.warning(u"Editor exited with status %i" % (es,))
            ok=False

        self.plugin.cjc.screen.display_buffer(self.buffer)
        if not ok:
            self.buffer.ask_question(u"Try to [E]dit again or [C]ancel?",
                    "choice",None,self.send_edit_cancel,values=("ec"))
            return True

        try:
            tmpfile=open(self.tmpfile_name,"r")
            try:
                msg=tmpfile.read()
            finally:
                try:
                    tmpfile.close()
                except IOError:
                    pass
        except IOError:
            self.plugin.cjc.error(u"Error reading the edited message!")
            return

        self.buffer.append(msg)
        recipient=None
        subject=None
        if u"\n\n" in msg:
            ok=True
            header,body=msg.split(u"\n\n",1)
            headers=self.hdr_nocont_re.split(header)
            for h in headers:
                if ":" not in h:
                    self.error(u"Bad header: %r" % (h,))
                    ok=False
                    break
                name,value=h.split(":",1)
                name=name.strip().lower()
                value=value.strip()
                if name==u"subject":
                    if subject:
                        self.error(u"More than one subject!")
                        ok=False
                        break
                    subject=value
                if name==u"to":
                    if recipient:
                        self.error(u"More than one recipient!")
                        ok=False
                        break
                    recipient=self.plugin.cjc.get_user(value)
                    if not recipient:
                        self.error(u"Bad recipient: %r!" % (recipient,))
                        ok=False
                        break
            if not recipient:
                self.error(u"No recipient!")
                ok=False
        else:
            self.error(u"Could not find header or body in the message")
            ok=False

        if not ok:
            self.buffer.ask_question(u"Errors found. [E]dit again or [C]ancel?",
                    "choice",None,self.send_edit_cancel,values=("ec"))
            return True

        self.buffer.clear()
        msg=self.fill_template(recipient,subject,body)
        self.buffer.append(msg)
        self.buffer.update()
        self.recipient=recipient
        self.subject=subject
        self.body=body
        self.buffer.ask_question(u"[S]end, [E]dit or [C]ancel?",
                "choice",None,self.send_edit_cancel,values=("sec"))
        return True

    def send_edit_cancel(self,arg,choice):
        if choice in "sS":
            self.plugin.send_message(recipient=self.recipient,
                    subject=self.subject,body=self.body)
            self.buffer.close()
            self.buffer=None
        elif choice in "eE":
            self.edit_message()
        else:
            self.buffer.close()
            self.buffer=None

    def error(self,msg):
        self.buffer.append_themed("error",msg)
        self.buffer.update()

    def warning(self,msg):
        self.buffer.append_themed("warning",msg)
        self.buffer.update()

class MessageBuffer:
    def __init__(self,plugin,peer,thread):
        self.plugin=plugin
        self.peer=peer
        self.thread=thread
        if peer:
            self.buffer=ui.TextBuffer(plugin.cjc.theme_manager,{"peer":self.peer},
                    "message.descr-per-user","message buffer",self)
        else:
            self.buffer=ui.TextBuffer(plugin.cjc.theme_manager,{},"message.descr",
                    "message buffer",self)
        self.buffer.preference=plugin.settings["buffer_preference"]
        self.buffer.update()
        self.last_sender=None
        self.last_subject=None
        self.last_body=None
        self.last_thread=None

    def add_received(self,sender,subject,body,thread,timestamp):
        d={
                "from": sender,
                "subject": subject,
                "thread": thread,
                "body": body,
                }
        if timestamp:
            d["timestamp"]=timestamp
        self.buffer.append_themed("message.received",d)
        self.buffer.update()
        self.last_sender=sender
        self.last_subject=subject
        self.last_body=body
        self.last_thread=thread

    def add_sent(self,recipient,subject,body,thread):
        self.buffer.append_themed("message.sent",{
                "to": recipient,
                "subject": subject,
                "thread": thread,
                "body": body,
                })
        self.buffer.update()

    def error(self,stanza):
        err=stanza.get_error()
        emsg=err.get_message()
        msg=u"Error"
        if emsg:
            msg+=u": %s" % emsg
        etxt=err.get_text()
        if etxt:
            msg+=u" ('%s')" % etxt
        self.buffer.append_themed("error",msg)
        self.buffer.update()

    def cmd_close(self,args):
        args.finish()
        if self.peer:
            key=self.peer.bare().as_unicode()
        else:
            key=None
        if self.plugin.buffers.has_key(key):
            l=self.plugin.buffers[key]
            if self in l:
                l.remove(self)
        self.buffer.close()
        return 1

    def cmd_reply(self,args):
        if not self.last_sender:
            self.buffer.append_themed("error","No message to reply to")
            return
        arg1=args.get()
        if arg1=="-subject":
            args.shift()
            subject=args.shift()
            if not subject:
                self.buffer.append_themed("error","subject argument missing")
                return
        else:
            if self.last_subject:
                if self.last_subject.startswith(u"Re:"):
                    subject=self.last_subject
                else:
                    subject=u"Re: "+self.last_subject
            else:
                subject=None

        if not self.plugin.cjc.stream:
            self.buffer.append_themed("error","Not connected!")
            return

        body=args.all()
        if not body:
            self.buffer.append_themed("error",u"Message composition not supported yet"
                " - you must include message body on the command line")
            return

        self.plugin.send_message(self.last_sender,subject,body,self.last_thread)

ui.CommandTable("message buffer",50,(
    ui.Command("close", MessageBuffer.cmd_close,
        "/close",
        "Closes current chat buffer"),
    ui.Command("reply", MessageBuffer.cmd_reply,
        "/reply [-subject subject] [text]",
        "Reply to the last message in window",
        ("-subject opaque","text")),
    )).install()

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        self.buffers={}
        self.last_thread=0
        app.theme_manager.set_default_attrs(theme_attrs)
        app.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "buffer": ("How received messages should be put in buffers"
                    " (single|separate|per-user|per-thread)",
                    ("single","separate","per-user","per-thread")),
            "log_filename": ("Where messages should be logged to",(str,None)),
            "log_format_in": ("Format of incoming message log entries",(str,None)),
            "log_format_out": ("Format of outgoing message log entries",(str,None)),
            "buffer_preference": ("Preference of message buffers when switching to the next active buffer. If 0 then the buffer is not even shown in active buffer list.",int),
            "auto_popup": ("When enabled each new message buffer is automaticaly made active.",bool),
            "editor": ("Editor for message composition. Default: $EDITOR or 'vi'",str),
            "editor_encoding": ("Character encoding for edited messages. Default: locale specific",str),
            }
        self.settings={
                "buffer":"per-user",
                "log_filename": u"%($HOME)s/.cjc/logs/messages/%(J:peer:bare)s",
                "log_format_in": u"[%(T:now:%c)s] Incoming message\n"
                        "From: %(sender)s\n"
                        "Subject: %(subject)s\n%(body)s\n",
                "log_format_out": u"[%(T:now:%c)s] Outgoing message\n"
                        "To: %(recipient)s\n"
                        "Subject: %(subject)s\n%(body)s\n",
                "buffer_preference": 50,
                "auto_popup": False,
                }
        app.add_event_handler("presence changed",self.ev_presence_changed)
        app.add_event_handler("day changed",self.ev_day_changed)
        ui.activate_cmdtable("message",self)

    def cmd_message(self,args):
        arg1=args.shift()
        if arg1=="-subject":
            subject=args.shift()
            if not subject:
                self.error("subject argument missing")
                return
            recipient=args.shift()
        else:
            subject=None
            recipient=arg1

        if not self.cjc.stream:
            self.error("Connect first!")
            return

        if not recipient:
            self.compose_message(subject=subject)
            return

        recipient=self.cjc.get_user(recipient)
        if not recipient:
            return

        body=args.all()
        if not body:
            self.compose_message(recipient,subject)
            return

        self.send_message(recipient,subject,body)

    def compose_message(self,recipient=None,subject=None,body=None):
        composer=Composer(self)
        return composer.start(recipient,subject,body)

    def send_message(self,recipient,subject,body,thread=0,buff=None):
        if thread==0:
            self.last_thread+=1
            thread="message-thread-%i" % (self.last_thread,)
        m=pyxmpp.Message(to_jid=recipient,stanza_type="normal",subject=subject,body=body,thread=thread)
        self.cjc.stream.send(m)
        if buff is None:
            buff=self.find_or_make(recipient,thread)
        if self.settings.get("log_filename"):
            self.log_message("out",self.cjc.jid,recipient,subject,body,thread)
        buff.add_sent(recipient,subject,body,thread)

    def ev_presence_changed(self,event,arg):
        key=arg.bare().as_unicode()
        if not self.buffers.has_key(key):
            return
        for buff in self.buffers[key]:
            if buff.peer==arg or buff.peer==arg.bare():
                buff.buffer.update()

    def ev_day_changed(self,event,arg):
        for buffers in self.buffers.values():
            for buf in buffers:
                buf.buffer.append_themed("message.day_change",{},activity_level=0)
                buf.buffer.update()

    def session_started(self,stream):
        self.cjc.stream.set_message_handler("normal",self.message_normal)
        self.cjc.stream.set_message_handler("error",self.message_error,None,90)

    def find_buffer(self,user,thread):
        buff=None
        if user:
            key=user.bare().as_unicode()
        else:
            key=user
        if self.buffers.has_key(key):
            buffs=self.buffers[key]
            for b in buffs:
                if thread==b.thread:
                    buff=b
                    break
        return buff

    def find_or_make(self,user,thread):
        bset=self.settings["buffer"]
        if bset=="separate":
            pass
        elif bset=="per-thread":
            buff=self.find_buffer(user,thread)
            if buff:
                return buff
        elif bset=="per-user":
            buff=self.find_buffer(user,None)
            if buff:
                return buff
            thread=None
        else:
            buff=self.find_buffer(None,None)
            if buff:
                return buff
            thread=None
            user=None
        buff=MessageBuffer(self,user,thread)
        if user:
            key=user.bare().as_unicode()
        else:
            key=user
        if not self.buffers.has_key(key):
            self.buffers[key]=[buff]
        else:
            self.buffers[key].append(buff)
        if self.settings.get("auto_popup"):
            self.cjc.screen.display_buffer(buff)
        return buff

    def message_error(self,stanza):
        if self.settings["buffer"]=="separate":
            return 0
        fr=stanza.get_from()
        thread=stanza.get_thread()

        buff=self.find_buffer(fr,thread)
        bset=self.settings["buffer"]
        if not buff and bset in ("per-thread","per-user","single"):
            buff=self.find_buffer(fr,thread)
        if not buff and bset in ("per-user","single"):
            buff=self.find_buffer(fr,None)
        if not buff and bset=="single":
            buff=self.find_buffer(None,None)
        if not buff:
            return 0
        buff.error(stanza)
        return 1

    def message_normal(self,stanza):
        fr=stanza.get_from()
        thread=stanza.get_thread()
        subject=stanza.get_subject()
        body=stanza.get_body()
        if not subject and not body:
            return
        if body is None:
            body=u""
        d=delay.get_delay(stanza)
        if d:
            timestamp=d.datetime_local()
        else:
            timestamp=None
        if self.settings.get("log_filename"):
            self.log_message("in",fr,self.cjc.jid,subject,body,thread,timestamp)
        buff=self.find_or_make(fr,thread)
        self.cjc.send_event("message received",body)
        buff.add_received(fr,subject,body,thread,timestamp)
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
        if dir=="in":
            d["peer"]=sender
        else:
            d["peer"]=recipient
        if timestamp:
            d["timestamp"]=timestamp
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
            self.cjc.error(u"Couldn't write message log: "+unicode(e))

ui.CommandTable("message",50,(
    ui.Command("message",Plugin.cmd_message,
        "/message [-subject subject] nick|jid [text]",
        "Compose or send message to given user",
        ("-subject opaque","user","text")),
    ui.CommandAlias("msg","message"),
    )).install()
# vi: sts=4 et sw=4
