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
        vars={"app":self.cjc}
        try:
            try:
                r=eval(code,vars,vars)
            except SyntaxError:
                r=None
                exec code in vars
        except:
            self.cjc.print_exception()
            return
        if r is not None:
            self.info(repr(r))

ui.CommandTable("python",50,(
    ui.Command("python",Plugin.cmd_python,
        "/python code...",
        "Executes given python code"),
    )).install()
# vi: sts=4 et sw=4
