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
import pyxmpp

from cjc import ui
from cjc.ui import cmdtable
from cjc import common

class UserCompletion(ui.Completion):
    def __init__(self,app):
        ui.Completion.__init__(self)
        self.app=app
        self.__logger=logging.getLogger("cjc.UserCompletion")
    def complete(self,word):
        self.__logger.debug("UserCompletion.complete(self,%r)" % (word,))
        matches=[]
        case_sensitive=self.app.settings["case_sensitive"]
        if case_sensitive:
            mword=word
        else:
            mword=word.lower()
        if self.app.roster:
            for ri in self.app.roster.items():
                name=ri.name
                if not case_sensitive and name:
                    name=name.lower()
                if mword==name:
                    items=self.app.roster.items_by_name(name,case_sensitive)
                    if len(items)>1:
                        for i in items:
                            matches.append(i.jid.as_unicode())
                        continue
                if name is None:
                    name=ri.jid.as_unicode()
                if (name.startswith(mword)
                        and name not in matches
                        and ri.jid.as_unicode() not in matches):
                    matches.append(name)
        for jid in self.app.user_info.keys():
            if self.app.roster:
                try:
                    name=self.app.roster.item_by_jid(jid).name
                    if name in matches:
                        continue
                except KeyError:
                    pass
            jid=jid.as_unicode()
            if jid.startswith(word) and jid not in matches:
                matches.append(jid)
        self.__logger.debug("roster completion matches for %r: %r" % (word,matches))
        matches=[[m,1] for m in matches]
        return self.make_result("",word,matches)

class SettingCompletion(ui.Completion):
    def __init__(self,app):
        self.app=app
        ui.Completion.__init__(self)
        self.__logger=logging.getLogger("cjc.SettingCompletion")
    def complete(self,word):
        self.__logger.debug("SettingCompletion.complete(self,%r)" % (word,))
        if "." in word:
            return self.complete_plugin(word)
        matches=[]
        for p in self.app.plugins.keys():
            if p.startswith(word):
                matches.append([p+".",0])
        for s in self.app.available_settings.keys():
            if s.startswith(word) and s not in matches:
                matches.append([s,1])
        self.__logger.debug("word=%r matches=%r" % (word,matches))
        return self.make_result("",word,matches)
    def complete_plugin(self,word):
        if word.startswith("."):
            obj=self.app
            head="."
            word=word[1:]
        else:
            d=word.find(".")
            plugin=word[0:d]
            if not self.app.plugins.has_key(plugin):
                return "",[]
            obj=self.app.plugins[plugin]
            head=plugin+"."
            word=word[d+1:]
        matches=[]
        for s in obj.available_settings.keys():
            if s.startswith(word) and s not in matches:
                matches.append([s,1])
        return self.make_result(head,word,matches)

class CommandCompletion(ui.Completion):
    def __init__(self,app):
        ui.Completion.__init__(self)
        self.app=app
        self.__logger=logging.getLogger("cjc.CommandCompletion")
    def complete(self,word):
        matches=[]
        for a in self.app.aliases.keys():
            if a.startswith(word):
                matches.append(a)
        for t in cmdtable.command_tables:
            if not t.active:
                continue
            for cmd in t.get_command_names():
                if cmd.startswith(word) and cmd not in matches:
                    matches.append(cmd)
        matches=[[m,1] for m in matches]
        return self.make_result("",word,matches)

# vi: sts=4 et sw=4
