# Console Jabber Client
# Copyright (C) 2005  Jacek Konieczny
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

import curses

from cjc.plugin import PluginBase
from cjc import ui
from pyxmpp import JID
from pyxmpp.jabber import disco
from pyxmpp.error import ErrorNode
import sys

indices=xrange(sys.maxint)
indices1=xrange(1,sys.maxint)

theme_attrs={}

theme_formats=(
    ("disco.info",u"[%(T:timestamp)s] Disco information for %(J:jid:full)s%(node? node\\: %(node)s)s %(cache_state?(%(cache_state)s))s\n%{disco_identities}%{disco_features}\n"),
    ("disco.identity",u"        %(category)s/%(type)s %(name)s\n"),
    ("disco.feature",u"        Feature: %(feature)s\n"),
    ("disco.items",u"[%(T:timestamp)s] Disco items for %(J:jid:full)s%(node? node\\: %(node)s)s %(cache_state?(%(cache_state)s))s\n%{disco_items}\n"),
    ("disco.item",u" %(index)6i. %(J:jid:full)s%(node? node\\: %(node)s)s%(name? '%(name)s')s\n"),
    ("disco.descr",u"Disco for %(J:jid:full)s%(node? node\\: %(node)s)s"),
)

class DiscoBuffer:
    def __init__(self,plugin,jid,node):
        self.plugin=plugin
        self.fparams={
                "jid": jid,
                "node": node,
                }
        self.jid = jid
        self.node = node
        self.items = None
        self.history = []
        self.buffer=ui.TextBuffer(plugin.cjc.theme_manager, self.fparams,
                "disco.descr", "disco buffer", self)
        self.buffer.preference=plugin.settings["buffer_preference"]
        plugin.cjc.screen.display_buffer(self.buffer)

    def start_disco(self,state="fresh"):
        self.items = None
        try:
            self.plugin.cjc.cache.request_object(disco.DiscoInfo, (self.jid, self.node), state,
                    self.got_disco_info, self.disco_info_error)
            self.plugin.cjc.cache.request_object(disco.DiscoItems, (self.jid, self.node), state,
                    self.got_disco_items, self.disco_items_error)
        except TypeError:
            if self.buffer:
                self.buffer.append_themed("error",
                        "No disco available for '%s','%s'. Maybe you should connect first?"
                        % (self.jid, self.node))
                self.ask_question()
                self.buffer.update()

    def got_disco_items(self,address,items,state):
        if address != (self.jid, self.node) or not self.buffer:
            pass
        self.buffer.unask_question()
        format_string=self.plugin.cjc.theme_manager.format_string
        if state=='new':
            cache_state=None
        else:
            cache_state="cached"
        formatted_items=[]
        self.items=items.items
        for i,item in zip(indices1,items.items):
            params={'jid': item.jid, 
                    'node': item.node, 
                    'name': item.name,
                    'index': i
                    }
            formatted_items+=format_string("disco.item",params)
        params={
                "jid": address[0], 
                "node": address[1], 
                "disco_items": formatted_items,
                "cache_state": cache_state,
                }
        self.buffer.append_themed("disco.items",params)
        self.ask_question()
        self.buffer.update()

    def disco_items_error(self,address,data):
        if address != (self.jid, self.node) or not self.buffer:
            pass
        if not data:
            message="Timeout"
        elif isinstance(data,ErrorNode):
            message=data.get_message()
        else:
            try:
                message=unicode(data)
            except:
                message=str(data)
        jid, node = address
        if node:
            node=u", node: '%s'" % (node,)
        else:
            node=u""
        self.buffer.append_themed("error",
                u"Error while discovering items on '%s'%s: %s" 
                % (jid, node, message))
        self.ask_question()
        self.buffer.update()

    def got_disco_info(self,address,info,state):
        if address != (self.jid, self.node) or not self.buffer:
            pass
        self.buffer.unask_question()
        format_string=self.plugin.cjc.theme_manager.format_string
        if state=='new':
            cache_state=None
        else:
            cache_state="cached"
        formatted_identities=[]
        for identity in info.identities:
            params={
                    'name': identity.name,
                    'category': identity.category,
                    'type': identity.type,
                    }
            formatted_identities+=format_string("disco.identity",params)
        formatted_features=[]
        for feature in info.features:
            params={'feature': feature, }
            formatted_features+=format_string("disco.feature",params)

        params={
                "jid": address[0], 
                "node": address[1], 
                "disco_identities": formatted_identities,
                "disco_features": formatted_features,
                "cache_state": cache_state,
                }
        self.buffer.append_themed("disco.info",params)
        self.ask_question()
        self.buffer.update()

    def disco_info_error(self,address,data):
        if address != (self.jid, self.node) or not self.buffer:
            pass
        if not data:
            message=u"Timeout"
        elif isinstance(data,ErrorNode):
            message=data.get_message()
        else:
            try:
                message=unicode(data)
            except:
                message=str(data)
        jid, node = address
        if node:
            node=u", node: '%s'" % (node,)
        else:
            node=u""
        self.buffer.append_themed("error",
                u"Error while discovering information about '%s'%s: %s" 
                % (jid,node,message))
        self.ask_question()
        self.buffer.update()

    def cmd_close(self,args):
        if self.buffer:
            self.buffer.close()
        self.buffer=None

    def ask_question(self):
        if self.items: 
            max_num = len(self.items)+1
            if self.history:
                self.buffer.ask_question("Item to discover, [R]efresh, [B]ack or [C]lose",
                        "choice", None, self.response, values=[xrange(1,max_num),"r","b","c"], 
                        required=1)
            else:
                self.buffer.ask_question("Item to discover, [R]efresh or [C]lose",
                        "choice", None, self.response, values=[xrange(1,max_num),"r","c"], 
                        required=1)
        else:
            if self.history:
                self.buffer.ask_question("[R]efresh, [B]ack or [C]lose",
                        "choice", None, self.response, values=["r","b","c"], required=1)
            else:
                self.buffer.ask_question("[R]efresh or [C]lose",
                        "choice", None, self.response, values=["r","c"], required=1)

    def response(self, response):
        if response == "c":
            self.cmd_close(None)
        elif response == "r":
            self.buffer.clear()
            self.start_disco("new")
        else:
            if response == "b":
                self.jid, self.node = self.history.pop()
            else:
                self.history.append((self.jid,self.node))
                item = self.items[response-1]
                self.jid = item.jid
                self.node = item.node
            self.fparams['jid'] = self.jid
            self.fparams['node'] = self.node
            self.buffer.clear()
            self.buffer.update_info(self.fparams)
            self.start_disco()
            self.buffer.update()

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        ui.activate_cmdtable("disco",self)
        app.theme_manager.set_default_attrs(theme_attrs)
        app.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "buffer_preference": ("Preference of disco buffers when switching to the next active buffer. If 0 then the buffer is not even shown in active buffer list.",int),
            }
        self.settings={"buffer_preference":2}

    def cmd_disco(self,args):
        jid=args.shift()
        if not jid:
            if self.cjc.stream:
                jid=JID(self.cjc.stream.me.domain)
            else:
                jid=self.cjc.settings['jid']
            node=None
        else:
            node=args.shift()
        args.finish()
        buffer=DiscoBuffer(self,jid,node)
        buffer.start_disco()
    
    def unload(self):
        ui.uninstall_cmdtable("disco buffer")
        ui.uninstall_cmdtable("disco")
        return True

ui.CommandTable("disco buffer",51,(
    ui.Command("close",DiscoBuffer.cmd_close,
        "/close",
        "Closes current disco buffer"),
    )).install()

ui.CommandTable("disco",51,(
    ui.Command("disco",Plugin.cmd_disco,
        "/disco",
        "Do the Services Discovery on the selected JID and node (own server by default)"),
    )).install()

# vi: sts=4 et sw=4
