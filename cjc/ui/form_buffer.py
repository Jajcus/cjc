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
from types import StringType,IntType,UnicodeType

from cjc.ui.text_buffer import TextBuffer
from cjc import common
from cjc.ui import keytable

from pyxmpp.jabber.dataforms import Form

theme_attrs = ()
theme_formats = (
        ("form.head", u"%(title?%(title)s\n)s%(instructions?\n%(instructions)s\n)s\n"),
        ("form.fixed", u"\n%(value)s\n"),
        ("form.field_head", u"%(index)3i. %(label?%(label)s,%(name)s)s:\n"),
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
    initialized_theme_managers = {}
    def __init__(self, theme_manager, info, descr_format = "default_buffer_descr",
                command_table = None, command_table_object = None, length = 200):
        if id(theme_manager) not in self.initialized_theme_managers:
            theme_manager.set_default_attrs(theme_attrs)
            theme_manager.set_default_formats(theme_formats)
            self.initialized_theme_managers[id(theme_manager)] = True
        TextBuffer.__init__(self, theme_manager, info, descr_format, command_table,
                command_table_object, length)
        self.form = None
        self.callback = None
        self.indexes = {}

    def set_form(self, form, callback):
        self.form = form.copy()
        self.callback = callback
        self.indexes = {}
        self.main_menu()

    def main_menu(self):
        self.clear()
        num_indexes = self.print_form()
        self.ask_question("[O]k, [C]ancel, [E]dit, or edit field #...", "choice", "o",
                self.main_menu_choice, values = ("o", "c", "e", xrange(1, num_indexes+1)),
                required = True)
        self.update()

    def main_menu_choice(self, arg, response):
        if response == "o":
            form = self.form.make_submit()
            self.form = None
            self.callback(self, form)
            self.callback = None
        elif response == "c":
            self.form = None
            self.callback(self, Form("cancel"))
            self.callback = None
        else:
            self.main_menu()

    def print_form(self):
        field_index = 1
        self.append_themed("form.head", 
                {"title": self.form.title, "instructions": self.form.instructions})
        for field in self.form.fields:
            if self.print_field(field_index, field):
                field_index += 1
        return field_index - 1

    def print_field(self, field_index, field):
        if field.type == "hidden":
            return False
        if field.type == "fixed":
            self.append_themed("form.fixed", {"value": field.value})
            return False
        if not field.name:
            return False
        self.append_themed("form.field_head", {
                "index": field_index,
                "name": field.name, 
                "label": field.label,
                "type": field.type,
                })
        self.indexes[field_index] = field.name
        field_index += 1
        field_type = field.type
        if not field.values and field_type and not field_type.startsswith("list-"):
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
