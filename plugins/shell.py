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


import os
import locale

from cjc.plugin import PluginBase
from cjc import ui

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        ui.activate_cmdtable("shell",self)

    def command_returned(self,command,ret):
        if ret:
            es=os.WEXITSTATUS(ret)
            if not os.WIFEXITED(ret):
                self.error("Command exited abnormally")
            elif es:
                self.warning("Command exited with status %i" % (es,))

    def cmd_shell(self,args):
        if args.get()=="-noterm":
            args.shift()
            term=False
        else:
            term=True
        command=args.all()
        if not command or not command.strip():
            self.error("Command must be given")
            return
        try:
            if term:
                self.cjc.screen.shell_mode()
                try:
                    ret=os.system(command)
                finally:
                    self.cjc.screen.prog_mode()
            else:
                ret=os.system(command+" 0</dev/null >/dev/null 2>&1")
        except OSError,e:
            self.error("Shell command execution failed: %s" % (e,))
        self.command_returned(command,ret)

    def cmd_pipe_in(self,args):
        if args.get()=="-noterm":
            args.shift()
            term=False
        else:
            term=True
        command=args.all()
        if not command or not command.strip():
            self.error("Command must be given")
            return
        if term:
            self.cjc.screen.shell_mode()
        else:
            command+=" 0</dev/null 2>&1"
        try:
            try:
                pipe=os.popen(command,"r")
            except OSError,e:
                self.error("Shell command execution failed: %s" % (e,))
                return
            try:
                try:
                    while 1:
                        l=pipe.readline()
                        if not l:
                            break
                        if l.endswith("\n"):
                            l=l[:-1]
                        if not l or l[0] in ("/","\\"):
                            l="\\"+l
                        l=unicode(l,self.cjc.screen.encoding,"replace")
                        self.cjc.screen.do_user_input(l)
                except (OSError,IOError),e:
                    self.error("Pipe read failed: %s" % (e,))
            finally:
                ret=pipe.close()
                if ret:
                    self.command_returned(command,ret)
        finally:
            if term:
                self.cjc.screen.prog_mode()

    def cmd_pipe_out(self,args):
        if args.get()=="-noterm":
            args.shift()
            term=False
        else:
            term=True
        command=args.all()
        if not command or not command.strip():
            self.error("Command must be given")
            return
        if term:
            self.cjc.screen.shell_mode()
        else:
            command+=" >/dev/null 2>&1"
        try:
            try:
                pipe=os.popen(command,"w")
            except OSError,e:
                self.error("Shell command execution failed: %s" % (e,))
                return
            try:
                try:
                    if self.cjc.screen.active_window.buffer:
                        s=self.cjc.screen.active_window.buffer.as_string()
                        s=s.encode(self.cjc.screen.encoding,"replace")
                        pipe.write(s)
                except (OSError,IOError),e:
                    self.error("Pipe read failed: %s" % (e,))
            finally:
                ret=pipe.close()
                if ret:
                    self.command_returned(command,ret)
        finally:
            if term:
                self.cjc.screen.prog_mode()

ui.CommandTable("shell",50,(
    ui.Command("shell",Plugin.cmd_shell,
        "/shell [-noterm] command [arg...]",
        "Executes given shelll command. If -noterm option is used"
        " then the command is not given access to the terminal and the screen"
        " is not refreshed after command exits.",
        ("-noterm","opaque")),
    ui.Command("pipe_in",Plugin.cmd_pipe_in,
        "/pipe_in command [arg...]",
        "Takes shell command output as user input. If -noterm option is used"
        " then the command is not given access to the terminal and the screen"
        " is not refreshed after command exits.",
        ("-noterm","opaque")),
    ui.Command("pipe_out",Plugin.cmd_pipe_out,
        "/pipe_out command [arg...]",
        "Feeds shell command with current buffer content. If -noterm"
        " option is used then the command is not given access to the"
        " terminal and the screen is not refreshed after command exits.",
        ("-noterm","opaque")),
    )).install()
# vi: sts=4 et sw=4
