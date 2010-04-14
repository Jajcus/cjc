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

"""
Buffer for rich text content.
"""

from __future__ import absolute_import

import collections

from .buffer import Buffer
from . import keytable
from .. import cjc_globals

BufferPosition = collections.namedtuple("BufferPosition", "l c")

class TextBuffer(Buffer):
    """A scrolable container for a formatted text.

    `TextBuffer` contains a list of 'lines'. Each line is a list
    of (attribute, string) tuples. 
    
    `TextBuffer` class is responsible for keeping track of the visible part of
    the text and writting it to a `curses` window.
    
    :Ivariables:
        - `lines`: the buffer content
        - `pos`: current position in the buffer of the window top-left corner.
          `None` means the window will follow the end of the buffer.
        - `_underflow_data`: when in 'fillinig up underflow' mode the
          data to be added at the beginig of `lines`. `None` when not in
          the 'filling up the underflow' mode.
    :Types:
        - `lines`: `list`
        - `pos`: `BufferPosition`
        - `_underflow_data`: `list`
    """
    default_length = 200
    def __init__(self, info, descr_format = "default_buffer_descr",
                command_table = None, command_table_object = None,
                                                        length = None):
        """
        :Parameters:
            - `info`: buffer metadata. E.g. as used in the buffer description
              vi `descr_format`
            - `descr_format`: name of the theme format for creating buffer
              description
            - `command_table`: name of the command table to be active with this
              buffer.
            - `command_table_object`: subject of the commands from the selected
              `command_table`
            - `length`: maximum length of the buffer
        :Types:
            - `info`: `dict`
            - `descr_format`: `str`
            - `command_table`: `str`
            - `length`: `int`
        """
        Buffer.__init__(self, info, descr_format, command_table,
                                                    command_table_object)
        if length:
            self.length = length
        else:
            self.length = self.default_length
        self.lines = []
        self.pos = None
        self.update_pos()
        self._underflow_data = None

    def set_window(self, win):
        """Map the buffer into a window."""
        Buffer.set_window(self, win)
        if win:
            keytable.activate("text-buffer", self)
        else:
            keytable.deactivate("text-buffer", self)

    def append(self, text, attr = "default", activity_level = 1):
        """Add some text to the buffer.
        
        :Parameters:
            - `text`: the text
            - `attr`: attribute (color) of the string
            - `activity_level`: 'importance level' of the action
        :Types:
            - `text`: `unicode`
            - `attr`: `str` or `int`
            - `activity_level`: `int`
        """
        with self.lock:
            return self._append(text, attr, activity_level)

    def _append(self, text, attr, activity_level = 1):
        """Add some text to the buffer.

        This one, as opposed to `self.append` assummes `self.lock`
        is already acquired.
        
        :Parameters:
            - `text`: the text
            - `attr`: attribute (color) of the string
            - `activity_level`: 'importance level' of the action
        :Types:
            - `text`: `unicode`
            - `attr`: `str` or `int`
            - `activity_level`: `int`

        """
        if self._underflow_data is not None:
            target = self._underflow_data
            display = False
        else:
            display = self.window and self.pos is None
            target = self.lines
        if attr is not None and not isinstance(attr, int):
            attr = cjc_globals.theme_manager.attrs[attr]
        if not target:
            target[:] = [[]]
        elif display and target[-1] == []:
            self.window.nl()
        lines = text.split(u"\n")
        num_lines = len(lines)
        for i, line in enumerate(lines):
            if i:
                if i < (num_lines - 1) and display:
                    self.window.nl()
                target.append([])
            if line:
                target[-1].append( (attr, line) )
                if display:
                    win_y, win_x = self.window.win.getyx()
                    while line:
                        if win_x + len(line) > self.window.iw:
                            current, line = self._split_text(line,
                                                        self.window.iw - win_x)
                        else:
                            current, line = line, None
                        self.window.write(current, attr)
                        win_x += len(current)
                        if win_x >= self.window.iw:
                            win_x = 0
                            win_y += 1
                            if win_y >= self.window.ih:
                                win_y = self.window.ih - 1
                    else:
                        self.window.write(line, attr)
        if len(self.lines) > self.length and self.pos is None:
            self.lines = self.lines[-self.length:]
        if not self.window or self.pos is not None and activity_level:
            self.activity(activity_level)

    def append_line(self, text, attr="default", activity_level = 1):
        """Append a line to the buffer.
        
        :Parameters:
            - `text`: the line of text (with no EOL character)
            - `attr`: attribute (color) of the string
            - `activity_level`: 'importance level' of the action
        :Types:
            - `text`: `unicode`
            - `attr`: `str` or `int`
            - `activity_level`: `int`
        """
        with self.lock:
            return self._append_line(text, attr, activity_level)

    def _append_line(self, text, attr, activity_level = 1):
        """Append a line to the buffer.
        
        This one, as opposed to `self.append_line` assummes `self.lock` is
        already acquired.

        :Parameters:
            - `text`: the line of text (with no EOL character)
            - `attr`: attribute (color) of the string
            - `activity_level`: 'importance level' of the action
        :Types:
            - `text`: `unicode`
            - `attr`: `str` or `int`
            - `activity_level`: `int`
        """
        if not isinstance(attr, int):
            attr = cjc_globals.theme_manager.attrs[attr]
        self._append(text + u"\n", attr, activity_level)

    def append_themed(self, theme_fmt, params, activity_level = 1):
        """Add a message formatted via a CJC theme to the buffer.

        :Parameters:
            - `theme_fmt`: name of the theme format to use
            - `params`: message data
            - `activity_level`: 'importance level' of the action
        :Types:
            - `theme_fmt`: `str`
            - `params`: mapping
            - `activity_level`: `int`
        """
        for attr, text in cjc_globals.theme_manager.format_string(
                                                            theme_fmt, params):
            self.append(text, attr, activity_level)

    def write(self, text):
        """Write a text to the buffer using default attributes.

        :Parameters:
            - `text`: the text to write
        :Types:
            - `text`: `unicode`"""
        self.lock.acquire()
        try:
            self._append(text, "default")
            self.update()
        finally:
            self.lock.release()

    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.pos = None
            self.lines = [[]]
            if self.window:
                self.window.clear()

    @staticmethod
    def _line_length(line):
        """Compute the length of a buffer line.

        :Parameters:
            - `line`: a line from the buffer
        :Types:
            - `line`: a list of (attribute, text) tuples.

        :Returns: length of the line in characters
        """
        ret = 0
        for dummy, text in line:
            ret += len(text)
        return ret

    def fill_top_underflow(self, lines_needed):
        """Called when trying to scroll over the top of the buffer.

        May be overriden in derived classes to provide extra data (e.g.
        archival messages).
        
        Content added to the buffer in the code called from this method will be
        appended at the top of the buffer."""
        pass

    def offset_back(self, width, back, pos = None, fill_underflow = True):
        """Compute a position (buffer line, character in the line) in the
        buffer `back` 'screen lines' up from postition `pos`.
        
        :Parameters:
            - `width`: window width ('screen line' width)
            - `back`: number of screen lines
            - `pos`: start position. `None` for the end of the buffer.
        :Types:
            - `width`: `int`
            - `back`: `int`
            - `pos`: `BufferPosition`

        :Returns: the computed position
        :Returntype: `BufferPosition`
        """
        # FIXME: what about pos.c
        if not self.lines:
            return BufferPosition(0, 0)
        if pos is None or pos.l >= len(self.lines):
            if self.lines[-1] == []:
                pos_l = len(self.lines) - 1
            else:
                pos_l = len(self.lines)
            if pos_l <= 0:
                return 0, 0
        else:
            pos_l = pos.l
        while back > 0 and pos_l > 1:
            pos_l -= 1
            line = self.lines[pos_l]
            line_len = self._line_length(line)
            line_height = line_len / width + 1
            back -= line_height
        if back > 0:
            if not fill_underflow:
                return BufferPosition(0, 0)
            self._underflow_data = []
            try:
                self.fill_top_underflow(back)
                if self._underflow_data and self._underflow_data[-1] == []:
                    self._underflow_data = self._underflow_data[:-1]
                if not self._underflow_data:
                    return BufferPosition(0, 0)
                pos_l = len(self._underflow_data)
                self.lines = self._underflow_data + self.lines
            finally:
                self._underflow_data = None
            return self.offset_back(width, back, BufferPosition(pos_l, 0))
        if back == 0:
            return BufferPosition(pos_l, 0)
        return BufferPosition(pos_l, (-back) * width)

    def offset_forward(self, width, forward, pos):
        """Compute a position (buffer line, character in the line) in the
        buffer `forward` 'screen lines' down from postition `pos`.
        
        :Parameters:
            - `width`: window width ('screen line' width)
            - `forward`: number of screen lines
            - `pos`: start position. `None` for the end of the buffer.
        :Types:
            - `width`: `int`
            - `forward`: `int`
            - `pos`: `BufferPosition`

        :Returns: the computed position
        :Returntype: `BufferPosition`
        """
        if pos is None:
            return pos

        if pos.l >= len(self.lines):
            pos_l = len(self.lines) - 1
            if self.lines[-1] == []:
                pos_l -= 1
            if pos_l > 0:
                return BufferPosition(pos_l, 0)
            else:
                return BufferPosition(0, 0)
        else:
            pos_l = pos.l

        if pos.c > 0:
            right = self._split_text(self.lines[pos_l], pos.c)[1]
            pos_l += 1
            line_len = self._line_length(right)
            forward -= line_len / width + 1

        end = len(self.lines)
        if self.lines[-1] == []:
            end -= 1

        pos_l -= 1
        while forward > 0 and pos_l < end - 1:
            pos_l += 1
            line = self.lines[pos_l]
            line_len = self._line_length(line)
            line_height = line_len / width + 1
            forward -= line_height

        if forward >= 0:
            return BufferPosition(pos_l, 0)

        if pos_l > 0:
            return BufferPosition(pos_l - 1, 0)
        else:
            return BufferPosition(0, 0)

    @staticmethod
    def _split_text(text, index):
        """Split a string into two at given position.
        
        :Parameters:
            - `text`: the string to split
            - `index`: the position
        """
        return text[:index], text[index:]

    @staticmethod
    def _cut_line(line, cut_position):
        """Split a buffer line into two.

        :Parameters:
            - `line`: the buffer line to split
            - `cut_position`: cut position
        :Types:
            - `line`: list of (attribute, text) tuples
            - `cut_position`: `int`

        :Returns: two lines
        :Returntype: tuple of two lists of (attribute, text) tuples
        """
        index = 0
        left = []
        right = []
        for attr, text in line:
            start_index = index
            index += len(text)
            if index < cut_position:
                left.append( (attr, text) )
            elif start_index < cut_position and index > cut_position:
                left.append( (attr, text[:cut_position - index]) )
                right.append( (attr, text[cut_position - index:]) )
            else:
                right.append( (attr, text) )
        return left, right

    def format(self, width, height):
        """Return the buffer content starting from the current position
        as a list of (attribute, text) pairs to be displayed in a window
        of given dimensions.

        This is used to redraw a window displaying this buffer.
        
        :Parameters:
            - `width`: target window width
            - `height`: target window height
        :Types:
            - `width`: `int`
            - `height`: `int`
        
        :Return: formatted content
        :Returntype: `list` of (`int`, `unicode`) tuples"""
        with self.lock:
            return self._format(width, height)

    def _format(self, width, height):
        """Return the buffer content starting from the current position
        as a list of (attribute, text) pairs to be displayed in a window
        of given dimensions.

        This is used to redraw a window displaying this buffer.

        This one assumes `self.lock` is already acquired.
        
        :Parameters:
            - `width`: target window width
            - `height`: target window height
        :Types:
            - `width`: `int`
            - `height`: `int`
        
        :Return: formatted content
        :Returntype: `list` of (`int`, `unicode`) tuples"""

        if self.pos is None:
            pos_l, pos_c = self.offset_back(width, height,
                                                    fill_underflow = False)
        else:
            pos_l, pos_c = self.pos

        if pos_c:
            line = self._cut_line(self.lines[pos_l], pos_c)[1]
            ret = [line]
            pos_l += 1
            height -= self._line_length(line) / width + 1
        else:
            ret = []

        end = len(self.lines)
        if end and self.lines[-1] == []:
            end -= 1

        while height > 0 and pos_l < end:
            line = self.lines[pos_l]
            while line is not None and height > 0:
                line_len = self._line_length(line)
                if line_len > width:
                    part, line = self._cut_line(line, width)
                else:
                    part, line = line, None
                if part == [] and height == 1:
                    break
                ret.append(part)
                height -= 1
            pos_l += 1
        return ret

    def update_pos(self):
        """Update current position information in the buffer meta-data and
        visible description."""
        if self.pos:
            self.update_info({"bufrow": self.pos[0], "bufcol": self.pos[1]})
        else:
            self.update_info({"bufrow": "", "bufcol":""})

    def page_up(self):
        """Handle page-up request."""
        with self.lock:
            if self.pos is None:
                pos = self.offset_back(self.window.iw, self.window.ih-1)
            else:
                pos = self.pos

            if pos == (0, 0):
                self.pos = pos
                formatted = self._format(self.window.iw, self.window.ih + 1)
                if len(formatted) <= self.window.ih:
                    self.pos = None
            else:
                self.pos = self.offset_back(self.window.iw, self.window.ih-1,
                                                                            pos)
        self.update_pos()
        self.window.draw_buffer()
        self.window.update()

    def page_down(self):
        """Handle page-down request."""
        with self.lock:
            if self.pos is None:
                self.update_pos()
                return

            self.pos = self.offset_forward(self.window.iw, self.window.ih - 1,
                                                                    self.pos)
            formatted = self.format(self.window.iw, self.window.ih + 1)
            if len(formatted) <= self.window.ih:
                self.pos = None
        self.update_pos()
        self.window.draw_buffer()
        self.window.update()

    def as_string(self):
        """Return string (unicode) representation of the buffer content.
        
        :Returntype: `unicode`"""
        with self.lock:
            ret = u""
            num_lines = len(self.lines)
            for i in range(0, num_lines):
                for dummy, text in self.lines[i]:
                    ret += text
                if i < num_lines - 1:
                    ret += u"\n"
        return ret

from .keytable import KeyFunction

keytable.install(
    keytable.KeyTable("text-buffer", 30, (
        KeyFunction("page-up",
                TextBuffer.page_up,
                "Scroll buffer one page up",
                "PPAGE"),
        KeyFunction("page-down",
                TextBuffer.page_down,
                "Scroll buffer one page down",
                "NPAGE"),
        ))
    )

# vi: sts=4 et sw=4
