import sys
import traceback
import libxml2

non_errors=KeyboardInterrupt,SystemExit,StopIteration

def debug(s):
    print >>sys.stderr,"DEBUG:",s

def error(s):
    print >>sys.stderr,"ERROR:",s

def print_exception():
    traceback.print_exc(file=sys.stderr)

# vi: sts=4 et sw=4
