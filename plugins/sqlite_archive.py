# Console Jabber Client
# Copyright (C) 2010-2010 Jacek Konieczny
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

"""SQLite based message archive."""

from datetime import datetime
import logging
import os
import sqlite3
import collections
import threading
import re
import itertools
import codecs
import shutil

from pyxmpp.jid import JID

from cjc.main import Application
from cjc.plugin import Archiver, Archive, ArchiveRecord, Plugin, Configurable
from cjc.plugin import CLI, cli_command, cli_completion
from cjc.plugin import EventListener, event_handler
from cjc import ui, cjc_globals

logger = logging.getLogger("cjc.plugin.sqlite_archive")

SqliteArchiveRecord = collections.namedtuple("SqliteArchiveRecord",
        "event_type peer direction timestamp subject body thread")
ArchiveRecord.register(SqliteArchiveRecord)

SCHEMA = ["""
CREATE TABLE archive (
    record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
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

class SqliteArchive(Plugin, Archiver, Archive, Configurable, EventListener):
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

    @event_handler("config loaded")
    def ev_config_loaded(self, event, arg):
        """Initialize the database on load."""
        self._open_database()

    @property
    def filename(self):
        filename = self.settings.get("filename")
        if not filename:
            return None
        filename = os.path.expanduser(filename)
        return filename

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
        filename = self.filename
        if os.path.exists(filename):
            new = False
        else:
            new = True
            logger.info("Sqlite archive: no database found, will create a new one.")
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
        if new:
            logger.warning("New sqlite archive created."
                    " You may want to use /migrate_archive command to load old"
                    " log files into the new archive.")
        return self._database

    def _start_transaction(self):
        if self._database is None:
            self._open_database()
            if self._database is None:
                return None
        return self._database

    def _rollback(self):
        return self._database.rollback()

    def _commit(self):
        return self._database.commit()

    def _log_event(self, event_type, peer, direction = None, timestamp = None,
                    subject = None, body = None, thread = None, **kwargs):
        """Log an event using existing transaction."""
        if timestamp is None:
            timestamp = datetime.now()
        peer_resource = peer.resource
        peer = peer.bare()
        self._database.execute(
                "INSERT INTO archive(event_type, peer, peer_resource,"
                        " direction, timestamp, subject, body, thread)"
                    " VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_type, peer.as_unicode(), peer_resource, direction,
                                            timestamp, subject, body, thread))

    def log_event(self, event_type, peer, direction = None, timestamp = None,
                    subject = None, body = None, thread = None, **kwargs):
        """Log an event. 
        
        Only 'chat', 'message' and 'muc' event are supported."""
        if event_type not in ('chat', 'message', 'muc'):
            return
        if direction not in ('in', 'out'):
            return
        if not self._start_transaction():
            return
        try:
            self._log_event(event_type, peer, direction, timestamp, subject,
                                                        body, thread, **kwargs)
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
            if limit and order in (self.CHRONOLOGICAL,
                                            self.REVERSE_CHRONOLOGICAL):
                where.append("+peer = ?")
            else:
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


IMPORT_PATTERNS = {
        u"[%(T:now:%c)s] Incoming message\nFrom: %(sender)s\n"
                u"Subject: %(subject)s\n%(body)s\n":
                    ur"(^|\n)\[(?P<timestamp@@>[^]]+)\]"
                            ur" (?P<in>Incoming) message\nFrom: (?P<sender@@>[^\n]+)\n"
                            ur"Subject: (?P<subject@@>[^\n]*)\n",
        u"[%(T:now:%c)s] Outgoing message\nTo: %(recipient)s\n"
                u"Subject: %(subject)s\n%(body)s\n":
                    ur"(^|\n)\[(?P<timestamp@@>[^]]+)\]"
                            ur" (?P<out>Outgoing) message\nTo: (?P<recipient@@>[^\n]+)\n"
                            ur"Subject: (?P<subject@@>[^\n]*)\n",
        u"[%(T:now:%c)s] <%(J:sender:nick)s> %(body)s\n":
                    ur"(^|\n)\[(?P<timestamp@@>[^]]{10,30})\] <(?P<sender@@>[^>]+)> ",
        }

LOG_FILENAME_RE = re.compile(".*[a-zA-Z0-9-]$")

def in_pairs(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..., (sn, None)"""
    a, b = itertools.tee(itertools.chain(iterable, [None]))
    next(b, None)
    return itertools.izip(a, b)

class ArchiveImporter(object):
    def __init__(self):
        self.buffer = ui.TextBuffer({"buffer_name": "Archive importer"},
                                                command_table = "buffer")
	self.settings = None
	self.file_logger_settings = None
        self.archive = None
        self.older_than = None

    def _get_log_dir(self, msg_type):
        if msg_type + "_filename" in self.file_logger_settings:
            filename = self.file_logger_settings[msg_type + "_filename"]
        else:
            filename = self.settings.get(msg_type + ".log_filename")

        if not filename:
            return None

        self.info(u"Configured {0} log file path: {1}".format(msg_type,
                                                                    filename))
        if not filename.endswith("/%(J:peer:bare)s"):
            self.warning(u"Unsupported log file name pattern.")
            return None

        path = filename.rsplit("/", 1)[0]
        path = cjc_globals.theme_manager.substitute(path, {})
        if not os.path.isdir(path):
            self.warning(u"{0} is not a directory.".format(path))
            return None
        self.info(u"{0} log directory: {1}".format(msg_type.capitalize(), path))
        return path

    def _get_pattern(self, msg_type, direction):
        key = "{0}_format_{1}".format(msg_type, direction)
        if key in self.file_logger_settings:
            pattern = self.file_logger_settings[key]
        else:
            pattern = self.settings.get("{0}.log_{1}"
                                                .format(msg_type, direction))
        if not pattern:
            self.warning("No log pattern configured for: {0} {1}"
                                                .format(msg_type, direction))
            return None
        if pattern not in IMPORT_PATTERNS:
            self.warning("Unsupported pattern configured for {0} {1}: {2}"
                                        .format(msg_type, direction, pattern))
            return None
        return pattern

    def _get_patterns(self, msg_type):
        in_pattern = self._get_pattern(msg_type, "in")
        out_pattern = self._get_pattern(msg_type, "out")
        if None in (in_pattern, out_pattern):
            return None
        return IMPORT_PATTERNS[in_pattern], IMPORT_PATTERNS[out_pattern]

    def _nothing_to_do(self):
        self.error(u"Found nothing that could be imported")

    @staticmethod
    def _sender_is_jid(sender, jid):
        cjc = Application.instance
        if not sender:
            return False
        if "@" in sender:
            try:
                sender_jid = JID(sender)
                if sender_jid.bare() == jid.bare():
                    return True
            except ValueError:
                pass
        if sender == cjc.get_user_info(jid, "nick"):
            return True
        if sender == cjc.get_user_info(jid, "rostername"):
            return True
        return sender == jid.node

    @staticmethod
    def _parse_timestamp(timestamp):
        for pattern in (
                "%a %b %d %H:%M:%S %Y", 
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%s",
                "%a %d %b %Y %I:%M:%S %p ",
                ):
            try:
                return datetime.strptime(timestamp, pattern)
            except ValueError:
                continue
        raise ValueError

    def _import_log(self, msg_type, peer, pattern, data):
        self_jid = self.settings["jid"]
        user_dir = {}
        matches, unparseable, imported = 0, 0, 0
        for match, next_match in in_pairs(pattern.finditer(data)):
            direction = None
            matches += 1
            groups = match.groupdict()
            if groups.get("in"):
                direction = "in"
            elif groups.get("out"):
                direction = "out"
            if not direction:
                sender = None
                for var in ("sender", "sender_in", "sender_out"):
                    sender = groups.get(var)
                    if sender:
                        break
                if not sender:
                    logger.debug(u"Unparseable entry for {0}: no sender"
                            u" (groups: {1!r})".format(peer, groups))
                    unparseable += 1
                    continue
                if sender in user_dir:
                    direction = user_dir[sender]
                else:
                    is_me = self._sender_is_jid(sender, self_jid)
                    is_peer = self._sender_is_jid(sender, peer)
                    if is_me and not is_peer:
                        direction = "out"
                    elif is_peer and not is_me:
                        direction = "in"
                    else:
                        self.warning(u"Assuming '{0}' is '{1}'"
                                                        .format(sender, peer))
                        direction = "in"
                    user_dir[sender] = direction
                if not direction:
                    logger.debug(u"Unparseable entry for {0}: unknown direction"
                                    .format(peer))
                    unparseable += 1
                    continue
            timestamp = None
            for var in ("timestamp", "timestamp_in", "timestamp_out"):
                timestamp = groups.get(var)
                if timestamp:
                    break
            if not timestamp:
                logger.debug(u"Unparseable entry for {0}: no timestamp"
                                                            .format(peer))
                unparseable += 1
                continue
            try:
                timestamp = self._parse_timestamp(timestamp)
            except ValueError:
                logger.debug(u"Unparseable entry for {0}: bad timestamp: {1}"
                                                    .format(peer, timestamp))
                unparseable += 1
                continue
            subject = None
            for var in ("subject", "subject_in", "subject_out"):
                subject = groups.get(var)
                if subject:
                    break
            body_start = match.end()
            if next_match:
                body_end = next_match.start()
            else:
                body_end = len(data)
            body = data[body_start:body_end]
            logger.debug("timestamp={0!r} dir={1!r} subject={2!r} body={3!r}"
                                .format(timestamp, direction, subject, body))
            if self.older_than is None or timestamp < self.older_than:
                self.archive._log_event(msg_type, peer, direction, timestamp,
                                                                subject, body)
                imported += 1
        self.info("  {0} matches {1} unparseable {2} imported".format(
                                            matches, unparseable, imported))
        return matches, unparseable, imported

    def _import(self, msg_type, directory, patterns):
        in_pattern, out_pattern = patterns
        same_pattern = (in_pattern == out_pattern)
        if same_pattern:
            pattern = in_pattern.replace("@@", "")
        else:
            in_pattern = in_pattern.replace("@@", "_in")
            out_pattern = out_pattern.replace("@@", "_out")
            pattern = "(?:{0}|{1})".format(in_pattern, out_pattern)
        pattern = re.compile(pattern)
        matches, unparseable, imported = 0, 0, 0
        for filename in sorted(os.listdir(directory)):
            path = os.path.join(directory, filename)
            if not os.path.isfile(path) \
                    or not LOG_FILENAME_RE.match(filename):
                self.info(" skipping {0}".format(filename))
                continue
            try:
                peer = JID(filename)
            except ValueError:
                self.info(" skipping {0} (bad jid)".format(filename))
                continue
            self.info(" {0}...".format(filename))
            with codecs.open(path, "r", "utf-8", "replace") as log_file:
                data = log_file.read()
            new_m, new_up, new_i = self._import_log(msg_type, peer,
                                                                pattern, data)
            matches += new_m
            unparseable += new_up
            imported += new_i
        return matches, unparseable, imported

    def error(self, message):
        self.buffer.append_themed("error", message)
        self.buffer.update()

    def warning(self, message):
        self.buffer.append_themed("warning", message)
        self.buffer.update()

    def info(self, message = ""):
        self.buffer.append_themed("info", message)
        self.buffer.update()

    def _locate_settings(self):
	cjc = Application.instance
        self.settings = cjc.settings
        try:
            self.file_logger_settings = cjc.plugins.get_configurable(
                                                "file_logger").settings
        except KeyError:
            self.file_logger_settings = {}

    def start(self):
        cjc_globals.screen.display_buffer(self.buffer)
	self._locate_settings()
        if not self.settings.get("jid"):
            return self.error("Own JID not set, cannot continue)")
        if Application.instance.stream:
            return self.error("You must be disconnected"
                                                    " to migrate old archive.")
        if not Application.instance.roster:
            return self.error("Roster is required for archive migration,"
                                    " but not available yet.\n"
                                "Connect to the server to download the roster,"
                                " then disconnect and retry /migrate_archive")
        self.archive = Application.instance.plugins.get_service(SqliteArchive)
        if not self.archive:
            return self.error("Could not locate the sqlite3 archive service.")

        oldest = list(self.archive.get_records(limit = 1,
                                        order = Archive.CHRONOLOGICAL))
        if oldest:
            self.older_than = oldest[0][1].timestamp

        chat_dir = self._get_log_dir("chat")
        message_dir = self._get_log_dir("message")
        if not chat_dir and not message_dir:
            return self._nothing_to_do()
        if chat_dir:
            chat_patterns = self._get_patterns("chat")
        else:
            chat_patterns = None
        if message_dir:
            message_patterns = self._get_patterns("message")
        else:
            message_patterns = None
        if not chat_patterns and not message_patterns:
            return self._nothing_to_do()
        
        backup_filename = self.archive.filename + ".backup"
        if os.path.exists(backup_filename):
            return self.error("Archive backup file {0} already exists."
                    " Remove or rename it if you really wish to continue"
                                                    .format(backup_filename))

        try:
            shutil.copy(self.archive.filename, backup_filename)
        except (IOError, OSError), err:
            return self.error(u"Couldn't make a backup of the archive."
                                        u" Copying {0} to {1} failed: {2}"
                    .format(self.archive.filename.decode("utf-8"),
                                backup_filename.decode("utf-8"), err))
        
        if self.older_than:
            self.info()
            self.info("Will import log entries older than {0}"
                        .format(self.older_than.strftime("%Y-%m-%d %H:%M")))

        self.archive._start_transaction()
        try:
            if chat_patterns:
                self.info()
                self.info("Importing chat...")
                chat_stats = self._import("chat", chat_dir, chat_patterns)

            if message_patterns:
                self.info()
                self.info("Importing messages...")
                msg_stats = self._import("message", message_dir,
                                                            message_patterns)
        except:
            self.info("Error occured, rolling back the changes.")
            self.archive._rollback()
            raise
        else:
            self.archive._commit()
    
        self.info()
        self.info("Archive migration finished.")
        self.info()
        self.info("  {0} chat messages found, {1} unparseable, {2} imported."
                                            .format(*chat_stats))
        self.info("  {0} messages found, {1} unparseable, {2} imported."
                                            .format(*msg_stats))
        self.info()
        self.info("You may now want to disable file logging.")
    
class ArchiveCLI(Plugin, CLI):
    command_table_name = "sqlite_archive"
    @cli_command
    def cmd_migrate_archive(self, args):
        """/migrate_archive

        Import old message log files into the Sqlite3 archive."""
        importer = ArchiveImporter()
        importer.start()

