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
import re
import functools

from .ui import cmdtable

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

class UnloadablePlugin:
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
    CHRONOLOGICAL = 1
    REVERSE_CHRONOLOGICAL = 2
    @abstractmethod
    def get_records(self, event_type = None, peer = None,
            older_than = None, newer_than = None, limit = None,
            chronological = None, *kwargs):
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
            - `order`: `Archive.CHRONOLOGICAL` for chronological order (affects sorting
              and set returned by limit), `Archive.REVERSE_CHRONOLOGICAL` for
              reversed chronological order and `None` for no sorting.
        :Types:
            - `event_type`: `str`
            - `peer`: `pyxmpp.jid.JID`
            - `older_than`: `datetime.datetime` or opaque identifier
            - `newer_than`: `datetime.datetime` or opaque identifier
            - `limit`: `int`
            - `order`: `int`

        :Returns: archive entries matching the specified critetia.
        :Returntype: `collections.Iterable` of (archive_id, `ArchiveRecord`) 
            typles."""

def cli_command(func, completions = None):
    """Decorator for CLI commands methods."""
    func._cjc_command = True
    func._completions = completions
    return func

def cli_completion(*completions):
    """Decorator for CLI commands methods providing completion data."""
    return functools.partial(cli_command, completions = completions)

class CLI:
    """Base for classes implementing new CJC commands.
    
    Subclasses may return own command table by overriding the
    `get_command_table` method or implement the commands as methods
    decorated with @cli_command or @cli_command(completion,...).
    
    Names of the methods implementing CJC commands may be prefixed with
    'cmd_' to avoid conflicts, the prefix will be automatically stripped
    from the command name.

    The docstings of the methods will be converted to CJC help strings.
    Such docstring should consist of two parts separated with an empty line.
    First part will be the usage string (like '/do_something [argument]')
    and the other, the detailed description.
    
    Examples:
        >>> class MyCommands(CLI):
        ...     @cli_command
        ...     def cmd_do_something(self, args):
        ...         '''/do_something
        ...         
        ...         Do something interesting.'''
        ...         pass
        ...     @cli_completion("user", "text")
        ...     def cmd_tell(self, args):
        ...         '''/tell whom [what]
        ...
        ...         Tell something to somewhat'''
        ...         pass
        """
    __metaclass__ = ABCMeta
   
    @property
    def command_table_name(self):
        """Name of the command table implemented by this object."""
        return self.__class__.__name__.lower()

    @property
    def command_table_priority(self):
        """Priority of the command table implemented by this object."""
        return 60

    def get_command_table(self):
        """Return CLI command table.

        This implementation build the table from class methods
        decorated with @cli_command or @cli_completion."""
        commands = []
        for name, method in self.__class__.__dict__.items():
            if not hasattr(method, "_cjc_command"):
                continue
            if not method._cjc_command:
                continue
            if name.startswith("cmd_"):
                name = name[4:]
            if method.__doc__:
                doc = re.sub(r"[ \t]*\n[ \t]*", "\n", method.__doc__)
                if "\n\n" in doc:
                    usage, doc = [x.strip() for x in doc.split("\n\n", 1)]
                else:
                    usage = "/{0} [arg...]".format(name)
                    doc = doc.strip()
            else:
                usage = "/{0} [arg...]".format(name)
                doc = "*undocumented*"
            commands.append(
                    cmdtable.Command(name, method, usage, doc,
                                                    method._completions))
        return cmdtable.CommandTable(self.command_table_name,
                                    self.command_table_priority, commands)

def _event_handler_decorator(func, events):
    """Decorator function for event listener."""
    func._cjc_event_handler = True
    func._events = events
    return func

def event_handler(event, *events):
    """Returns decorator for event handler."""
    return functools.partial(_event_handler_decorator,
                                            events = [event] + list(events))

class EventListener:
    """Base for classes implementing event listeners.
    
    Subclasses may return own event listeners list by overriding the
    `get_event_handlers` method or implement the commands as methods
    decorated with @eventlistener(event, ...).
    """
    __metaclass__ = ABCMeta
    def get_event_handlers(self):
        """Return event listeners.

        This implementation build the table from class methods
        decorated with @event_handler(...)."""
        event_handlers = []
        for method in self.__class__.__dict__.values():
            if not hasattr(method, "_cjc_event_handler"):
                continue
            if not method._cjc_event_handler:
                continue
            # bind the method
            method = method.__get__(self, self.__class__)
            event_handlers.append((method._events, method))
        return event_handlers

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
