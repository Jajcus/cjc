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

import curses
import re
import datetime
from types import UnicodeType,StringType,ListType
import version
import os
import locale
import logging

import pyxmpp

from cjc.ui import CommandError,CommandArgs
from cjc import ui
from cjc import common

attr_sel_re=re.compile(r"(?<!\%)\%\[([^]]*)\]",re.UNICODE)
formatted_re=re.compile(r"(?<!\%)\%\{([^}]*)\}",re.UNICODE)
case_re=re.compile(r"(?<!\\)\:",re.UNICODE)
param_re=re.compile(r"(?<!\\)\,",re.UNICODE)

attributes_by_name={}
colors_by_val={}
colors_by_name={}

for att in dir(curses):
    if att.startswith("COLOR_"):
        name=att[6:].lower()
        colors_by_name[name]=getattr(curses,att)
        colors_by_val[getattr(curses,att)]=name
    elif att.startswith("A_"):
        name=att[2:].lower()
        attributes_by_name[name]=getattr(curses,att)

def name2attr(name):
    attr=0
    name.replace("|","+")
    for a in name.split("+"):
        attr|=attributes_by_name[a.lower()]
    return attr

def attr2name(attr):
    names=[]
    for name,val in attributes_by_name.items():
        if not val:
            continue
        if attr&val==val:
            attr-=val
            names.append(name)
    if not names:
        return "normal"
    return "+".join(names)

def name2color(name):
    if name=="none":
        return None
    if (name == "default" and hasattr(curses, "use_default_colors")):
        return -1
    return colors_by_name[name.lower()]

def color2name(color):
    if color is None:
        return "none"
    if (color == -1 and hasattr(curses, "use_default_colors")):
        return "default"
    return colors_by_val[color]

