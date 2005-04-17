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
import locale
import tempfile
import os
from types import StringType,IntType,UnicodeType

from cjc.ui.text_buffer import TextBuffer
from cjc import common
from cjc.ui import keytable

from pyxmpp.jabber.dataforms import Form

theme_attrs = ()
theme_formats = (
        ("form.head", u"%(title?%(title)s\n)s%(instructions?\n%(instructions)s\n)s\n"),
        ("form.fixed", u"\n%(value)s\n"),
        ("form.field_head", u"%(index)3i. %(label?%(label)s,%(name)s)s%(required? *)s:\n"),
        ("form.no_value", u"     No value\n"),
        ("form.boolean_true", u"     Value: True\n"),
        ("form.boolean_false", u"     Value: False\n"),
        ("form.jid-multi_head", u"     Values:\n"),
        ("form.jid-multi_value", u"       %(J:jid)s\n"),
        ("form.jid-single", u"     Value: %(J:jid)s\n"),
        ("form.list-multi_head", u"     Options (* - selected):\n"),
        ("form.list-multi_option_head", u"     %(selected?*, )s %(label)s\n"),
        ("form.list-multi_option_value", u""),
        ("form.list-single_head", u"     Options (* - selected):\n"),
        ("form.list-single_option_head", u"     %(selected?*, )s %(label)s\n"),
        ("form.list-single_option_value", u""),
        ("form.text-multi_head", u"     Value:\n"),
        ("form.text-multi_value", u"     %(value)s\n"),
        ("form.text-private", u"     Value: %(asterisks)s\n"),
        ("form.text-single", u"     Value: %(value)s\n"),
)

