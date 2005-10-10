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

import libxml2

import pyxmpp
from cjc import ui
from cjc.plugin import PluginBase
from cjc import common
from pyxmpp.jabber import delay

theme_formats=(
    ("jogger.composer_descr","Jogger message"),
)

class Composer(ui.TextBuffer):
    message_template=u"""Subject: %(subject)s
Level: %(level)s

%(body)s
"""
    hdr_nocont_re=re.compile("\r?\n(?![ \t])")
    def __init__(self,plugin,recipient):
        self.buffer=ui.TextBuffer(plugin.cjc.theme_manager,{},
                "jogger.composer_descr")
        self.plugin=plugin
        self.recipient=recipient
        self.tmpfile_name=None
        self.subject=None
        self.level=None
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

    def fill_template(self,subject,level,body):
        if not subject:
            subject=u""
        else:
            subject=self.hdr_nocont_re.sub(u"\t\n",subject)
        if level is None or level=="default":
            level="default"
        else:
            level=int(level)
        if not body:
            body=u""
        template=self.message_template % {
                "subject":subject,
                "level":level,
                "body":body}
        return template

    def start(self,subject,level,body):
        template=self.fill_template(subject,level,body)
        editor_encoding=self.plugin.settings.get("editor_encoding")
        if not editor_encoding:
            editor_encoding=locale.getlocale()[1]
        if not editor_encoding:
            editor_encoding="utf-8"
        self.editor_encoding=editor_encoding
        try:
            template=template.encode(editor_encoding,"strict")
        except UnicodeError:
            self.plugin.error("Cannot encode message to the editor encoding.")
            return False

        try:
            (tmpfd,self.tmpfile_name)=tempfile.mkstemp(
                    prefix="cjc-",suffix=".txt")
        except (IOError,OSError),e:
            self.plugin.error("Cannot create a temporary file: %s" % (e,))
            return False
        try:
            tmpfile=os.fdopen(tmpfd,"w+b")
            tmpfile.write(template)
            tmpfile.close()
        except (IOError,OSError),e:
            self.plugin.error("Cannot write the temporary file %r (fd: %i): %s"
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
                self.error("Editor exited abnormally")
            elif es:
                self.warning("Editor exited with status %i" % (es,))
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
            self.plugin.error("Error reading the edited message!")
            return

        msg = msg.decode(self.editor_encoding)

        self.buffer.append(msg)
        subject=None
        subject_char=0
        level=None
        if u"\n\n" in msg:
            ok=True
            header,body=msg.split(u"\n\n",1)
            body_line=len(header.split("\n"))+1
            line=0
            headers=self.hdr_nocont_re.split(header)
            for h in headers:
                if ":" not in h:
                    self.error(u"Bad header: %r" % (h,))
                    ok=False
                    break
                name,value=h.split(":",1)
                value_char=len(name)+1
                name=name.strip().lower()
                if name==u"subject":
                    if subject:
                        self.error(u"More than one subject!")
                        ok=False
                        break
                    subject=value
                    subject_line=line
                    subject_char=value_char
                if name==u"level":
                    if level is not None:
                        self.error(u"More than one level!")
                        ok=False
                        break
                    value=value.strip()
                    if value!="default":
                        try:
                            level=int(value)
                        except ValueError:
                            self.error(u"Bad level: %r!" % (level,))
                            ok=False
                            break
                line+=len(h.split("\n"))
        else:
            self.error("Could not find header or body in the message")
            ok=False

        self.buffer.append_themed("info","Validating message, please wait...")
        self.buffer.update()

        if self.plugin.settings.get("dtd"):
            if ok and subject:
                container=self.plugin.settings.get("subject_container")
                ok=self.validate(subject,container,subject_line,subject_char)

            if ok and body:
                container=self.plugin.settings.get("body_container")
                ok=self.validate(body,container,body_line)

        if not ok:
            self.buffer.ask_question(u"Errors found. [E]dit again or [C]ancel?",
                    "choice",None,self.send_edit_cancel,values=("ec"))
            return True

        self.buffer.clear()
        msg=self.fill_template(subject,level,body)
        self.buffer.append(msg)
        self.buffer.update()
        self.subject=subject
        self.level=level
        self.body=body
        self.buffer.ask_question(u"[S]end, [E]dit or [C]ancel?",
                "choice",None,self.send_edit_cancel,values=("sec"))
        return True

    def send_edit_cancel(self, choice):
        if choice in "sS":
            if self.level in (None,"default"):
                body=self.body
            else:
                body=u"<level%i>%s" % (self.level,self.body)
            self.plugin.send_message(recipient=self.recipient,
                    subject=self.subject,body=body)
            self.buffer.close()
            self.buffer=None
        elif choice in "eE":
            self.edit_message()
        else:
            self.buffer.close()
            self.buffer=None

    def validate(self,xml,container,line_offset=0,char_offset=0):
        dtd=self.plugin.settings["dtd"]
        xml=(u"<!DOCTYPE %s %s>\n<%s>\n%s\n</%s>"
                % (container,dtd,container,xml,container))
        xml=xml.encode("utf-8")
        self.plugin.debug("validating %r",xml)
        self.xml=xml
        self.xml_line_offset=line_offset;
        self.xml_char_offset=char_offset;
        self.xml_line_char_offsets=[]
        self.xml_errors=0
        self.parser=libxml2.createDocParserCtxt(xml)
        self.parser.lineNumbers(1)
        self.parser.validate(1)
        self.parser.setErrorHandler(self.xml_error,None)
        if " HTML " in dtd:
            self.parser.htmlParseDocument()
        else:
            self.parser.parseDocument()
        ok=self.parser.isValid() and self.xml_errors==0
        self.parser=None
        self.plugin.debug("validation result: %r",ok)
        return ok

    def xml_error(self,arg,msg,severity,reserved):
        self.xml_errors+=1
        # libxml2 parser doesn't provide us with line number
        # where error occured, so we do some magic to compute it
        b=self.parser.byteConsumed()
        if not self.xml_line_char_offsets:
            lines=self.xml.split("\n")
            off=0
            for l in lines:
                self.xml_line_char_offsets.append(off)
                off+=len(l)+1
        line=0
        line_char_offset=0
        for lco in self.xml_line_char_offsets:
            if lco>b:
                break
            line+=1
            line_char_offset=lco
        char=b-line_char_offset
        if line==3:
            char+=self.xml_char_offset
        line+=self.xml_line_offset-2;
        msg=unicode(msg,"utf-8").strip()
        self.error(u"line %i,character %i: %s" % (line,char,msg))

    def error(self,msg):
        self.buffer.append_themed("error",msg)
        self.buffer.update()

    def warning(self,msg):
        self.buffer.append_themed("warning",msg)
        self.buffer.update()

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        self.buffers={}
        self.last_thread=0
        app.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "editor": ("Editor for message composition."
                    " Default: $EDITOR or 'vi'",str),
            "editor_encoding": ("Character encoding for edited messages."
                    " Default: locale specific",str),
            "jid": ("Where to send jogger messages. Default (and recommended):"
                    " autodetect",(pyxmpp.JID,None)),
            "dtd": ("HTML or XML DTD identifier for jogger entries."
                    " Should match your jogger template."
                    " If not set no validation is done (not recommended).",str),
            "subject_container": ("Container element for the entry subject."
                    " Should match your jogger template.",str),
            "body_container": ("Container element for the entry subject."
                    " Should match your jogger template.",str),
            }
        self.settings={
                "dtd": u' PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"'
                        ' "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"',
                "subject_container": "div",
                "body_container": "div",
                }
        ui.activate_cmdtable("jogger_pl",self)
        libxml2.initializeCatalog()

    def cmd_jogger_pl(self,args):
        subject=args.all()

        if not self.cjc.stream:
            self.error("Connect first!")
            return
        recipient=self.settings.get("jid")
        if not recipient:
            if not self.cjc.roster:
                self.error("Roster is not available yet")
                return
            for item in self.cjc.roster.get_items():
                if item.jid.domain=="jogger.pl":
                    recipient=item.jid
                    break
            if not recipient:
                self.error("No Jogger.pl contact in your roster."
                        "You should add one (e.g. 'blog@jogger.pl')"
                        " and subscribe to it's presence to activate your"
                        " blog.")
                return
        self.compose_message(recipient,subject)

    def compose_message(self,recipient=None,subject=None,level=None,body=None):
        composer=Composer(self,recipient)
        return composer.start(subject,level,body)

    def send_message(self,recipient,subject,body):
        m=pyxmpp.Message(to_jid=recipient,stanza_type="normal",subject=subject,body=body)
        self.cjc.stream.send(m)
        self.info("Your entry has been sent to Jogger.PL")

ui.CommandTable("jogger_pl",50,(
    ui.Command("jogger_pl",Plugin.cmd_jogger_pl,
        "/jogger_pl subject",
        "Compose an antry to your Jogger.pl blog",
        ("text")),
    )).install()

# vi: sts=4 et sw=4
