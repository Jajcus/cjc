
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
		exec code in vars

ui.CommandTable("python",50,(
	ui.Command("python",Plugin.cmd_python,
		"/python code...",
		"Executes given python code"),
	)).install()
