import sys
import traceback
import curses,socket
import libxml2

standard_errors=StandardError,curses.error,socket.error,libxml2.treeError

def debug(s):
	print >>sys.stderr,"DEBUG:",s
		
def error(s):
	print >>sys.stderr,"ERROR:",s
		
def print_exception():
	traceback.print_exc(file=sys.stderr)
	
