#!/usr/bin/python

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

if len(sys.argv)>1 and sys.argv[1]=="--profile":
    sys.argv[1:]=sys.argv[2:]
    import profile
    profile.run("main.main(base_dir,profile=True)","cjc.prof")
else:
    main.main(base_dir)

# vi: sts=4 et sw=4
