
import re
import curses
import logging

from cjc import common
from types import StringType,UnicodeType

__logger=logging.getLogger("cjc.ui.keytable")

class KeytableError(StandardError):
    pass

fun_re=re.compile(r"^([a-z-]+)(\((([^)]|(\\\)))*)\))?$")

class KeyBinding:
    def __init__(self,fun,keys):
        m=fun_re.match(fun)
        if not m:
            raise KeytableError,"Bad key function syntax: "+`fun`
        self.fun=m.group(1)
        self.arg=m.group(3)
        if keys is None:
            self.keys=None
        elif type(keys) in (StringType,UnicodeType):
            self.keys=[keyname_to_code(keys)]
        else:
            self.keys=[keyname_to_code(k) for k in keys]

class KeyFunction:
    def __init__(self,name,handler,descr,default_keys=None):
        m=fun_re.match(name)
        if not m:
            raise KeytableError,"Bad key function syntax: "+`name`
        arg=m.group(3)
        if arg is not None:
            if arg:
                raise KeytableError,"Cannot use arguments in KeyFunction"
            elif default_keys:
                raise KeytableError,"Cannot assign default keybindings for function with arguments"
            self.accepts_arg=1
        else:
            self.accepts_arg=0
        if default_keys:
            self.default_binding=KeyBinding(name,default_keys)
        else:
            self.default_binding=None
        self.name=m.group(1)
        self.handler=handler
        self.descr=descr

    def __repr__(self):
        return "<KeyFunction %r>" % (self.name,)

    def invoke(self,object,arg=None):
        if self.accepts_arg and arg is None:
            raise KeytableError,"%s requires argument" % (self.name,)
        if self.accepts_arg:
            self.handler(object,arg)
        else:
            self.handler(object)

class KeyTable:
    def __init__(self,name,prio,content):
        self.name=name
        self.prio=prio
        self.orig_keytable={}
        self.funtable={}
        for x in content:
            if isinstance(x,KeyBinding):
                binding=x
                try:
                    fun=self.lookup_function(binding.fun)
                except KeyError:
                    try:
                        fun,obj=lookup_function(binding.fun)
                    except KeyError:
                        fun=binding.fun
            elif isinstance(x,KeyFunction):
                binding=x.default_binding
                fun=x
                self.funtable[fun.name]=fun
            else:
                raise "%r is not a KeyBinding nor a KeyFunction" % (x,)
            if binding:
                for k in binding.keys:
                    self.orig_keytable[k]=(fun,binding.arg)
        self.keytable=dict(self.orig_keytable)
        self.object=None
        self.active=0
        self.default_handler=None
        self.input_window=None

    def __repr__(self):
        if self.active:
            act="active "
        else:
            act=""
        return "<KeyTable %r %sprio=%r>" % (self.name,act,self.prio)

    def has_key(self,c,meta):
        return self.keytable.has_key((c,meta))

    def lookup_key(self,c,meta):
        return self.keytable[(c,meta)]

    def process_key(self,c,meta):
        object=None
        fun,arg=self.keytable[(c,meta)]
        if not isinstance(fun,KeyFunction):
            try:
                fun=self.lookup_function(fun)
            except KeyError:
                fun,object=lookup_function(fun,1)
        if object is None:
            object=self.object
        fun.invoke(object,arg)

    def has_function(self,name):
        return self.funtable.has_key(name)

    def lookup_function(self,name):
        return self.funtable[name]

    def get_bindings(self,only_new=0):
        ret=[]
        for (c,meta),(fun,arg) in self.keytable.items():
            if not isinstance(fun,KeyFunction):
                try:
                    fun=self.lookup_function(fun)
                except KeyError:
                    fun,obj=lookup_function(fun)
            if only_new and self.orig_keytable.has_key((c,meta)):
                # function name from original keybindings may
                # have not be resolved yet
                ofun,arg=self.orig_keytable[c,meta]
                if isinstance(ofun,KeyFunction):
                    if (ofun,arg)==(fun,arg):
                        continue
                elif (ofun,arg)==(fun.name,arg):
                    continue
            keyname=keycode_to_name(c,meta)
            if fun.accepts_arg:
                if arg:
                    funame="%s(%s)"  % (fun.name,arg)
                else:
                    funame="%s()"  % (fun.name,)
            else:
                funame=fun.name
            descr=fun.descr
            if descr and arg is not None:
                descr=descr.replace("<arg>",arg)
            ret.append((keyname,funame,descr))
        ret.sort()
        return ret

    def get_changed_bindings(self):
        ret=self.get_bindings(1)
        for (c,meta) in self.orig_keytable.keys():
            if not self.keytable.has_key((c,meta)):
                ret.append((keycode_to_name(c,meta),None,None))
        return ret

    def get_unbound_functions(self):
        kl=self.funtable.keys()
        kl.sort()
        ret=[self.funtable[k] for k in kl]
        for f,arg in self.keytable.values():
            if f in ret:
                ret.remove(f)
        return ret

    def bind(self,binding):
        try:
            fun=self.lookup_function(binding.fun)
        except KeyError:
            try:
                fun=lookup_function(binding.fun)
            except KeyError:
                fun=binding.fun
        for k in binding.keys:
            self.keytable[k]=(fun,binding.arg)

    def unbind(self,keyname):
        (c,meta)=keyname_to_code(keyname)
        try:
            del self.keytable[c,meta]
        except KeyError:
            pass

    def install(self):
        install(self)

