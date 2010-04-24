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

"""Reimplementation of the old logging by the message, chat and muc plugins."""

from datetime import datetime
import logging
import os

from cjc.main import Application
from cjc.plugin import Archiver, Plugin, Configurable
from cjc import cjc_globals

logger = logging.getLogger("cjc.plugin.file_logger")

class FileLogger(Archiver, Plugin, Configurable):
    """Reimplementation of the old logging by the message, chat and muc
    plugins."""
    settings_namespace = "file_logger"
    available_settings = {
            "chat_filename":
                ("Where chat should be logged to", (str, None)),
            "chat_format_in":
                ("Format of incoming chat log entries", (str, None)),
            "chat_format_out":
                ("Format of outgoing chat log entries", (str, None)),
            "message_filename":
                ("Where messages should be logged to", (str, None)),
            "message_format_in":
                ("Format of incoming message log entries", (str, None)),
            "message_format_out":
                ("Format of outgoing message log entries", (str, None)),
            "muc_filename":
                ("Where muc should be logged to", (str, None)),
            "muc_format_in":
                ("Format of incoming muc log entries", (str, None)),
            "muc_format_out":
                ("Format of outgoing muc log entries", (str, None)),
            };
    settings = None
    def __init__(self):
        self.settings = {
                "chat_filename": None,
                "chat_format_in": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
                "chat_format_out": "[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n",
                "message_filename": None,
                "message_format_in": u"[%(T:now:%c)s] Incoming message\n"
                        "From: %(sender)s\n"
                        "Subject: %(subject)s\n%(body)s\n",
                "message_format_out": u"[%(T:now:%c)s] Outgoing message\n"
                        "To: %(recipient)s\n"
                        "Subject: %(subject)s\n%(body)s\n",
                }
    def unload(self):
        """Allow plugin unload/reload."""
        return True
    def _migrate_settings(self, plugin_name):
        """Migrate logging settings from the old chat and message plugins.
        
        :Return: the migrated log file name."""
        cjc = Application.instance
        old_key = plugin_name + ".log_filename"
        if old_key not in cjc.settings:
            logger.debug("{0} not in CJC settings, nothing to migrate".format(old_key))
            return None
        logger.warning("File logger plugin: migrating logging settings from the old"
                        " {0} plugin.".format(plugin_name))
        filename  = cjc.settings[old_key]
        self.settings[plugin_name + "_filename"] = filename
        del cjc.settings[old_key]
        for setting in ("format_in", "format_out"):
            old_key = "{0}.log_{1}".format(plugin_name, setting)
            if old_key in cjc.settings:
                self.settings["{0}_{1}".format(plugin_name, setting)] = cjc.settings[
                                                                                old_key]
                del cjc.settings[old_key]
        return filename

    def log_event(self, event_type, peer, direction = None, timestamp = None,
                    subject = None, body = None, thread = None, **kwargs):
        """Log an event. 
        
        Only 'chat', 'message' and 'muc' event are supported."""
        if event_type not in ('chat', 'message', 'muc'):
            return
        if direction not in ('in', 'out'):
            return
        if not any((subject, body)):
            return
        if timestamp is None:
            timestamp = datetime.now()
        filename = self.settings.get(event_type +"_filename")
        if not filename:
            filename = self._migrate_settings(event_type)
            if not filename:
                return
        format = self.settings["{0}_format_{1}".format(event_type, direction)]
        cjc = Application.instance
        params = {
            "sender": peer if direction == 'in' else cjc.jid,
            "recipient": cjc.jid if direction == 'in' else peer,
            "subject": subject,
            "body": body,
            "thread": thread,
            "peer": peer,
            }
        filename = cjc_globals.theme_manager.substitute(filename, params)
        filename = os.path.expanduser(filename.encode("utf-8"))
        entry = cjc_globals.theme_manager.substitute(format, params)
        try:
            dirname = os.path.dirname(filename)
            if dirname and not os.path.exists(dirname):
                os.makedirs(dirname)
            with open(filename, "a") as log:
                log.write(entry.encode("utf-8", "replace"))
        except (IOError, OSError),e:
            logger.error(u"Couldn't write chat log: {0!r}".format(e))

