
import os
from cjc.plugin import PluginBase
from cjc import ui

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		ui.activate_cmdtable("shell",self)

	def command_returned(self,command,ret):
		if ret:
			es=os.WEXITSTATUS(ret)
			if not os.WIFEXITED(ret):
				self.cjc.error("Command exited abnormally")
			elif es:
				self.cjc.warning("Command exited with status %i" % (es,))

	def cmd_shell(self,args):
		command=args.all()
		if not command or not command.strip():
			self.error("Command must be given") 
			return
		try:
			ret=os.system(command)
		except OSError,e:
			self.error("Shell command execution failed: %s" % (e,)) 
		self.command_returned(command,ret)

	def cmd_pipe_in(self,args):
		command=args.all()
		if not command or not command.strip():
			self.error("Command must be given") 
			return
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

	def cmd_pipe_out(self,args):
		command=args.all()
		if not command or not command.strip():
			self.error("Command must be given") 
			return
		try:
			pipe=os.popen(command,"w")
		except OSError,e:
			self.error("Shell command execution failed: %s" % (e,))
			return
		try:
			try:
				if self.cjc.screen.active_window.buffer:
					pipe.write(self.cjc.screen.active_window.buffer.as_string())
			except (OSError,IOError),e:
				self.error("Pipe read failed: %s" % (e,))
		finally:
			ret=pipe.close()
			if ret:
				self.command_returned(command,ret)

ui.CommandTable("shell",50,(
	ui.Command("shell",Plugin.cmd_shell,
		"/shell command [arg...]",
		"Executes given shelll command"),
	ui.Command("pipe_in",Plugin.cmd_pipe_in,
		"/pipe_in command [arg...]",
		"Takes shell command output as user input"),
	ui.Command("pipe_out",Plugin.cmd_pipe_out,
		"/pipe_out command [arg...]",
		"Feeds shell command with current buffer content"),
	)).install()
