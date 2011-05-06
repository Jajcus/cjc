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
import locale
import tempfile
import re
import uuid

from datetime import datetime
import logging

logger = logging.getLogger("cjc.plugin.message")

import pyxmpp
from cjc import ui
from cjc.plugin import PluginBase, Archiver, Archive
from cjc import common
from cjc import cjc_globals
from pyxmpp.jabber import delay

theme_attrs=(
    ("message.info", curses.COLOR_GREEN,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
    ("message.date", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("message.subject", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("message.sender", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("message.body", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
    ("message.archive_end", "%[message.info]----- message archive end -----"),
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
        self.buffer=ui.TextBuffer({}, "message.composer_descr")
        self.plugin=plugin
        self.tmpfile_name=None
        self.recipient=None
        self.subject=None
        self.body=None
        self.editor_encoding=None

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
        editor_encoding=self.plugin.settings.get("editor_encoding")
        if not editor_encoding:
            editor_encoding=self.plugin.cjc.settings.get("editor_encoding")
        if not editor_encoding:
            editor_encoding=locale.getlocale()[1]
        if not editor_encoding:
            editor_encoding="utf-8"
        self.editor_encoding=editor_encoding
        try:
            template = template.encode(editor_encoding,"strict")
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
        editor = self.plugin.settings.get("editor")
        if not editor:
            editor = self.plugin.settings.get("editor")
        if not editor: 
            editor = os.environ.get("EDITOR", "vi")
        command="%s %s" % (editor,self.tmpfile_name)
        ok=True
        try:
            cjc_globals.screen.shell_mode()
            try:
                ret=os.system(command)
            finally:
                cjc_globals.screen.prog_mode()
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

        cjc_globals.screen.display_buffer(self.buffer)
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
            self.plugin.error(u"Error reading the edited message!")
            return

        msg = msg.decode(self.editor_encoding)

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
                    recipient=self.plugin.cjc.get_best_user(value)
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

    def send_edit_cancel(self, choice):
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


class MessagesBuffer(ui.TextBuffer):
    def __init__(self, conversation):
        self.conversation = conversation
        try:
            self.archive = cjc_globals.application.plugins.get_service(Archive)
        except KeyError:
            self.archive = None
        if conversation.peer:
            ui.TextBuffer.__init__(self, {"peer": conversation.peer},
                "message.descr-per-user","message buffer", conversation)
        else:
            ui.TextBuffer__init__(self, {}, "message.descr",
                                    "message buffer", conversation)
        self.last_record = None

    def fill_top_underflow(self, lines_needed):
        if not self.archive:
            return
        if self.last_record:
            older_than = self.last_record
        else:
            older_than = self.conversation.start_time
        record_iter = self.archive.get_records('message', 
                        self.conversation.peer.bare(),
                        older_than = older_than, limit = lines_needed,
                        order = Archive.REVERSE_CHRONOLOGICAL)
        records = list(record_iter)
        if not records:
            return
        records.reverse()
        logger.debug("Got {0} records:".format(len(records)))
        for record_id, record in records:
            logger.debug("Record {0!r}: {1!r}".format(record_id, record))
            fparams = dict()
            if record.direction == "in":
                fparams["from"] = record.peer
                theme_fmt = "message.received"
            else:
                fparams["to"] = record.peer
                theme_fmt = "message.sent"
            if record.timestamp:
                fparams["timestamp"] = record.timestamp
            fparams["subject"] = record.subject
            fparams["thread"] = record.thread
            fparams["body"] = record.body
            self.append_themed(theme_fmt, fparams)
        self.append_themed("message.archive_end", {})
        self.last_record = records[0][0]


class Conversation:
    def __init__(self,plugin,peer,thread):
        self.start_time = None
        self.plugin=plugin
        self.peer=peer
        self.thread=thread
        self.buffer = MessagesBuffer(self)
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
         
        if not self.start_time:
            self.start_time = timestamp if timestamp else datetime.now()

        self.buffer.append_themed("message.received",d)
        self.buffer.update()
        self.last_sender=sender
        self.last_subject=subject
        self.last_body=body
        self.last_thread=thread

    def add_sent(self,recipient,subject,body,thread):
        if not self.start_time:
            self.start_time = datetime.now()
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
        msg=u"Error from %s" % (stanza.get_from().as_unicode(),)
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
        if self.plugin.conversations.has_key(key):
            l=self.plugin.conversations[key]
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
    ui.Command("close", Conversation.cmd_close,
        "/close",
        "Closes current chat buffer"),
    ui.Command("reply", Conversation.cmd_reply,
        "/reply [-subject subject] [text]",
        "Reply to the last message in window",
        ("-subject opaque","text")),
    )).install()

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        self.conversations={}
        cjc_globals.theme_manager.set_default_attrs(theme_attrs)
        cjc_globals.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "buffer": ("How received messages should be put in buffers"
                    " (single|separate|per-user|per-thread)",
                    ("single","separate","per-user","per-thread")),
            "buffer_preference": ("Preference of message buffers when switching to the next active buffer. If 0 then the buffer is not even shown in active buffer list.",int),
            "auto_popup": ("When enabled each new message buffer is automatically made active.",bool),
            "editor": ("Editor for message composition. Default: global 'editor' option, $EDITOR or 'vi'",str),
            "editor_encoding": ("Character encoding for edited messages. Default: locale specific",str),
            }
        self.settings={
                "buffer":"per-user",
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

        recipient=self.cjc.get_best_user(recipient)
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

    def send_message(self,recipient,subject,body,thread=0,conv=None):
        if thread==0:
            thread = unicode(uuid.uuid4())
        m=pyxmpp.Message(to_jid=recipient,stanza_type="normal",subject=subject,body=body,thread=thread)
        self.cjc.stream.send(m)
        if conv is None:
            conv=self.find_or_make(recipient,thread)

        conv.add_sent(recipient,subject,body,thread)

        archivers = self.cjc.plugins.get_services(Archiver)
        for archiver in archivers:
            archiver.log_event("message", recipient, 'out', None, subject, body, thread)

    def ev_presence_changed(self,event,arg):
        key=arg.bare().as_unicode()
        if not self.conversations.has_key(key):
            return
        for conv in self.conversations[key]:
            if conv.peer==arg or conv.peer==arg.bare():
                conv.buffer.update()

    def ev_day_changed(self,event,arg):
        for conversations in self.conversations.values():
            for conv in conversations:
                conv.buffer.append_themed("message.day_change",{},activity_level=0)
                conv.buffer.update()

    def session_started(self,stream):
        self.cjc.stream.set_message_handler("normal",self.message_normal)
        self.cjc.stream.set_message_handler("error",self.message_error,None,90)

    def find_conversation(self,user,thread):
        conv=None
        if user:
            key=user.bare().as_unicode()
        else:
            key=user
        if self.conversations.has_key(key):
            buffs=self.conversations[key]
            for b in buffs:
                if thread==b.thread:
                    conv=b
                    break
        return conv

    def find_or_make(self,user,thread):
        bset=self.settings["buffer"]
        if bset=="separate":
            pass
        elif bset=="per-thread":
            conv=self.find_conversation(user,thread)
            if conv:
                return conv
        elif bset=="per-user":
            conv=self.find_conversation(user,None)
            if conv:
                return conv
            thread=None
        else:
            conv=self.find_conversation(None,None)
            if conv:
                return conv
            thread=None
            user=None
        conv=Conversation(self,user,thread)
        if user:
            key=user.bare().as_unicode()
        else:
            key=user
        if not self.conversations.has_key(key):
            self.conversations[key]=[conv]
        else:
            self.conversations[key].append(conv)
        if self.settings.get("auto_popup"):
            cjc_globals.screen.display_buffer(conv.buffer)
        return conv

    def message_error(self,stanza):
        if self.settings["buffer"]=="separate":
            return 0
        fr=stanza.get_from()
        thread=stanza.get_thread()

        conv=self.find_conversation(fr,thread)
        bset=self.settings["buffer"]
        if not conv and bset in ("per-thread","per-user","single"):
            conv=self.find_conversation(fr,thread)
        if not conv and bset in ("per-user","single"):
            conv=self.find_conversation(fr,None)
        if not conv and bset=="single":
            conv=self.find_conversation(None,None)
        if not conv:
            return 0
        conv.error(stanza)
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
            timestamp=d.get_datetime_local()
        else:
            timestamp=None

        conv=self.find_or_make(fr,thread)
        self.cjc.send_event("message received",body)
        conv.add_received(fr,subject,body,thread,timestamp)

        archivers = self.cjc.plugins.get_services(Archiver)
        for archiver in archivers:
            archiver.log_event("message", fr, 'in', timestamp, subject, body, thread)

        return 1

ui.CommandTable("message",50,(
    ui.Command("message",Plugin.cmd_message,
        "/message [-subject subject] nick|jid [text]",
        "Compose or send message to given user",
        ("-subject opaque","user","text")),
    ui.CommandAlias("msg","message"),
    )).install()
# vi: sts=4 et sw=4
