
import os
from cjc.plugin import PluginBase
from cjc import commands

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		commands.activate_table("python",self)

	def cmd_python(self,args):
		code=args.all()
		if not code or not code.strip():
			self.error("Python code must be given") 
			return
		vars={"app":self.cjc}
		exec code in vars

ctb=commands.CommandTable("python",50,(
	commands.Command("python",Plugin.cmd_python,
		"/python code...",
		"Executes given python code"),
	))
commands.install_table(ctb)
