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
import sys

indices=xrange(sys.maxint)
indices1=xrange(1,sys.maxint)

theme_attrs={}

theme_formats=(
    ("disco.info",u"[%(T:timestamp)s] Disco information for %(J:jid:full)s%(node? node: %(node)s)s %(cache_state?(%(cache_state)s))s\n%{disco_identities}%{disco_features}\n"),
    ("disco.identity",u"        %(category)s/%(type)s %(name)s\n"),
    ("disco.feature",u"        Feature: %(feature)s\n"),
    ("disco.items",u"[%(T:timestamp)s] Disco items for %(J:jid:full)s%(node? node: %(node)s)s %(cache_state?(%(cache_state)s))s\n%{disco_items}\n"),
    ("disco.item",u" %(index)6i. %(J:jid:full)s%(node? node: %(node)s)s%(name? '%(name)s')s\n"),
    ("disco.descr",u"Disco for %(J:jid:full)s%(node? node: %(node)s)s"),
)

class DiscoBuffer:
    def __init__(self,plugin,jid,node):
        self.plugin=plugin
        self.fparams={
                "jid": jid,
                "node": node,
                }
        self.items=None
        self.buffer=ui.TextBuffer(plugin.cjc.theme_manager, self.fparams,
                "disco.descr", "disco buffer", self)
        self.buffer.preference=plugin.settings["buffer_preference"]
        plugin.cjc.screen.display_buffer(self.buffer)

    def got_disco_items(self,address,items,state):
        format_string=self.plugin.cjc.theme_manager.format_string
        if state=='new':
            cache_state=None
        else:
            cache_state="cached"
        formatted_items=[]
        self.items=items.items()
        for i,item in zip(indices1,items.items()):
            params={'jid': item.jid(), 
                    'node': item.node(), 
                    'name': item.name(),
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
        self.buffer.update()

    def disco_items_error(self,address,data):
        self.buffer.append_themed("error",u"%r: %s" % (address,unicode(data)))
        self.buffer.update()

    def got_disco_info(self,address,info,state):
        format_string=self.plugin.cjc.theme_manager.format_string
        if state=='new':
            cache_state=None
        else:
            cache_state="cached"
        formatted_identities=[]
        for identity in info.identities():
            params={
                    'name': identity.name(),
                    'category': identity.category(),
                    'type': identity.type(),
                    }
            formatted_identities+=format_string("disco.identity",params)
        formatted_features=[]
        for feature in info.features():
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
        self.buffer.update()

    def disco_info_error(self,address,data):
        self.buffer.append_themed("error",u"%r: %s" % (address,unicode(data)))
        self.buffer.update()

    def cmd_close(self,args):
        if self.buffer:
            self.buffer.close()
        self.buffer=None


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
            jid=JID(self.cjc.stream.me.domain)
            node=None
        else:
            node=args.shift()
        args.finish()
        buffer=DiscoBuffer(self,jid,node)
        self.cjc.cache.request_object(disco.DiscoItems, (jid, node), "fresh",
                buffer.got_disco_items, buffer.disco_items_error)
        self.cjc.cache.request_object(disco.DiscoInfo, (jid, node), "fresh",
                buffer.got_disco_info, buffer.disco_info_error)
    
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
