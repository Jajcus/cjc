
from types import StringType,IntType,UnicodeType
import re
import curses

from cjc import common

quoted_arg_re=re.compile(r'^"(?P<arg>.*?)(?<!\\)"(?P<rest>.*)$',re.UNICODE)
need_quote_re=re.compile(r'[ \"\\\n\t]',re.UNICODE)
quote_re=re.compile(r'\\(.)',re.UNICODE)

def quote(s):
    s=s.replace(u'\\',u'\\\\')
    s=s.replace(u'"',u'\\"')
    s=s.replace(u'\t',u'\\t')
    s=s.replace(u'\n',u'\\n')
    return s

def unquote(s):
    s=s.replace(u'\\t',u'\t')
    s=s.replace(u'\\n',u'\n')
    s=quote_re.sub(ur"\1",s)
    return s

class CommandError(ValueError):
    pass

class Command:
    def __init__(self,name,handler,usage,descr,hints=None):
        self.name=name
        self.handler=handler
        self.usage=usage
        self.descr=descr
        self.hints=hints
    def run(self,object,args):
        try:
            return self.handler(object,args)
        except common.non_errors:
            raise
        except CommandError,e:
            common.error(u"%s: %s" % (self.name,e))
        except:
            common.print_exception()

class CommandAlias:
    def __init__(self,name,cmd):
        self.name=name
        self.cmd=cmd

class CommandTable:
    def __init__(self,name,priority,commands):
        self.name=name
        self.priority=priority
        self.commands={}
        for c in commands:
            if isinstance(c,CommandAlias):
                self.commands[c.name]=self.commands[c.cmd]
            else:
                self.commands[c.name]=c
        self.object=None
        self.active=0

    def __repr__(self):
        if self.active:
            act="active "
        else:
            act=""
        return "<CommandTable %r %sprio=%r>" % (self.name,act,self.priority)

    def has_command(self,cmd):
        return self.commands.has_key(cmd)

    def lookup_command(self,cmd):
        return self.commands[cmd]

    def run_command(self,cmd,args):
        return self.commands[cmd].run(self.object,args)

    def get_commands(self):
        l=self.commands.items()
        l.sort()
        return [i[1] for i in l if isinstance(i[1],Command) and i[0]==i[1].name]

    def get_command_names(self):
        l=self.commands.keys()
        l.sort()
        return l

    def install(self):
        install(self)

command_tables=[]
def install(command_table):
    pos=len(command_tables)
    for i in range(0,len(command_tables)):
        if command_table.priority>command_tables[i].priority:
            pos=i
            break
    command_tables.insert(pos,command_table)

def uninstall(name):
    try:
        table=lookup_table(name)
    except KeyError:
        return
    table.active=0
    table.object=None
    if table:
        try:
            command_tables.remove(table)
        except ValueError:
            pass

def lookup_table(name):
    for t in command_tables:
        if t.name==name:
            return t
    raise KeyError,name

def activate(name,object):
    table=lookup_table(name)
    table.active=1
    table.object=object

def deactivate(name,object=None):
    try:
        table=lookup_table(name)
    except KeyError:
        return
    if object and table.object!=object:
        return
    table.active=0
    table.object=None

def lookup_command(name,active_only=0):
    for ctb in command_tables:
        if active_only and not ctb.active:
            continue
        try:
            return ctb.lookup_command(name)
        except KeyError:
            pass
    raise KeyError,name

def run_command(cmd,args=None):
    if args is None:
        args=CommandArgs(cmd)
        cmd=args.shift()
    cmd=cmd.lower()
    for t in command_tables:
        if not t.active:
            continue
        try:
            return t.run_command(cmd,args)
        except KeyError:
            continue
    if default_handler:
        return default_handler(cmd,args)
    common.error("Unknown command: /"+cmd)
    try:
        curses.beep()
    except curses.error:
        pass

default_handler=None
def set_default_handler(handler):
    global default_handler
    default_handler=handler

class CommandArgs:
    def __init__(self,args=None):
        if isinstance(args,CommandArgs):
            self.args=args.args
        else:
            self.args=args

    def all(self):
        args=self.args
        self.args=""
        return args

    def finish(self):
        if self.args:
            self.args=self.args.strip()
        if self.args:
            raise CommandError,"Too many arguments"

    def get(self,remove=0):
        if not self.args:
            return None
        args=self.args.lstrip()
        if not args:
            return None
        if not args.startswith('"'):
            sp=self.args.split(None,1)
            if remove:
                if len(sp)>1:
                    self.args=sp[1]
                else:
                    self.args=None
            return sp[0]
        m=quoted_arg_re.match(args)
        if not m:
            raise CommandError,"Command arguments syntax error"
        arg=unquote(m.group("arg"))
        if remove:
            self.args=m.group("rest").lstrip()
        return arg

    def shift(self):
        return self.get(1)

    def add_quoted(self,s):
        if not self.args:
            self.args=""
        else:
            self.args+=" "
        if need_quote_re.search(s) or not s:
            self.args+='"%s"' % (quote(s),)
        else:
            self.args+=s

    def add_unquoted(self,s):
        if not self.args:
            self.args=""
        else:
            self.args+=" "
        self.args+=s
# vi: sts=4 et sw=4
