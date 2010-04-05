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


import os
from cjc.plugin import PluginBase
from cjc import ui

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        ui.activate_cmdtable("python",self)

    def cmd_python(self,args):
        code=args.all()
        if not code or not code.strip():
            self.error("Python code must be given")
            return
        vars={"app":self.cjc,"cjc":self.cjc,
                "debug":self.debug,
                "info":self.info,
                "warning":self.warning,
                "error":self.error}
        try:
            try:
                r=eval(code,vars,vars)
            except SyntaxError:
                r=None
                exec code in vars
        except:
            self.logger.exception("Exception caught in /python code")
            return
        if r is not None:
            self.info(repr(r))

ui.CommandTable("python",50,(
    ui.Command("python",Plugin.cmd_python,
        "/python code|expression",
        "Executes given python code or expression.\n"
        "In the code's namespace following names are defined:\n"
        "  cjc -- CJC Application object.\n"
        "  debug(str,args) -- Passes str%args to debug output.\n"
        "  info(str,args) -- Prints str%args as an info message to the status window.\n"
        "  warning(str,args) -- Prints str%args as a warning message to the status window.\n"
        "  error(str,args) -- Prints str%args as an error message to the status window.\n"
        "If expression is given and evaluates to not None then"
        " it's result will be printed."
        " '/python expression' is equivalent to '/python info(expression)'",
        ("opaque",)),
    )).install()
# vi: sts=4 et sw=4
