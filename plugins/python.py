
import os
from cjc.plugin import PluginBase
from cjc import ui

class Plugin(PluginBase):
    def __init__(self,app):
        PluginBase.__init__(self,app)
        ui.activate_cmdtable("python",self)

    def cmd_python(self,args):
        code=args.all()
        if not code or not code.strip():
            self.error("Python code must be given")
            return
        vars={"app":self.cjc}
        try:
            r=eval(code,vars,vars)
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