class ThemeManager:
    def __init__(self,app):
        self.attrs={}
        self.attr_defs={}
        self.formats={}
        self.pairs={}
        self.next_pair=1
        self.app=app
        lc,self.encoding=locale.getlocale()
        if self.encoding is None:
            self.encoding="us-ascii"
        if hasattr(curses, "use_default_colors"):
            curses.use_default_colors()
        self.__logger=logging.getLogger("cjc.ThemeManager")

    def load(self,filename=None):
        if not filename:
            filename=self.app.theme_file
        if not os.path.split(filename)[0]:
            fn=os.path.join(self.app.home_dir,"themes",filename)
            if os.path.exists(fn):
                filename=fn
            else:
                filename=os.path.join(self.app.home_dir,"themes",filename)
        f=open(filename,"r")
        for l in f.xreadlines():
            command=CommandArgs(unicode(l,"utf-8").strip())
            self.command(command,1)
        f.close()
        if self.app and self.app.screen:
            self.app.screen.redraw()

    def save(self,filename=None):
        if not filename:
            filename=self.app.theme_file
        if not os.path.split(filename)[0]:
            theme_dir=os.path.join(self.app.home_dir,"themes")
            if not os.path.exists(theme_dir):
                os.makedirs(theme_dir)
            filename=os.path.join(theme_dir,filename)
        f=open(filename,"w")
        attr_names=self.attr_defs.keys()
        attr_names1=[n for n in attr_names if "." not in n]
        attr_names2=[n for n in attr_names if "." in n]
        attr_names1.sort()
        attr_names2.sort()
        for name in attr_names1+attr_names2:
            (fg,bg,attr,fallback)=self.attr_defs[name]
            cmd=CommandArgs(u"attr")
            cmd.add_quoted(name)
            if attr is None:
                cmd.add_quoted(u"empty")
            else:
                cmd.add_quoted(color2name(fg))
                cmd.add_quoted(color2name(bg))
                cmd.add_quoted(attr2name(attr))
                cmd.add_quoted(attr2name(fallback))
            print >>f,cmd.all()
        format_names=self.formats.keys()
        format_names1=[n for n in format_names if "." not in n]
        format_names2=[n for n in format_names if "." in n]
        format_names1.sort()
        format_names2.sort()
        for name in format_names1+format_names2:
            format=self.formats[name]
            cmd=CommandArgs(u"format")
            cmd.add_quoted(name)
            cmd.add_quoted(format)
            print >>f,cmd.all().encode("utf-8")
        f.close()

    def command(self,args,safe=0):
        cmd=args.shift()
        if cmd==u"save" and not safe:
            filename=args.shift()
            args.finish()
            self.save(filename)
            return
        if cmd==u"load" and not safe:
            filename=args.shift()
            args.finish()
            self.load(filename)
            return
        if cmd==u"attr":
            name=args.shift()
            arg1=args.shift()
            if arg1==u"empty":
                fg,bg,attr,fallback=(None,)*4
            else:
                try:
                    fg=name2color(arg1)
                    bg=name2color(args.shift())
                except KeyError,e:
                    common.error(u"Unknown color name: %s" % (e,))
                    return
                if None in (fg,bg) and fg!=bg:
                    common.error(u"Both foreground and background colors must be 'none' or none of them." % (e,))
                    return
                try:
                    attr=name2attr(args.shift())
                    fallback=name2attr(args.shift())
                except KeyError,e:
                    common.error(u"Unknown attribute name: %s" % (e,))
                    return
            args.finish()
            self.set_attr(name,fg,bg,attr,fallback)
        if cmd==u"format":
            name=args.shift()
            format=args.shift()
            args.finish()
            self.set_format(name,format)

    def set_attr(self,name,fg,bg,attr,fallback):
        if attr is None:
            self.attrs[name]=None
            self.attr_defs[name]=(None,)*4
            return
        if not curses.has_colors():
            self.attrs[name]=fallback
            self.attr_defs[name]=(fg,bg,attr,fallback)
            return
        if fg is None:
            self.attrs[name]=attr
            self.attr_defs[name]=(fg,bg,attr,fallback)
            return
        self.__logger.debug("for attr %r need pair: (%r,%r)",name,fg,bg)
        if self.pairs.has_key((fg,bg)):
            pair=self.pairs[fg,bg]
            self.__logger.debug("already got it: %r",pair)
        elif self.next_pair>=curses.COLOR_PAIRS:
            self.attrs[name]=fallback
            self.__logger.debug("too many color pairs used, falling back to:"
                    " %r",fallback)
            self.attr_defs[name]=(fg,bg,attr,fallback)
            return
        else:
            self.__logger.debug("creating new pair #%i...",self.next_pair)
            curses.init_pair(self.next_pair,fg,bg)
            pair=self.next_pair
            self.pairs[fg,bg]=pair
            self.next_pair+=1
        attr|=curses.color_pair(pair)
        self.attrs[name]=attr
        self.attr_defs[name]=(fg,bg,attr,fallback)

    def set_default_attr(self,name,fg,bg,attr,fallback):
        if not self.attrs.has_key(name):
            self.set_attr(name,fg,bg,attr,fallback)

    def set_default_attrs(self,attrs):
        for name,fg,bg,attr,fallback in attrs:
            self.set_default_attr(name,fg,bg,attr,fallback)

    def set_format(self,name,format):
        self.formats[name]=format

    def set_default_format(self,name,format):
        if not self.formats.has_key(name):
            self.formats[name]=format

    def set_default_formats(self,formats):
        for name,format in formats:
            if not self.formats.has_key(name):
                self.formats[name]=format

    def format_buffers(self,attr,params):
        ret=[]
        for num in range(0,len(ui.buffer.buffer_list)):
            buf=ui.buffer.buffer_list[num]
            if buf is None:
                continue
            p=params.copy()
            p.update(buf.info)
            if buf.window:
                format="buffer_visible"
            elif buf.preference==0:
                format="buffer_inactive"
            elif buf.active==1:
                format="buffer_active1"
            elif buf.active==2:
                format="buffer_active2"
            elif buf.active>2:
                format="buffer_active3"
            else:
                format="buffer_inactive"
            format=self.formats.get(format)
            if not format:
                continue
            f_buf=self.do_format_string(format,attr,p)
            if ret:
                ret.append((self.attrs.get(attr,self.attrs["default"]),","))
            ret+=f_buf
        return ret

    def format_string(self,fname,params):
        format=self.formats[fname]
        return self.do_format_string(format,"default",params)

    def do_format_string(self,format,attr,params):
        if type(params) in (UnicodeType,StringType):
            params={u"msg":params}
        else:
            params=params.copy()
        l=attr_sel_re.split(format,1)
        if len(l)==3:
            format=l[0]
            next_attr=l[1]
            if "%" in next_attr:
                next_attr=self.substitute(next_attr,params)
            next=l[2]
        else:
            next=None

        l=formatted_re.split(format,1)
        if len(l)==3:
            before,name,after=l
            if name.startswith(u"@"):
                val=name[1:]
            elif params.has_key(name):
                val=params[name]
            else:
                val=self.find_format_param(name,params)
            if val is not None:
                ret=[]
                if before:
                    ret+=self.do_format_string(before,attr,params)
                if callable(val):
                    ret+=val(attr,params)
                elif type(val) is ListType:
                    ret+=val
                elif self.formats.has_key(val):
                    f=self.formats[val]
                    ret+=self.do_format_string(f,attr,params)
                else:
                    format=u"%s%%%%{%s}%s" % (before,name,after)
                    ret+=self.do_format_string(format,attr,params)
                    before=None
                    after=None
                if after:
                    ret+=self.do_format_string(after,attr,params)
                if next:
                    ret+=self.do_format_string(next,next_attr,params)
                return ret
            else:
                format=u"%s%%%%{%s}%s" % (before,name,after)
                return self.do_format_string(format,attr,params)

        s=self.substitute(format,params)

        if self.attrs.has_key(attr):
            attr=self.attrs[attr]
        else:
            attr=self.attrs["default"]

        ret=[]
        if s:
            ret.append((attr,s))
        if next:
            ret+=self.do_format_string(next,next_attr,params)
        return ret

    def substitute(self,format,params):
        while 1:
            try:
                s=format % params
                break
            except (ValueError,TypeError),e:
                s=u"[%s: %r, %r]" % (unicode(e),format,params)
                break
            except KeyError,key:
                key=key.args[0]
                if "?" in key:
                    format=self.process_format_cond(format,key,params)
                elif ":" in key:
                    format=self.process_format_param(format,key,params)
                else:
                    val=self.find_format_param(key,params)
                    if not val:
                        format=self.quote_format_param(format,key)
        return s

    def quote_format_param(self,format,key):
        return format.replace(u"%%(%s)" % (key,),u"%%%%(%s)" % (key,))

    def find_format_param(self,key,params):
        if key.startswith(u"$"):
            if os.environ.has_key(key[1:]):
                val=os.environ[key[1:]]
            else:
                return None
        elif key in (u"now",u"timestamp"):
            val=datetime.datetime.now()
        elif key in (u"me",u"jid"):
            if self.app.stream:
                val=self.app.jid
            else:
                val=self.app.settings["jid"]
        elif key==u"buffers":
            val=self.format_buffers
        elif key==u"program_name":
            val=u"CJC"
        elif key==u"program_author":
            val=u"Jacek Konieczny <jajcus@jajcus.net>"
        elif key==u"program_version":
            val=version.version
        else:
            return None
        params[key]=val
        return val

    def process_format_cond(self,format,key,params):
        sp=key.split(u"?",1)
        val,expr=sp
        if not params.has_key(val) and u":" in val:
            val=self.process_format_param(format,val,params)
        if not params.has_key(val):
            return self.quote_format_param(format,key)
        value=params[val]
        options=param_re.split(expr)
        if not case_re.search(options[0]):
            # yes/no choice
            if value:
                params[key]=self.substitute(options[0].replace("\\:",":"),params)
            else:
                if len(options)>1:
                    params[key]=self.substitute(options[1].replace("\\:",":"),params)
                else:
                    params[key]=u""
            return format
        # case-like choice
        retval=u""
        for opt in options:
            if not case_re.search(opt):
                retval=opt.replace("\\:",":")
                break
            test,val=case_re.split(opt,1)
            test=test.replace("\\:",":")
            if value==test:
                retval=val.replace("\\:",":")
                break
        if retval:
            retval=self.substitute(retval,params)
        params[key]=retval
        return format

    def process_format_param(self,format,key,params):
        sp=key.split(u":",2)
        if len(sp)==2:
            typ,param=sp
            form=None
        else:
            typ,param,form=sp
        if params.has_key(param):
            val=params[param]
        else:
            val=self.find_format_param(param,params)
            if val is None:
                return self.quote_format_param(format,key)

        if typ==u"T":
            if form:
                form=form.encode(self.encoding,"replace")
                formatted=val.strftime(form)
            else:
                formatted=val.strftime("%H:%M")
            params[key]=unicode(formatted,self.encoding,"replace")
            return format
        elif typ==u"J":
            if not isinstance(val,pyxmpp.JID):
                try:
                    val=pyxmpp.JID(val)
                except pyxmpp.JIDError:
                    params[key]=u""
                    return format
            if form == u"nick":
                nick =  self.app.get_user_info(val, "nick")
                if not nick:
                    nick = self.app.get_user_info(val,"rostername")
                if nick:
                    params[key] = nick
                else:
                    params[key] = val.node
            elif form==u"node":
                params[key]=val.node
            elif form==u"domain":
                params[key]=val.domain
            elif form==u"resource":
                params[key]=val.resource
            elif form==u"bare":
                params[key]=val.bare().as_unicode()
            elif form in (u"show",u"status"):
                pr=self.app.get_user_info(val,"presence")
                if form==u"show":
                    if pr is None or pr.get_type()=="unavailable":
                        val=u"offline"
                    elif pr.get_type()=="error":
                        val=u"error"
                    else:
                        val=pr.get_show()
                        if not val or val=="":
                            val=u"online"
                elif form==u"status":
                    if pr is None:
                        val=""
                    elif pr.get_type()==u"error":
                        err=pr.get_error()
                        val=err.get_message()
                    else:
                        val=pr.get_status()
                        if val is None:
                            val=""
                params[key]=val
            elif form in (u"full",None):
                params[key]=val.as_unicode()
            else:
                ival=self.app.get_user_info(val,form)
                if not ival:
                    val=u""
                elif ival not in (StringType,UnicodeType):
                    if self.app.info_handlers.has_key(form):
                        val=self.app.info_handlers[form](form,ival)[1]
                    else:
                        val=unicode(ival)
                params[key]=val
            return format
        else:
            return self.quote_format_param(format,key)
# vi: sts=4 et sw=4