def keyname_to_code(name):
    if name.startswith("M-") or name.startswith("m-") or name.startswith("^["):
        meta=1
        name=name[2:]
    else:
        meta=0
    if hasattr(curses,"KEY_"+name.upper()):
        return getattr(curses,"KEY_"+name.upper()),meta
    if hasattr(curses,"key_"+name.lower()):
        return getattr(curses,"key_"+name.lower()),meta
    if name.upper()=="SPACE":
        return 32,meta
    if name.upper()=="ESCAPE":
        return 27,meta
    if len(name)==2 and name[0]=="^":
        if name[1]=="?":
            return 0x7f,meta
        c=ord(name[1].upper())
        if c<64 or c>95:
            raise KeytableError,"Bad key name: "+`name`
        return c-64,meta
    if name.startswith("\\"):
        if len(name)==2:
            name=name[1]
        elif len(name)==4:
            name=chr(int(name[1:],8))
        else:
            raise KeytableError,"Bad key name: "+`name`
    if len(name)!=1:
        raise KeytableError,"Bad key name: "+`name`
    return ord(name[0]),meta

def keycode_to_name(code,meta):
    if code>=256:
        name=curses.keyname(code)
        if name.startswith("KEY_"):
            name=name[4:]
        if name.startswith("key_"):
            name=name[4:].upper()
        if name.startswith("F("):
            name="F"+name[2:-1]
    elif code>=128:
        name="\\%03o" % (code,)
    elif code==27:
        name="ESCAPE"
    elif code==32:
        name="SPACE"
    else:
        name=curses.keyname(code)
    if meta:
        return "M-"+name
    else:
        return name

keytables=[]
active_input_window=None

def install(keytable):
    pos=len(keytables)
    for i in range(0,len(keytables)):
        if keytable.prio>keytables[i].prio:
            pos=i
            break
    keytables.insert(pos,keytable)

def lookup_table(name):
    for t in keytables:
        if t.name==name:
            return t
    raise KeyError,name

def find_active_input_window():
    global active_input_window
    active_input_window=None
    for t in keytables:
        if t.input_window:
            active_input_window=t.input_window
            return

def activate(name,object,default_handler=None,input_window=None):
    table=lookup_table(name)
    table.active=1
    table.object=object
    table.default_handler=default_handler
    table.input_window=input_window
    find_active_input_window()

def deactivate(name,object=None):
    table=lookup_table(name)
    if object and table.object!=object:
        return
    table.active=0
    table.object=None
    table.default_handler=None
    table.input_window=None

def lookup_function(name,active_only=0):
    for ktb in keytables:
        if active_only and not ktb.active:
            continue
        try:
            return ktb.lookup_function(name),ktb.object
        except KeyError:
            pass
    raise KeyError,name

meta=0

def process_key(code):
    default_handler=None
    for t in keytables:
        if not t.active:
            continue
        if not default_handler and t.default_handler:
            default_handler=t.default_handler
        try:
            return t.process_key(code,meta)
        except KeyError:
            continue
    if default_handler:
        return default_handler(code,meta)
    else:
        try:
            logging.getLogger("cjc.ui.keytable").debug("Unhandled key: "+keycode_to_name(code,meta))
            curses.beep()
        except curses.error:
            pass
        return 0

def keypressed():
    global meta
    if not active_input_window:
        raise KeytableError,"No input window set"
    ch=active_input_window.getch()
    if ch==-1:
        return 0
    if ch==27:
        if meta:
            meta=0
            try:
                process_key(27)
            except common.non_errors:
                raise
            except:
                __logger.exception("Exception during keybinding execution")
            return 1
        else:
            meta=1
            return 1
    try:
        process_key(ch)
    except common.non_errors:
        raise
    except:
        __logger.exception("Exception during keybinding execution")
    meta=0
    return 1

def bind(keyname,fun,table=None):
    binding=KeyBinding(fun,keyname)
    if table:
        table=lookup_table(table)
        return table.bind(binding)
    for t in keytables:
        if t.has_function(binding.fun):
            t.bind(binding)

def unbind(keyname,table=None):
    if table:
        table=lookup_table(table)
        return table.unbind(keyname)
    for t in keytables:
        t.unbind(keyname)

# vi: sts=4 et sw=4
