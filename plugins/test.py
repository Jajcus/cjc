
# Normative reference: JEP-0092

import os
import threading
import time

from cjc import ui
from cjc.plugin import PluginBase

class Test(threading.Thread):
	def __init__(self,plugin,name):
		threading.Thread.__init__(self,name=name)
		self.plugin=plugin
		self.buffer=ui.TextBuffer(self.plugin.cjc.theme_manager,name)
		self.buffer.register_commands({	"close": (self.cmd_close,
							"/close",
							"Closes current test")
						})
		self.stop_it=0
	def cmd_close(self,args):
		args.finish()
		self.stop_it=1
		self.buffer.close()

class ScrollTest(Test): 
	def __init__(self,plugin):
		Test.__init__(self,plugin,"Scroll test")
		
	def run(self):
		self.plugin.cjc.info("Test thread started")
		for i in range(0,200):
			if self.plugin.cjc.exiting:
				break
			if self.stop_it:
				break
			self.buffer.append_line("line %i" % (i+1,))
		self.buffer.update()
		self.plugin.cjc.info("Test thread finished")

class WrapTest(Test): 
	def __init__(self,plugin):
		Test.__init__(self,plugin,"Wrap test")
		
	def run(self):
		self.plugin.cjc.info("Test thread started")
		for i in range(0,20):
			for j in range(0,15):
				if self.stop_it:
					break
				if self.plugin.cjc.exiting:
					break
				time.sleep(0.1)
				self.buffer.append("line-%i-word-%i " % (i+1,j+1))
				self.buffer.update()
			self.buffer.append_line("")
			self.buffer.update()
		self.buffer.update()
		self.plugin.cjc.info("Test thread finished")
	
class InputTest(Test): 
	def __init__(self,plugin):
		Test.__init__(self,plugin,"Input")
		self.questions=[
			("What is your name?","text-single",u"",None,
				u"Your name is %s.",u"You don't seem to know your own name"),
			("Do you like me?","boolean",1,None,
				u"Your answer is %s.",u"Are you afraid to answer?"),
			("How old are you?","choice",1,[xrange(1,100)],
				u"Your answer is %s.",u"Are you afraid to answer?"),
			("Male or Female?","choice",1,["m","f"],
				u"Your answer is %s.",u"Are you afraid to answer?"),
			]
		
	def run(self):
		self.ask_next_question()

	def ask_next_question(self):
		if not self.questions:
			return
		q,t,d,v,m1,m2=self.questions.pop(0)
		self.plugin.cjc.command_line.ask_question(q,t,d,self.input_handler,
								self.abort_handler,(m1,m2),v)
	
	def input_handler(self,arg,answer):
		self.buffer.append_line(arg[0] % answer)
		self.buffer.update()
		self.ask_next_question()

	def abort_handler(self,arg):
		self.buffer.append_line(arg[1])
		self.buffer.update()
		self.ask_next_question()
		
class Plugin(PluginBase):
	tests={
		"scroll": ScrollTest,
		"wrap": WrapTest,
		"input": InputTest
		}
	def __init__(self,app):
		PluginBase.__init__(self,app)
		app.register_commands({"test": (self.cmd_test,
							"/test [scroll|wrap]",
							"Various tests of CJC engine.")
						})
	
	def cmd_test(self,args):
		name=args.shift()
		if not name:
			self.cjc.error("Test name not given")
			return
		clas=self.tests.get(name,None)
		if clas is None:
			self.cjc.error("Uknown test: "+name)
			return
		test_thread=clas(self)
		test_thread.start()
