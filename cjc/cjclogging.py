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

class UnicodeFormatter(logging.Formatter):
    def __init__(self,encoding,fmt=None,datefmt=None):
        logging.Formatter.__init__(self,fmt,datefmt)
        self.encoding=encoding
    def format(self,record):
        s=logging.Formatter.format(self,record)
        return s.encode(self.encoding,"replace")

class ScreenHandler(logging.Handler):
    def __init__(self,app,level=logging.NOTSET):
        logging.Handler.__init__(self,level=level)
        self.app=app
    def emit(self,record):
        msg=self.format(record)
        if record.levelno==logging.ERROR:
            self.app.show_error(msg)
        elif record.levelno==logging.WARNING:
            self.app.show_warning(msg)
        elif record.levelno==logging.DEBUG:
            self.app.show_debug(msg)
        else:
            self.app.show_info(msg)

# vi: sts=4 et sw=4
