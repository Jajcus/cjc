
import threading
import sys
import time

oRLock=threading.RLock

def log(info):
	frame=sys._getframe(2)
	code=frame.f_code
	filename=code.co_filename
	lineno=frame.f_lineno
	tname=threading.currentThread().getName()
	timestamp=time.strftime("%H:%M:%S",time.localtime())
	print >>sys.stderr,"[%s] %s:%s:%i: %s" % (timestamp,tname,filename,lineno,info)

class RLock:
	def __init__(self):
		log("RLock()")
		self.lock=oRLock()
	def __del__(self):
		del self.lock
	def acquire(self,blocking=1):
		log("RLock.acquire(%r)" % (blocking,))
		self.lock.acquire(blocking)
	def release(self):
		log("RLock.release()")
		self.lock.release()

threading.RLock=RLock
	
oCondition=threading.Condition

class Condition:
	def __init__(self,*args):
		log("Condition%r" % (args,))
		self.condition=apply(oCondition,args)
	def __del__(self):
		del self.condition
	def acquire(self,*args):
		log("Condition.acquire%r" % (args,))
		apply(self.condition.acquire,args)
	def release(self):
		log("Condition.release()")
		self.condition.release()
	def wait(self,*args):
		log("Condition.wait%r" % (args,))
		apply(self.condition.wait,args)
	def notify(self):
		log("Condition.notify()")
		self.condition.notify()
	def notifyAll(self):
		log("Condition.notifyAll()")
		self.condition.notifyAll()

threading.Condition=Condition
