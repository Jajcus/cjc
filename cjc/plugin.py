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

import logging

from collections import Mapping
from abc import ABCMeta, abstractmethod, abstractproperty

class Plugin:
    """Subclasses of `Plugin` will be instantiated when loading modules from
    CJC plugin directories."""
    __metaclass__ = ABCMeta
    @property
    def services(self):
        """Collection of services provided by this plugin."""
        return [self]
    @abstractmethod
    def unload(self):
        """Unload the plugin if possible.

        :Return: `True` on success, `False` if unload is not possible."""
        pass

class NamedService:
    """Service registered with a name.

    All services may be looked up in the plugin registry using a base class name. When 
    a service is a subclass of `NamedService` it can also be looked up by class
    and name."""
    __metaclass__ = ABCMeta
    @abstractproperty
    def service_name(self):
        """:Return: service name"""

class Configurable:
    """Configurable is a object with own settings."""
    __metaclass__ = ABCMeta
    @abstractproperty
    def available_settings(self):
        """A `Mapping` providing description of available settings."""
        pass
    @abstractproperty
    def settings(self):
        """A `Mapping` providing current values of available settings.  This
        property should provide defaults when the class is instantiated."""
        pass
    @abstractproperty
    def settings_namespace(self):
        """Settings namespace string - the part used before '.' in the setting
        name."""
        pass

class Archiver:
    """Generic message/chat_event logging service."""
    __metaclass__ = ABCMeta
    @abstractmethod
    def log_event(self, event_type, peer, direction = None, timestamp = None,
                        subject = None, body = None, thread = None,
                        **kwargs):
        """Write an event record to a log or archive.

        :Parameters:
            - `event_type`: predefined possible values are: 'message', 'chat'
              and 'muc'
            - `peer`: full JID of the conversation peer or event source
            - `direction`: 'in' for incoming messages, 'out' for outgoing
            - `timestamp`: event timestamp
            - `subject`: messages subject
            - `body`: message body
            - `thread`: message thread
            - `kwargs`: extra keyword parameters for future use
        :Types:
            - `event_type`: `str`
            - `peer`: `pyxmpp.jid.JID`
            - `direction`: `str`
            - `timestamp`: `datetime.datetime`
            - `subject`: `unicode`
            - `body`: `unicode`
            - `thread`: `unicode`
        """
        pass

class ArchiveRecord:
    """Message archive record."""
    __metaclass__ = ABCMeta
    @abstractproperty
    def event_type(self):
        "Event type"
        pass
    @abstractproperty
    def peer(self):
        "Conversation peer"
        pass
    @abstractproperty
    def direction(self):
        "'in', 'out' or None"
        pass
    @abstractproperty
    def timestamp(self):
        "Event timestamp"
        pass
    @abstractproperty
    def subject(self):
        "Message subject"
        pass
    @abstractproperty
    def body(self):
        "Message body"
        pass
    @abstractproperty
    def thread(self):
        "Message thread"
        pass

class Archive:
    """Archive access and manipulation service."""
    __metaclass__ = ABCMeta
    @abstractmethod
    def get_records(self, event_type = None, peer = None,
            older_than = None, newer_than = None, limit = None,
                                                        *kwargs):
        """Get records from archive.

        :Parameters:
            - `event_type`: predefined possible values are: 'message', 'chat'
              and 'muc'
            - `peer`: conversation peer
            - `older_than`: return records older than this timestamp or archive
              id
            - `newer_than`: return recorse newer than this timestamp or archive
              id
            - `limit`: return up to that many most recent entries matching the
              query
            - `kwargs`: more archive record properties may be specified 
              as extra keyword arguments to limit the query, thogh it may
              be not supported by the archive service.
        :Types:
            - `event_type`: `str`
            - `peer`: `pyxmpp.jid.JID`
            - `older_than`: `datetime.datetime` or opaque identifier
            - `newer_than`: `datetime.datetime` or opaque identifier
            - `limit`: `int`

        :Returns: archive entries matching the specified critetia.
        :Returntype: `collections.Iterable` of (archive_id, `ArchiveRecord`) 
            typles."""

class PluginBase(Plugin, Configurable):
    """'Old-style' plugin base class"""
    settings = None
    available_settings = None
    def __init__(self, cjc, name):
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
    @property
    def services(self):
        return [self]
    @property
    def settings_namespace(self):
        return self.name

# vi: sts=4 et sw=4
