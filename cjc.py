#!/usr/bin/python

"""Startup script for running CJC directly from the "source" tree."""

#try:
#   import psyco
#   psyco.profile()
#except ImportError:
#   pass

import sys
import os
import glob

base_dir=sys.path[0]

l=glob.glob(os.path.join(base_dir,"../pyxmpp*"))
for p in l:
    if os.path.exists(os.path.join(p,"pyxmpp/__init__.py")):
        print >>sys.stderr,"PyXMPP sources found in:", p
        l=glob.glob(os.path.join(p,"build/lib*"))
        if l:
            sys.path+=l
        else:
            print >>sys.stderr,"Not compiled, skipping",

if os.path.exists(os.path.join(base_dir,"CVS/Entries")):
    print >>sys.stderr,"Running from CVS, updating version"
    try:
        cwd=os.getcwd()
        try:
            os.chdir(base_dir)
            if os.system("make version >&2"):
                raise OSError,"make failed"
        finally:
            os.chdir(cwd)
    except (OSError,IOError):
        print >>sys.stderr,"failed"
        try:
            p=os.path.join(base_dir,"cjc/version.py")
            f=file(p,"w")
            print >>f,"version='unknown CVS'"
            f.close()
        except (OSError,IOError):
            pass

from cjc import main
main.main(base_dir)
# vi: sts=4 et sw=4
