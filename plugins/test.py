
# Normative reference: JEP-0092

import os
import threading
import time

from cjc import ui
from cjc.plugin import PluginBase

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		app.register_commands({"test": (self.cmd_test,
							"/test [scroll|wrap]",
							"Various tests of CJC engine.")
						})
	
	def cmd_test(self,args):
		name=args.shift()
		handler=getattr(self,"test_"+name,None)
		if handler is None:
			self.cjc.error("Uknown test: "+name)
			return
		test_thread=threading.Thread(None,self.start_test,name+" test",(handler,args))
		test_thread.start()

	def start_test(self,handler,args):
		self.cjc.info("Test thread started")
		handler(args)
		self.cjc.info("Test thread finished")

	def test_scroll(self,args):
		buf=ui.TextBuffer(self.cjc.theme_manager,"Scroll Test")
		for i in range(0,200):
			buf.append_line("line %i" % (i+1,))
		buf.update()

	def test_wrap(self,args):
		buf=ui.TextBuffer(self.cjc.theme_manager,"Scroll Test")
		for i in range(0,200):
			for j in range(0,15):
				if self.cjc.exiting:
					return
				time.sleep(0.1)
				buf.append("line-%i-word-%i " % (i,j))
				buf.update()
			buf.append_line("")
			buf.update()
		buf.update()
