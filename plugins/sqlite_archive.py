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
import sqlite3
import collections
import threading

from pyxmpp.jid import JID

from cjc.main import Application
from cjc.plugin import Archiver, Archive, ArchiveRecord, Plugin, Configurable

logger = logging.getLogger("cjc.plugin.sqlite_archive")

SqliteArchiveRecord = collections.namedtuple("SqliteArchiveRecord",
        "event_type peer direction timestamp subject body thread")
ArchiveRecord.register(SqliteArchiveRecord)

SCHEMA = ["""
CREATE TABLE archive (
    record_id       INTEGER PRIMARY KEY,
    event_type      TEXT,
    peer            TEXT,
    peer_resource   TEXT,
    direction       TEXT,
    timestamp       TEXT,
    subject         TEXT,
    body            TEXT,
    thread          TEXT
    );""",
    "CREATE INDEX archive_peer_i ON archive(peer);",
    "CREATE INDEX archive_timestamp_i ON archive(timestamp);",
    ]

class SqliteArchive(Plugin, Archiver, Archive, Configurable):
    """Reimplementation of the old logging by the message, chat and muc
    plugins."""
    settings_namespace = "sqlite_archive"
    available_settings = {
            "filename": ("Archive database filename", (str, None)),
            };
    settings = None
    def __init__(self):
        self.settings = {
                "filename": "~/.cjc/archive.db",
                }
        self._local = threading.local()

    @property
    def _database(self):
        if hasattr(self._local, 'database'):
            return self._local.database
        else:
            return None
    @_database.setter
    def _database(self, value):
        self._local.database = value

    def unload(self):
        """Allow plugin unload/reload."""
        return True

    def _open_database(self):
        filename = self.settings.get("filename")
        if not filename:
            return None
        filename = os.path.expanduser(filename)
        if os.path.exists(filename):
            new = False
        else:
            new = True
        try:
            self._database = sqlite3.connect(filename,
                                    detect_types = sqlite3.PARSE_COLNAMES)
            self._database.row_factory = sqlite3.Row
            if not new:
                return self._database
            for command in SCHEMA:
                self._database.execute(command)
        except Exception, err:
            if self._database:
                self._database.rollback()
            logger.error("Couldn't open archive database {0!r}: {1}".format(
                                                                filename, err))
            try:
                os.unlink(filename)
            except OSError:
                pass
            return None
        self._database.commit()
        return self._database

    def log_event(self, event_type, peer, direction = None, timestamp = None,
                    subject = None, body = None, thread = None, **kwargs):
        """Log an event. 
        
        Only 'chat', 'message' and 'muc' event are supported."""
        if event_type not in ('chat', 'message', 'muc'):
            return
        if direction not in ('in', 'out'):
            return
        if self._database is None:
            self._open_database()
            if self._database is None:
                return
        if timestamp is None:
            timestamp = datetime.now()
        peer_resource = peer.resource
        peer = peer.bare()
        try:
            self._database.execute(
                "INSERT INTO archive(event_type, peer, peer_resource,"
                        " direction, timestamp, subject, body, thread)"
                    " VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_type, peer.as_unicode(), peer_resource, direction,
                                            timestamp, subject, body, thread))
        except:
            self._database.rollback()
            raise
        else:
            self._database.commit()

    def get_records(self, event_type = None, peer = None,
            older_than = None, newer_than = None, limit = None,
                                            order = None, *kwargs):
        if self._database is None:
            self._open_database()
            if self._database is None:
                return
        query = ('SELECT record_id, event_type, peer, peer_resource,' 
                    ' direction, timestamp AS "timestamp [TIMESTAMP]",' 
                    ' subject, body, thread FROM archive')
        where = []
        params = []
        if event_type is not None:
            where.append("event_type = ?")
            params.append(event_type)
        if peer is not None:
            where.append("peer = ?")
            params.append(unicode(peer.bare()))
            if peer.resource:
                where.append("peer_resource = ?")
                params.append(peer.resource)
        if isinstance(older_than, datetime):
            where.append("timestamp < ?")
            params.append(older_than)
        elif older_than is not None:
            where.append("timestamp < "
                        " (select timestamp from archive where record_id = ?)")
            params.append(older_than)
        if isinstance(newer_than, datetime):
            where.append("timestamp > ?")
            params.append(newer_than)
        elif newer_than is not None:
            where.append("timestamp > "
                        " (select timestamp from archive where record_id = ?)")
            params.append(newer_than)
        if where:
            query += " WHERE " + " AND ".join(where)
        if order == self.CHRONOLOGICAL:
            query += " ORDER BY timestamp"
        elif order == self.REVERSE_CHRONOLOGICAL:
            query += " ORDER BY timestamp DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        logger.debug("Executing query: {0!r} with params: {1!r}"
                                                    .format(query, params))
        result = []
        for row in self._database.execute(query, params):
            peer = JID(row['peer'])
            if row['peer_resource']:
                peer = JID(peer.node, peer.domain, row['peer_resource'])
            yield (row['record_id'], SqliteArchiveRecord(
                row['event_type'], peer, row['direction'],
                row['timestamp'], row['subject'], row['body'], row['thread']))
