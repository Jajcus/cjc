import sys
import traceback

def debug(s):
	print >>sys.stderr,"DEBUG:",s
		
def error(s):
	print >>sys.stderr,"ERROR:",s
		
def print_exception():
	traceback.print_exc(file=sys.stderr)
	
