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
import threading
import time

from cjc import ui
from cjc.plugin import PluginBase

class Test(threading.Thread):
    def __init__(self,plugin,name):
        threading.Thread.__init__(self,name=name)
        self.plugin=plugin
        self.buffer=ui.TextBuffer(self.plugin.cjc.theme_manager,name)
        ui.activate_cmdtable("test buffer",self)
        self.stop_it=0
    def cmd_close(self,args):
        args.finish()
        self.stop_it=1
        self.buffer.close()

ui.CommandTable("test buffer",50,(
    ui.Command("close",Test.cmd_close,
        "/close",
        "Closes current test"),
    )).install()

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
            ("What is your name?","text-single",u"",None,0),
            ("Do you like me?","boolean",None,None,0),
            ("How old are you?","choice",None,[xrange(1,100)],0),
            ("Male or Female?","choice",None,["m","f"],0),
            ("Your favorite animal?","list-single",None,
                {1:"dog",2:"cat",3:"turtle",100:"Tux, the penguin with atitude, logo of the Linux operating system. What can I write more, to make this entry big enough?"},0),
            ("Your favorite animals?","list-multi",None,
                {1:"dog",2:"cat",3:"turtle",100:"Tux, the penguin with atitude, logo of the Linux operating system. What can I write more, to make this entry big enough?"},0),
            ("Do you like very, very long questions which make no sense beside being very long?",
                "boolean",None,None,0),
            ]

    def run(self):
        self.ask_next_question()

    def ask_next_question(self):
        if not self.questions:
            return
        q,t,d,v,r=self.questions.pop(0)
        self.buffer.ask_question(q,t,d,self.input_handler,self.abort_handler,(t,v),v,r)

    def input_handler(self,arg,answer):
        if answer in (None,[],u""):
            self.buffer.append_line("You didn't answer")
        else:
            type,values=arg
            if type=="boolean":
                if answer:
                    ans="yes"
                else:
                    ans="no"
            elif type=="list-single":
                ans=values[answer]
            elif type=="list-multi":
                ans=[values[a] for a in answer]
            else:
                ans=answer
            self.buffer.append_line("Your answer is %r (%r)" % (answer,ans))
        self.buffer.update()
        self.ask_next_question()

    def abort_handler(self,arg):
        self.buffer.append_line("You have aborted the question")
        self.buffer.update()
        self.ask_next_question()

class Plugin(PluginBase):
    tests={
        "scroll": ScrollTest,
        "wrap": WrapTest,
        "input": InputTest
        }
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        ui.activate_cmdtable("test",self)

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

ui.CommandTable("test",51,(
    ui.Command("test",Plugin.cmd_test,
        "/test [scroll|wrap]",
        "Various tests of CJC engine."),
    )).install()
# vi: sts=4 et sw=4
