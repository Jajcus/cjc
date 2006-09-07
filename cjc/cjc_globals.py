# Console Jabber Client
# Copyright (C) 2004-2006  Jacek Konieczny
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

"""
References to CJC global objects (singletons).

Usage::

    from cjc import cjc_globals

Never use::

    from cjc.cjc_globals import anything

as module contents may be uninitialized.

:Variables:
    - `application`: the `cjc.main.Application` object
    - `screen`: the `ui.screen.Screen` object
    - `theme_manager`: the `cjc.theme_manage.ThemeManager` object
"""

application = None
screen = None
theme_manager = None

# vi: sts=4 et sw=4
