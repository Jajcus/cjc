
import os
from cjc.plugin import PluginBase

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		app.register_commands({"python": (self.cmd_python,
							"/python code...",
							"Executes given python code")
						})

	def cmd_python(self,args):
		code=args.all()
		if not code or not code.strip():
			self.error("Python code must be given") 
			return
		vars={"app":self.cjc}
		exec code in vars