class FormBuffer(TextBuffer):
    editor_encoding = None
    editor = None
    initialized_theme_managers = {}
    def __init__(self, theme_manager, info, descr_format = "default_buffer_descr",
                command_table = None, command_table_object = None, length = 200):
        if id(theme_manager) not in self.initialized_theme_managers:
            theme_manager.set_default_attrs(theme_attrs)
            theme_manager.set_default_formats(theme_formats)
            self.initialized_theme_managers[id(theme_manager)] = True
        self.__logger=logging.getLogger("cjc.ui.FormBuffer")
        TextBuffer.__init__(self, theme_manager, info, descr_format, command_table,
                command_table_object, length)
        self.form = None
        self.callback = None
        self.editable_fields = None
        self.indexes = {}

    def set_form(self, form, callback):
        self.form = form.copy()
        self.callback = callback
        self.main_menu()

    def main_menu(self):
        self.clear()
        self.print_form()
        required_missing = False
        for field in self.form:
            if field.required and not field.values:
                required_missing = True
                break
        if required_missing:
            self.ask_question("[C]ancel, [E]dit, or edit field #...", "choice", None,
                    self.main_menu_choice, values = ("c", "e", xrange(1, len(self.editable_fields)+1)),
                    required = True)
        else:
            self.ask_question("[O]k, [C]ancel, [E]dit, or edit field #...", "choice", "o",
                    self.main_menu_choice, values = ("o", "c", "e", xrange(1, len(self.editable_fields)+1)),
                    required = True)
        self.pos = (0,0)
        self.update_pos()
        self.update()

    def main_menu_choice(self, response):
        if response == "o":
            form = self.form.make_submit()
            self.form = None
            self.callback(self, form)
            self.callback = None
        elif response == "c":
            self.form = None
            self.callback(self, Form("cancel"))
            self.callback = None
        elif response == "e":
            self.clear()
            self.edit_next_field(iter(self.editable_fields))
        elif response in xrange(1, len(self.editable_fields)+1):
            self.clear()
            self.edit_field(self.editable_fields[response - 1], self.main_menu)
        else:
            self.main_menu()

    def edit_next_field(self, fields_iter):
        try:
            field = fields_iter.next()
        except StopIteration:
            return self.main_menu()
        old_content = [list(l) for l in self.lines]
        def post_edit_callback():
            self.lines[:] = old_content 
            self.pos = None
            self.update_pos()
            self.redraw()
            self.print_field(field)
            return self.edit_next_field(fields_iter)
        self.edit_field(field, post_edit_callback)

    def edit_field(self, field, post_edit_callback):
        self.print_field(field)
        if field.label:
            prompt = field.label+" > "
        else:
            prompt = field.name+" > "
        def ask_question(input_type, value, handler, values = None):
            def callback(response):
                return handler(response, field, post_edit_callback)
            def abort_callback():
                return self.edit_field(field, post_edit_callback)
            self.ask_question(prompt, input_type, value, callback, abort_callback,
                    required = field.required, values = values)
        def ask_edit_question(value, handler):
            def callback(response):
                return handler(response, field, post_edit_callback)
            def abort_callback():
                return self.edit_field(field, post_edit_callback)
            def edit_callback(response):
                if response=="e":
                    return self.external_edit(value, callback, abort_callback)
                else:
                    return post_edit_callback()
            self.ask_question("[E]dit or [A]ccept? ", "choice", "a", edit_callback, abort_callback, required = True, values = "ae")
        if field.type == "boolean":
            ask_question("boolean", field.value, self.boolean_field_modified)
        elif field.type == "jid-multi":
            ask_edit_question([unicode(jid) for jid in field.value], self.jid_multi_field_modified)
        elif field.type == "jid-single":
            if field.value is None:
                value = u""
            else:
                value = field.value.as_unicode()
            ask_question("text-single", field.value, self.jid_single_field_modified)
        elif field.type in ("list-multi", "list-single"):
            labels = []
            default = None
            for option in field.options:
                if option.label:
                    label = option.label
                else:
                    label = u",".join(option.values)
                labels.append(label)
                if option.values == field.values:
                    default = label
            ask_question(field.type, default, self.list_multi_field_modified, labels)
        elif field.type == "text-multi":
            ask_edit_question(field.value, self.text_multi_field_modified)
        else:
            if field.value is None:
                value = u""
            else:
                value = field.value
            ask_question("text-single", value, self.text_single_field_modified)
        self.update()
                    
                    
    def external_edit(self, value, callback, error_callback):
        editor_encoding=self.editor_encoding
        if not editor_encoding:
            editor_encoding=locale.getlocale()[1]
        if not editor_encoding:
            editor_encoding="utf-8"
        try:
            text = u"\n".join(value).encode(editor_encoding, "strict")
        except UnicodeError:
            self.append_themed("error", u"Cannot encode message or address to the editor encoding.")
            return error_callback()
        try:
            (tmpfd, self.tmpfile_name) = tempfile.mkstemp(prefix = "cjc-", suffix = ".txt")
        except (IOError, OSError),e:
            self.append_themed("error", u"Cannot create a temporary file: %s" % (e,))
            return error_callback()
        try:
            tmpfile = os.fdopen(tmpfd,"w+b")
            tmpfile.write(text)
            tmpfile.close()
        except (IOError,OSError),e:
            self.append_themed("error", u"Cannot write the temporary file %r (fd: %i): %s"
                    % (self.tmpfile_name, tmpfd,e))
            return error_callback()
        editor = self.editor
        if not editor:
            editor = os.environ.get("EDITOR", "vi")
        command="%s %s" % (editor, self.tmpfile_name)
        ok=True
        try:
            self.window.screen.shell_mode()
            try:
                ret=os.system(command)
            finally:
                self.window.screen.prog_mode()
        except (OSError,),e:
            self.append_themed(u"Couldn't start the editor: %s" % (e,))
            ok=False
        if ret:
            es=os.WEXITSTATUS(ret)
            if not os.WIFEXITED(ret):
                self.error(u"Editor exited abnormally")
            elif es:
                self.warning(u"Editor exited with status %i" % (es,))
            ok=False
        if not ok:
            return error_callback()
        try:
            tmpfile = open(self.tmpfile_name, "r")
            try:
                text = tmpfile.read()
            finally:
                try:
                    tmpfile.close()
                except IOError:
                    pass
        except IOError:
            self.append_themed("error", u"Error reading the edited message!")
            return error_callback()

        try:
            value = [unicode(l, editor_encoding, "strict") for l in text.split("\n")]
        except UnicodeError:
            self.append_themed("error", u"Cannot encode message or address to the editor encoding.")
            return error_callback()
        if len(value) and value[-1] == u"":
                value = value[:-1]
        return callback(value)

    def boolean_field_modified(self, response, field, post_edit_callback):
        if response is None and field.required:
            self.edit_field(field, post_edit_callback)
            return
        field.value = response
        post_edit_callback()

    def text_single_field_modified(self, response, field, post_edit_callback):
        if not response and field.required:
            self.edit_field(field, post_edit_callback)
            return
        field.value = response
        post_edit_callback()

    def text_multi_field_modified(self, response, field, post_edit_callback):
        if not response and field.required:
            self.edit_field(field, post_edit_callback)
            return
        field.value = response
        post_edit_callback()

    def jid_multi_field_modified(self, response, field, post_edit_callback):
        if not response and field.required:
            self.edit_field(field, post_edit_callback)
            return
        try:
            field.value = [JID(v) for v in response if v]
        except (ValueError,TypeError):
            self.edit_field(field, post_edit_callback)
            return
        post_edit_callback()

    def list_single_field_modified(self, response, field, post_edit_callback):
        if not response and field.required:
            self.edit_field(field, post_edit_callback)
            return
        field.value = response
        post_edit_callback()

    def list_multi_field_modified(self, response, field, post_edit_callback):
        if not response and field.required:
            self.edit_field(field, post_edit_callback)
            return
        field.value = response
        post_edit_callback()


    def jid_single_field_modified(self, response, field, post_edit_callback):
        if not response and field.required:
            self.edit_field(field, post_edit_callback)
            return
        if not response:
            field.value = None
        else:
            try:
                field.value = JID(response)
            except ValueError:
                self.edit_field(field, post_edit_callback)
                return
        post_edit_callback()

    def print_form(self):
        self.indexes = {}
        self.editable_fields = []
        self.append_themed("form.head", 
                {"title": self.form.title, "instructions": self.form.instructions})
        for field in self.form:
            field_index = len(self.editable_fields)
            if self.print_field(field, field_index):
                self.editable_fields.append(field)
                self.indexes[field.name] = field_index

    def print_field(self, field, field_index = None):
        if field.type == "hidden":
            return False
        if field.type == "fixed":
            self.append_themed("form.fixed", {"value": field.value})
            return False
        if not field.name:
            return False
        if field_index is None:
            field_index = self.indexes[field.name]
        self.append_themed("form.field_head", {
                "index": field_index + 1,
                "name": field.name, 
                "label": field.label,
                "type": field.type,
                "required": field.required,
                })
        field_type = field.type
        if not field.values and field_type and not field_type.startswith("list-"):
            self.append_themed("form.no_value", {})
        elif field_type == "bolean":
            if field.value:
                self.append_themed("form.boolean_true", {})
            else:
                self.append_themed("form.boolean_false", {})
        elif field_type == "jid-multi":
            self.append_themed("form.jid-multi_head", {})
            for jid in field.value:
                self.append_themed("form.jid-multi_value", {"jid": jid})
        elif field_type == "jid-single":
            self.append_themed("form.jid-single", {"jid": field.value})
        elif field_type in ("list-multi", "list-single"):
            self.append_themed("form.%s_head" % (field_type,), {})
            found = []
            for option in field.options:
                selected = True
                for v in option.values:
                    if v not in field.values:
                        selected = False
                        break
                self.append_themed("form.%s_option_head" % (field_type,),
                        {"label": option.label, "selected": selected})
                for value in option.values:
                    if value in field.values:
                        selected = True
                    else:
                        selected = False
                    self.append_themed("form.%s_option_value" % (field_type,), 
                            {"label": option.label, "value": value, "selected": selected})
        elif field_type == "text-multi":
            self.append_themed("form.text-multi_head", {})
            for value in field.value:
                self.append_themed("form.text-multi_value", {"value": value})
        elif field_type == "text-private":
            value = field.value
            if value is not None:
                asterisks = "*" * len(value)
            self.append_themed("form.text-private", {"value": value, "asterisks": asterisks})
        else:
            self.append_themed("form.text-single", {"value": field.value})
        return True
       

# vi: sts=4 et sw=4
