# Console Jabber Client
# Copyright (C) 2004-2005  Jacek Konieczny
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

class PluginBase:
    def __init__(self,cjc,name):
        """
        Initialize the plugin.
        """
        self.settings={}
        self.available_settings={}
        self.cjc=cjc
        self.name=name
        self.module=None
        self.sys_path=None
        self.logger=logging.getLogger("cjc.plugin."+name)
        self.debug=self.logger.debug
        self.info=self.logger.info
        self.warning=self.logger.warning
        self.error=self.logger.error

    def unload(self):
        """
        Unregister every handler installed etc. and return True if the plugin
        may safely be unloaded.
        """
        return False

    def session_started(self,stream):
        """
        Stream-related plugin setup (stanza handler registration, etc).
        """
        pass

    def session_ended(self,stream):
        """
        Called when a session is closed (the stream has been disconnected).
        """
        pass

# vi: sts=4 et sw=4
