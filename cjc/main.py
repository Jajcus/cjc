#!/usr/bin/python -u

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

import libxml2
import time
import traceback
import sys,os
import string
from types import StringType,UnicodeType,IntType,ListType,TupleType,TypeType
import locale
import curses
import threading
import socket
import signal
import getopt
import datetime
import logging

import pyxmpp
from pyxmpp import jabber

from cjc import cjclogging
from cjc import ui
from cjc.ui import buffer as ui_buffer
from cjc.ui import keytable as ui_keytable
from cjc.ui import cmdtable as ui_cmdtable
from cjc import version
from cjc import themes
from cjc import common
from cjc import tls
from cjc import completions

class Exit(Exception):
    pass


global_settings={
    "jid": ("Jabber ID to use.",pyxmpp.JID),
    "password": ("Jabber ID to use.",unicode),
    "port": ("Port number to connect to",int),
    "server": ("Server address to connect to",str),
    "tls_enable": ("Enable TLS (encrypted) connections",bool),
    "tls_require": ("Require TLS (encrypted) connections",bool),
    "tls_cert_file": ("Path to user certificate file",(str,None)),
    "tls_key_file": ("Path to user private key file (default: same to tls_cert_file)",(str,None)),
    "tls_ca_cert_file": ("Path to CA certificates file",(str,None)),
    "auth_methods": ("Authentication methods to use (e.g. 'sasl:DIGEST-MD5,digest')",list),
    "layout": ("Screen layout - one of: plain,icr,irc,vertical,horizontal",str,"set_layout"),
    "status_buffer_preference": ("Preference of status buffer when switching to the next active buffer. If 0 then the buffer is not even shown in active buffer list.",int),
    "disconnect_timeout": ("Time (in seconds) to wait until the connection is closed before exit",float),
    "disconnect_delay": ("Delay (in seconds) before stream is disconnected after final packets are written - needed for some servers to accept disconnect reason.",float),
    "autoconnect": ("Automatically connect on startup.",bool),
    "keepalive": ("Keep-alive interval in seconds (0 to disable).",bool),
    "case_sensitive": ("Should roster name matches be case sensitive?",bool),
    "backup_config": ("Save backup of previous config file when saving.",bool),
    "debug": ("Display some debuging information in status window.",bool,"set_debug"),
}

global_theme_attrs=(
    ("default", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
    ("error", curses.COLOR_RED,curses.COLOR_BLACK,curses.A_BOLD, curses.A_STANDOUT),
    ("warning", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_UNDERLINE),
    ("info", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
    ("debug", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_DIM),
    ("bar", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_STANDOUT, curses.A_STANDOUT),
    ("scroll_mark", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_BOLD, curses.A_BOLD),
)

global_theme_formats=(
    ("window_status",u"%[bar] %(active)s%(locked)s %(buffer_num)s: %{buffer_descr}"),
    ("default_buffer_descr",u"%(buffer_name)s"),
    ("title_bar",u"%[bar]%(program_name)s ver. %(program_version)s by %(program_author)s"),
    ("status_bar",u"%[bar][%(J:me:show)s] (%(J:me:status)s) Active buffers: [%{buffers}]"),
    ("error",u"%[error][%(T:now)s] %(msg)s\n"),
    ("warning",u"%[warning][%(T:now)s] %(msg)s\n"),
    ("info",u"%[info][%(T:now)s] %(msg)s\n"),
    ("debug",u"%[debug][%(T:now)s] %(msg)s\n"),
    ("day_change",u"%[warning][%(T:now:%c)s] And here comes a brand new day...\n"),
    ("buffer_visible",""),
    ("buffer_inactive",""),
    ("buffer_active1","%[default]%(buffer_num)i"),
    ("buffer_active2","%[warning]%(buffer_num)i"),
    ("buffer_list","[%(T:now)s] Buffers: \n%{buffers_on_list}"),
    ("buffer_on_list","[%(T:now)s] %(buffer_num)i. %{buffer_descr}\n"),
    ("keybindings","%[info]Current key bindings:\n%{tables}"),
    ("keytable","%[info] table %(name)s:\n%{bindings}%{unbound}"),
    ("keybinding","%[info]  %(key)-10s %(function)-20s %(description)s\n"),
    ("keyfunction","%[info]         %(function)-20s %(description)s\n"),
    ("certificate","  Subject: %(subject)s\n"
            "  Issuer: %(issuer)s\n"
            "  Serial number: %(serial_number)s\n"
            "  Valid not before: %(not_before)s\n"
            "  Valid not after: %(not_after)s\n"),
    ("certificate_error","%[warning]Server certificate failed verifiaction.\n\n"
        "%[info]Server has presented following certificate chain:\n"
        "%{chain}\n"
        "The rejected certificate is:\n"
        "%{certificate}\n"
        "%[error]Verification failed with error #%(errnum)i: %(errdesc)s\n"),
    ("certificate_remember","%[info]Server '%(who)s' has presented following certificate:\n\n"
        "%{certificate}\n"
        "Verification of that certificat failed.\n"
        "Should it be accepted in future sessions anyway?\n"),
    ("tls_error_ignored","%[info]Certificate verification error #%(errnum)i:"
            " '%(errdesc)s' ignored - peer certificate is known as trustworthy.\n"),
)


class Application(jabber.Client,tls.TLSHandler):
    def __init__(self,base_dir,config_file="default",theme_file="theme",home_dir=None,profile=False):
        self.profile=profile
        jabber.Client.__init__(self)
        self.__logger=logging.getLogger("cjc.Application")
        self.settings={
            "jid":self.jid,
            "password":self.password,
            "auth_methods":self.auth_methods,
            "layout":"plain",
            "disconnect_timeout":10.0,
            "disconnect_delay":0.25,
            "autoconnect":False,
            "tls_enable":True,
            "tls_require":False,
            "keepalive":15*60,
            "backup_config":False,
            "case_sensitive":True,
            "status_buffer_preference":1,
            "debug":False}
        self.aliases={}
        self.available_settings=global_settings
        self.base_dir=base_dir
        self.config_file=config_file
        self.theme_file=theme_file
        if home_dir:
            self.home_dir=home_dir
        else:
            home=os.environ.get("HOME","")
            self.home_dir=os.path.join(home,".cjc")
        self.plugin_dirs=[os.path.join(base_dir,"plugins"),
                    os.path.join(self.home_dir,"plugins")]
        self.plugins={}
        self.plugin_modules={}
        self.event_handlers={}
        self.user_info={}
        self.info_handlers={}
        self.exiting=0
        self.ui_thread=None
        self.stream_thread=None
        self.roster_window=None
        self.status_window=None
        self.main_window=None
        self.top_bar=None
        self.bottom_bar=None
        self.resize_request=0
        self.disconnecting=0
        ui.activate_keytable("default",self)
        ui.activate_keytable("global",self)
        ui.activate_cmdtable("global",self)
        ui.set_default_command_handler(self.unknown_command)
        completions.SettingCompletion(self).register("setting")
        completions.UserCompletion(self).register("user")
        completions.CommandCompletion(self).register("command")

    def _load_plugin(self,name):
        try:
            mod=self.plugin_modules.get(name)
            if mod:
                mod=reload(mod)
            else:
                mod=__import__(name)
            plugin=mod.Plugin(self,name)
            plugin.module=mod
            plugin.sys_path=sys.path
            self.plugins[name]=plugin
            self.plugin_modules[name]=mod
        except:
            self.__logger.exception("Exception:")
            self.__logger.info("Plugin load failed")

    def load_plugin(self,name):
        sys_path=sys.path
        try:
            for path in self.plugin_dirs:
                sys.path=[path]+sys_path
                f=os.path.join(path,name+".py")
                if not os.path.exists(f):
                    continue
                if self.plugins.has_key(name):
                    self.__logger.error("Plugin %s already loaded!" % (name,))
                    return
                self.__logger.info("Loading plugin %s..." % (name,))
                self._load_plugin(name)
                return
            self.__logger.error("Couldn't find plugin %s" % (name,))
        finally:
            sys.path=sys_path

    def unload_plugin(self,name):
        try:
            plugin=self.plugins[name]
        except KeyError:
            self.__logger.error("Plugin %s is not loaded" % (name,))
            return False
        self.__logger.info("Unloading plugin %s..." % (name,))
        try:
            r=plugin.unload()
        except:
            self.__logger.exception("Exception:")
            r=None
        if not r:
            self.__logger.error("Plugin %s cannot be unloaded" % (name,))
            return False
        del self.plugins[name]
        return True

    def reload_plugin(self,name):
        try:
            plugin=self.plugins[name]
        except KeyError:
            self.__logger.error("Plugin %s is not loaded" % (name,))
            return False
        self.__logger.info("Reloading plugin %s..." % (name,))
        try:
            r=plugin.unload()
        except:
            self.__logger.exception("Exception:")
        if not r:
            self.__logger.error("Plugin %s cannot be reloaded" % (name,))
            return False
        sys_path=sys.path
        sys.path=plugin.sys_path
        try:
            mod=reload(plugin.module)
            plugin=mod.Plugin(self)
            plugin.module=mod
            self.plugins[name]=plugin
        except:
            self.__logger.exception("Exception:")
            self.__logger.info("Plugin load failed")
            del self.plugins[name]
        sys.path=sys_path

    def load_plugins(self):
        sys_path=sys.path
        try:
            for path in self.plugin_dirs:
                sys.path=[path]+sys_path
                try:
                    d=os.listdir(path)
                except (OSError,IOError),e:
                    self.__logger.debug("Couldn't get plugin list: %s" % (e,))
                    self.__logger.info("Skipping plugin directory %s" % (path,))
                    continue
                self.__logger.info("Loading plugins from %s:" % (path,))
                for f in d:
                    if f[0]=="." or not f.endswith(".py"):
                        continue
                    name=os.path.join(f[:-3])
                    if not self.plugins.has_key(name):
                        self.__logger.info("  %s" % (name,))
                        self._load_plugin(name)
        finally:
            sys.path=sys_path

    def get_plugin(self,name):
        return self.plugins[name]

    def add_event_handler(self,event,handler):
        self.lock.acquire()
        try:
            if not self.event_handlers.has_key(event):
                self.event_handlers[event]=[]
            if handler not in self.event_handlers[event]:
                self.event_handlers[event].append(handler)
        finally:
            self.lock.release()

    def remove_event_handler(self,event,handler):
        self.lock.acquire()
        try:
            if not self.event_handlers.has_key(event):
                return
            if handler not in self.event_handlers[event]:
                self.event_handlers[event].remove(handler)
        finally:
            self.lock.release()

    def send_event(self,event,arg=None):
        if event=="presence changed" and arg==self.jid:
            self.update_status_bars()
        if event=="day changed":
            self.status_buf.append_themed("day_change",{})
            self.status_buf.update(1)
        if self.event_handlers.has_key(event):
            for h in self.event_handlers[event]:
                try:
                    h(event,arg)
                except:
                    self.__logger.exception("Exception:")
                    self.__logger.info("Event handler failed")
        if not self.event_handlers.has_key("*"):
            return
        for h in self.event_handlers["*"]:
            try:
                h(event,arg)
            except:
                self.__logger.exception("Exception:")
                self.__logger.info("Event handler failed")

    def add_info_handler(self,var,handler):
        self.info_handlers[var]=handler

    def key_command(self,arg):
        args=ui.CommandArgs(arg)
        cmd=args.shift()
        ui.run_command(cmd,args)

    def unknown_command(self,cmd,args):
        if self.aliases.has_key(cmd):
            newcommand=self.aliases[cmd]
            if args.args:
                newcommand=newcommand.replace(u"$*",args.args)
                i=1
                while 1:
                    var=u"$%i" % (i,)
                    val=args.shift()
                    if val is None:
                        break
                    newcommand=newcommand.replace(var,val)
                    i+=1
            args=ui.CommandArgs(newcommand)
            cmd=args.shift()
        ui.set_default_command_handler(None)
        ui.run_command(cmd,args)
        ui.set_default_command_handler(self.unknown_command)

    def layout_plain(self):
        ui_buffer.activity_handlers=[]
        self.top_bar=ui.StatusBar(self.theme_manager,"title_bar",{})
        ui_buffer.activity_handlers.append(self.top_bar.update)
        self.main_window=ui.Window(self.theme_manager,"Main")
        self.command_line=ui.Input(self.theme_manager)
        self.bottom_bar=ui.StatusBar(self.theme_manager,"status_bar",{})
        ui_buffer.activity_handlers.append(self.bottom_bar.update)
        sp=ui.HorizontalSplit(self.top_bar,self.main_window,self.bottom_bar,self.command_line)
        self.screen.set_content(sp)
        self.screen.focus_window(self.main_window)
        self.status_window=None
        self.roster_window=None

    def layout_icr(self):
        ui_buffer.activity_handlers=[]
        self.top_bar=ui.StatusBar(self.theme_manager,"title_bar",{})
        ui_buffer.activity_handlers.append(self.top_bar.update)
        self.status_window=ui.Window(self.theme_manager,"Status",1)
        self.main_window=ui.Window(self.theme_manager,"Main")
        self.command_line=ui.Input(self.theme_manager)
        self.bottom_bar=ui.StatusBar(self.theme_manager,"status_bar",{})
        ui_buffer.activity_handlers.append(self.bottom_bar.update)
        self.roster_window=ui.Window(self.theme_manager,"Roster",1)

        sp=ui.VerticalSplit(self.main_window,self.roster_window)
        sp=ui.HorizontalSplit(self.top_bar,self.status_window,sp,self.bottom_bar,self.command_line)
        self.screen.set_content(sp)
        self.screen.focus_window(self.main_window)

    def layout_irc(self):
        ui_buffer.activity_handlers=[]
        self.top_bar=ui.StatusBar(self.theme_manager,"title_bar",{})
        ui_buffer.activity_handlers.append(self.top_bar.update)
        self.status_window=ui.Window(self.theme_manager,"Status",1)
        self.main_window=ui.Window(self.theme_manager,"Main")
        self.command_line=ui.Input(self.theme_manager)
        self.bottom_bar=ui.StatusBar(self.theme_manager,"status_bar",{})
        ui_buffer.activity_handlers.append(self.bottom_bar.update)
        self.roster_window=ui.Window(self.theme_manager,"Roster",1)

        sp=ui.VerticalSplit(self.status_window,self.roster_window)
        sp=ui.HorizontalSplit(self.top_bar,sp,self.main_window,self.bottom_bar,self.command_line)
        self.screen.set_content(sp)
        self.screen.focus_window(self.main_window)

    def layout_vertical(self):
        status_bar_params={
            "name": "CJC",
            "version": version.version,
            "author": "Jacek Konieczny <jajcus@bnet.pl>",
            }
        ui_buffer.activity_handlers=[]
        self.top_bar=ui.StatusBar(self.theme_manager,"title_bar",{})
        ui_buffer.activity_handlers.append(self.top_bar.update)
        self.main_window=ui.Window(self.theme_manager,"Main")
        self.command_line=ui.Input(self.theme_manager)
        self.bottom_bar=ui.StatusBar(self.theme_manager,"status_bar",{})
        ui_buffer.activity_handlers.append(self.bottom_bar.update)
        self.roster_window=ui.Window(self.theme_manager,"Roster",1)

        sp=ui.VerticalSplit(self.main_window,self.roster_window)
        sp=ui.HorizontalSplit(self.top_bar,sp,self.bottom_bar,self.command_line)
        self.screen.set_content(sp)
        self.screen.focus_window(self.main_window)
        self.status_window=None

    def layout_horizontal(self):
        ui_buffer.activity_handlers=[]
        self.top_bar=ui.StatusBar(self.theme_manager,"title_bar",{})
        ui_buffer.activity_handlers.append(self.top_bar.update)
        self.main_window=ui.Window(self.theme_manager,"Main")
        self.command_line=ui.Input(self.theme_manager)
        self.bottom_bar=ui.StatusBar(self.theme_manager,"status_bar",{})
        ui_buffer.activity_handlers.append(self.bottom_bar.update)
        self.roster_window=ui.Window(self.theme_manager,"Roster",1)
        sp=ui.HorizontalSplit(self.top_bar,self.roster_window,self.main_window,self.bottom_bar,{})
        self.screen.set_content(sp)
        self.screen.focus_window(self.main_window)
        self.status_window=None

    def update_status_bars(self):
        if self.top_bar:
            self.top_bar.update()
        if self.bottom_bar:
            self.bottom_bar.update()

    def run(self,screen):
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        self.screen=screen
        self.theme_manager=themes.ThemeManager(self)
        try:
            self.theme_manager.load()
        except (IOError,OSError):
            pass
        self.theme_manager.set_default_attrs(global_theme_attrs)
        self.theme_manager.set_default_formats(global_theme_formats)

        self.status_buf=ui.TextBuffer(self.theme_manager,"Status")
        self.status_buf.preference=self.settings["status_buffer_preference"]

        self.set_layout(self.settings["layout"],"plain")

        self.screen.update()

        if not os.path.exists(self.home_dir):
            try:
                os.makedirs(self.home_dir)
            except (OSError,IOError),e:
                self.__logger.info(e)

        logger=logging.getLogger()
        self.log_hdlr=cjclogging.ScreenHandler(self)
        if self.settings.get("debug"):
            self.log_hdlr.setLevel(logging.DEBUG)
        else:
            self.log_hdlr.setLevel(logging.INFO)
        logger.addHandler(self.log_hdlr)
        libxml2.registerErrorHandler(self.xml_error_handler,None)

        self.load_plugins()
        self.load()
        if not self.settings["jid"]:
            self.__logger.info("")
            self.__logger.info("Quickstart:")
            self.__logger.info("/set jid your_username@your.domain/your_resource")
            self.__logger.info("/set password your_password")
            self.__logger.info("/save")
            self.__logger.info("/connect")
            self.__logger.info("/chat jajcus@jabber.bnet.pl CJC Rulez!")
            self.__logger.info("")
            self.__logger.info("If you don't have your JID yet then register on some Jabber server first.")
            self.__logger.info("CJC doesn't support registration yet.")
            self.__logger.info("")
            self.__logger.info("press Alt-Tab (or Escape Tab) to change active window")
            self.__logger.info("PgUp/PgDown to scroll window content")

        self.update_status_bars()
        if self.profile:
            self.__logger.info("Running UI thread under profiler")
            self.ui_thread=threading.Thread(None,self.ui_loop_prof,"UI")
        else:
            self.ui_thread=threading.Thread(None,self.ui_loop,"UI")
        self.ui_thread.setDaemon(1)
        if self.profile:
            self.__logger.info("Running Stream thread under profiler")
            self.stream_thread=threading.Thread(None,self.stream_loop_prof,"Stream")
        else:
            self.stream_thread=threading.Thread(None,self.stream_loop,"Stream")
        self.stream_thread.setDaemon(1)

        self.ui_thread.start()
        self.stream_thread.start()

        if self.settings["autoconnect"]:
            self.cmd_connect()
        self.main_loop()


        for th in threading.enumerate():
            if th is threading.currentThread():
                continue
            th.join(1)
        for th in threading.enumerate():
            if th is threading.currentThread():
                continue
            th.join(1)

        logger.removeHandler(self.log_hdlr)

    def resize_handler(self):
        self.screen.lock.acquire()
        layout=self.settings["layout"]
        self.screen.set_input_handler(None)
        self.set_layout(layout,layout)
        self.screen.lock.release()

    def stream_created(self,stream):
        self.send_event("stream created",stream)

    def session_started(self):
        for p in self.plugins.values():
            try:
                p.session_started(self.stream)
            except:
                self.__logger.exception("Exception:")
                self.__logger.info("Plugin call failed")
        self.stream.set_message_handler("error",self.message_error)


    def stream_closed(self,stream):
        self.send_event("stream closed",stream)

    def stream_error(self,err):
        msg=u"Stream error"
        emsg=err.get_message()
        if emsg:
            msg+=": %s" % emsg
        etxt=err.get_text()
        if etxt:
            msg+=" ('%s')" % etxt
        self.__logger.error(msg)

    def connected(self):
        tls=self.stream.get_tls_connection()
        if tls:
            self.tls_connected(tls)
        elif self.settings.get("tls_require"):
            self.__logger.error("Couldn't start encryption."
                    " Are you sure your server supports it?")
            self.disconnect()
        else:
            self.__logger.info("Unencrypted connection to %s established."
                % (self.stream.peer,))

    def disconnected(self):
        self.disconnecting=0
        for user,info in self.user_info.items():
            if info.has_key("presence"):
                del info["presence"]
            if info.has_key("resources"):
                del info["resources"]
        self.__logger.warning("Disconnected")

    def message_error(self,stanza):
        self.__logger.warning(u"Message error from: "+stanza.get_from().as_unicode())
        return 1

    def cmd_quit(self,args):
        reason=args.all()
        args.finish()
        self.exit_request(reason)

    def cmd_connect(self,args=None):
        if self.stream:
            self.__logger.error(u"Already connected")
            return
        jid=self.settings.get("jid")
        if not jid:
            self.__logger.error(u"Can't connect - jid not given")
            return
        if None in (jid.node,jid.resource):
            self.__logger.error(u"Can't connect - jid is not full")
            return
        password=self.settings.get("password")
        if not password:
            self.__logger.error(u"Can't connect - password not given")
            return
        auth_methods=self.settings.get("auth_methods")
        if not auth_methods:
            self.__logger.error(u"Can't connect - auth_methods not given")
            return
        self.jid=jid
        self.password=password
        self.port=self.settings.get("port")
        if not self.port:
            self.port=5222
        self.server=self.settings.get("server")
        self.keepalive=self.settings.get("keepalive",0)
        self.auth_methods=auth_methods
        self.tls_init()
        self.__logger.info(u"Connecting:")
        try:
            self.connect()
        except pyxmpp.StreamError,e:
            self.__logger.error("Connection failed: "+str(e))
        except (socket.error),e:
            self.__logger.error("Connection failed: "+e.args[1])
        else:
            self.disco_identity.set_name("CJC Jabber client")
            self.disco_identity.set_category("client")
            self.disco_identity.set_type("console")

    def cmd_disconnect(self,args):
        if not self.stream:
            self.__logger.error(u"Not connected")
            return
        reason=args.all()
        args.finish()
        if self.disconnecting:
            self.force_disconnect()
        else:
            self.disconnecting=1
            if reason:
                self.__logger.info(u"Disconnecting (%s)..." % (reason,))
            else:
                self.__logger.info(u"Disconnecting...")
            self.send_event("disconnect request",reason)
            time.sleep(self.settings["disconnect_delay"])
            self.disconnect()

    def force_disconnect(self):
        self.__logger.info(u"Forcing disconnect...")
        self.lock.acquire()
        self.stream.close()
        self.stream=None
        self.lock.release()
        self.disconnected()

    def cmd_set(self,args):
        self.__logger.debug("args: "+`args.args`)
        fvar=args.shift()
        self.__logger.debug("fvar: "+`fvar`+" args:"+`args.args`)
        if not fvar:
            for plugin in [None]+self.plugins.keys():
                if plugin is None:
                    obj=self
                else:
                    obj=self.plugins[plugin]
                for var in obj.available_settings:
                    sdef=obj.available_settings[var]
                    if len(sdef)<3:
                        nsdef=[None,str,None]
                        nsdef[:len(sdef)]=list(sdef)
                        sdef=nsdef
                    descr,typ,handler=sdef
                    val=obj.settings.get(var)
                    if var=="password":
                        val=len(val) * '*'
                    if plugin is not None:
                        var="%s.%s" % (plugin,var)
                    if val is None:
                        self.__logger.info("%s is not set" % (var,))
                        continue
                    if type(typ) is TupleType:
                        typ=typ[0]
                    if typ is list:
                        self.__logger.info(u"%s = %s" % (var,string.join(val,",")))
                    elif typ is pyxmpp.JID:
                        self.__logger.info(u"%s = %s" % (var,val.as_unicode()))
                    else:
                        self.__logger.info(u"%s = %s" % (var,val))
            return

        val=args.shift()
        self.__logger.debug("val: "+`val`)
        args.finish()

        if fvar.find(".")>0:
            plugin,var=fvar.split(".",1)
            try:
                obj=self.plugins[plugin]
            except KeyError:
                self.__logger.error("Unknown category: "+plugin)
                return
        elif fvar[0]==".":
            obj=self
            var=fvar[1:]
        else:
            obj=self
            var=fvar

        try:
            sdef=obj.available_settings[var]
            if len(sdef)<3:
                nsdef=[None,str,None]
                nsdef[:len(sdef)]=list(sdef)
                sdef=nsdef
            descr,typ,handler=sdef
        except KeyError:
            self.__logger.error("Unknown setting: "+fvar)
            return

        if val is None:
            self.__logger.info(u"%s - %s" % (fvar,descr))
            val=obj.settings.get(var)
            if val is None:
                self.__logger.info("%s is not set" % (fvar,))
                return
            self.__logger.debug("Type: "+`typ`)
            if type(typ) in (TupleType,ListType):
                if type(typ[0]) is TypeType:
                    typ=typ[0]
            if typ is list:
                self.__logger.info(u"%s = %s" % (fvar,string.join(val,",")))
            elif typ is pyxmpp.JID:
                self.__logger.info(u"%s = %s" % (fvar,val.as_unicode()))
            else:
                self.__logger.info(u"%s = %s" % (fvar,val))
            return

        if type(typ) is not tuple:
            typ=(typ,)

        valid=0
        for t in typ:
            if val==t:
                valid=1
                break
            if t is None:
                continue
            if t is UnicodeType:
                valid=1
                break
            if t is bool:
                if val.lower() in ("t","true","yes","y","on"):
                    valid=1
                    val=True
                    break
                elif val.lower() in ("f","false","no","n","off"):
                    valid=1
                    val=False
                    break
                else:
                    try:
                        val=int(val)
                    except ValueError:
                        continue
                    val=bool(val)
                    valid=1
                    break
            try:
                if t is ListType:
                    val=val.split(",")
                elif type(t) is not TypeType and type(typ) is TupleType:
                    e="not one of: "+string.join(typ,",")
                    continue
                else:
                    val=t(val)
                valid=1
                break
            except Exception,e:
                continue

        if not valid:
            self.__logger.error("Bad value: "+str(e))
            return

        if handler:
            if not callable(handler):
                handler=getattr(obj,handler)

        oldval=obj.settings.get(var)
        obj.settings[var]=val
        if handler:
            handler(oldval,val)

    def cmd_unset(self,args):
        fvar=args.shift()

        if not fvar:
            return self.cmd_set(args)

        if fvar.find(".")>0:
            plugin,var=fvar.split(".",1)
            try:
                obj=self.plugins[plugin]
            except KeyError:
                self.__logger.error("Unknown category: "+plugin)
                return
        else:
            obj=self
            var=fvar

        try:
            descr,typ=obj.available_settings[var][:2]
        except KeyError:
            self.__logger.error("Unknown setting: "+fvar)
            return

        if typ is None:
            pass
        elif type(typ) is tuple and None in typ:
            pass
        else:
            self.__logger.error("%s cannot be unset %r" % (fvar,typ))
            return
        del obj.settings[var]

    def set_debug(self,oldval,newval):
        if newval:
            self.log_hdlr.setLevel(logging.DEBUG)
        else:
            self.log_hdlr.setLevel(logging.INFO)

    def set_layout(self,oldval,newval):
        if newval not in ("plain","icr","irc","vertical","horizontal"):
            self.settings["layout"]=oldval
            return
        self.screen.lock.acquire()
        if self.main_window:
            main_buf=self.main_window.buffer
        else:
            main_buf=None
        getattr(self,"layout_"+newval)()
        self.screen.lock.release()
        if self.status_window:
            self.status_window.set_buffer(self.status_buf)
        elif main_buf==None:
            main_buf=self.status_buf
        if self.main_window and main_buf:
            self.main_window.set_buffer(main_buf)
        self.send_event("layout changed",newval)
        self.screen.redraw()

    def cmd_save(self,args):
        filename=args.shift()
        args.finish()
        self.save(filename)

    def cmd_alias(self,args):
        name=args.shift()
        if not name:
            self.__logger.info("Aliases:")
            for alias,value in self.aliases.items():
                self.__logger.info(u"  /%s %s" % (alias,value))
            return
        value=args.all()
        if not value:
            if self.aliases.has_key(name):
                self.__logger.info("%s is an alias for: %s" % (name,self.aliases[name]))
            else:
                self.__logger.info("There is no such alias")
            return
        self.aliases[name]=value

    def cmd_unalias(self,args):
        name=args.shift()
        if not name:
            self.__logger.info("Aliases:")
            for alias,value in self.aliases.items():
                self.__logger.info(u"  /%s %s" % (alias,value))
            return
        args.finish()
        if self.aliases.has_key(name):
            del self.aliases[name]
        else:
            self.__logger.info("There is no such alias")

    def save(self,filename=None):
        if filename is None:
            filename=self.config_file
        if not os.path.split(filename)[0]:
            filename=os.path.join(self.home_dir,filename+".conf")
        self.__logger.info(u"Saving settings to "+filename)
        tmpfilename=filename+".tmp"
        try:
            f=file(tmpfilename,"w")
        except IOError,e:
            self.__logger.error(u"Couldn't open config file: "+str(e))
            return 0

        for plugin in [None]+self.plugins.keys():
            if plugin is None:
                obj=self
            else:
                obj=self.plugins[plugin]
            for var in obj.available_settings:
                descr,typ=obj.available_settings[var][:2]
                val=obj.settings.get(var)
                if val is None:
                    continue
                if plugin is not None:
                    var="%s.%s" % (plugin,var)
                args=ui.CommandArgs(var)
                if type(typ) is tuple:
                    typ=typ[0]
                if typ is list:
                    val=string.join(val,",")
                elif typ is pyxmpp.JID:
                    val=val.as_string()
                elif typ is unicode:
                    val=val.encode("utf-8")
                args.add_quoted(str(val))
                print >>f,"set",args.all()
        for alias,value in self.aliases.items():
            print >>f,"alias",alias,value

        for table in ui_keytable.keytables:
            for keyname,funame,descr in table.get_changed_bindings():
                if funame:
                    print >>f,"bind",funame,table.name,keyname
                else:
                    print >>f,"unbind",table.name,keyname

        if os.path.exists(filename):
            bakfilename=filename+".bak"
            if os.path.exists(bakfilename):
                os.unlink(bakfilename)
            os.rename(filename,bakfilename)
        else:
            bakfilename=None
        os.rename(tmpfilename,filename)
        if not self.settings["backup_config"] and bakfilename:
            os.unlink(bakfilename)
        return 1

    def cmd_load(self,args):
        filename=args.shift()
        args.finish()
        self.load(filename)

    def load(self,filename=None):
        if filename is None:
            filename=self.config_file
        if not os.path.split(filename)[0]:
            if filename=="default":
                legacy_filename=os.path.join(self.home_dir,"config")
            else:
                legacy_filename=os.path.join(self.home_dir,filename)
            filename=os.path.join(self.home_dir,filename+".conf")

        if not os.path.exists(filename) and os.path.exists(legacy_filename):
            self.__logger.warning("Renaming %r to %r" % (legacy_filename,filename) )
            try:
                os.rename(legacy_filename,filename)
            except OSError,e:
                self.__logger.warning("Operation failed: "+str(e))
                return 0
        try:
            f=file(filename,"r")
        except IOError,e:
            self.__logger.warning("Couldn't open config file: "+str(e))
            return 0

        for l in f.readlines():
            if not l:
                continue
            l=l.strip()
            if not l:
                continue
            if l[0]=='#':
                continue
            try:
                args=ui.CommandArgs(unicode(l,"utf-8"))
                self.__logger.debug("args: "+`args.args`)
                cmd=args.get()
                self.__logger.debug("cmd: %r args: %r" % (cmd,args.args))
                if cmd=="alias":
                    args.shift()
                    self.__logger.debug("alias %r" % (args.args,))
                    self.cmd_alias(args)
                elif cmd=="set":
                    args.shift()
                    self.__logger.debug("set %r" % (args.args,))
                    self.cmd_set(args)
                elif cmd=="bind":
                    args.shift()
                    self.__logger.debug("bind %r" % (args.args,))
                    self.cmd_bind(args)
                elif cmd=="unbind":
                    args.shift()
                    self.__logger.debug("unbind %r" % (args.args,))
                    self.cmd_unbind(args)
                else:
                    self.__logger.debug("set %r" % (args.args,))
                    self.cmd_set(args)
            except (ValueError,UnicodeError):
                self.__logger.warning(
                    "Invalid config directive %r ignored" % (l,))
        f.close()
        return 1

    def cmd_redraw(self,args):
        self.screen.redraw()

    def cmd_info(self,args):
        jid=args.shift()
        if not jid:
            self.__logger.error("JID missing")
            return
        args.finish()
        jid=self.get_user(jid)
        if jid is None:
            self.__logger.error("Invalid jabber id")
            return
        uinf=self.get_user_info(jid)
        if uinf is None:
            self.__logger.info(u"I know nothing about "+jid.as_unicode())
            return
        self.__logger.info(u"Information known about %s:" % (jid.as_unicode(),))
        for k,v in uinf.items():
            if not self.info_handlers.has_key(k):
                continue
            r=self.info_handlers[k](k,v)
            if not r:
                continue
            self.__logger.info(u"  %s: %s" % r)

    def cmd_help(self,args):
        cmd=args.shift()
        if not cmd:
            self.__logger.info("Available commands:")
            for tb in ui_cmdtable.command_tables:
                tname=tb.name[0].upper()+tb.name[1:]
                if tb.active:
                    active="active"
                else:
                    active="inactive"
                self.__logger.info("  %s commands (%s):" % (tname,active))
                for cmd in tb.get_commands():
                    self.__logger.info(u"    /"+cmd.name)
            return

        if cmd[0]=="/":
            cmd=cmd[1:]

        try:
            cmd=ui_cmdtable.lookup_command(cmd,1,1)
        except KeyError:
            try:
                cmd=ui_cmdtable.lookup_command(cmd,0,1)
            except KeyError:
                self.__logger.error(u"Unknown command: "+`cmd`)
                return

        self.__logger.info(u"Command /%s:" % (cmd.name,))
        if type(cmd.usage) in (ListType,TupleType):
            for u in cmd.usage:
                self.__logger.info(u"  "+u)
        else:
            self.__logger.info(u"  "+cmd.usage)
        self.__logger.info(u"  "+cmd.descr)

    def cmd_theme(self,args):
        self.theme_manager.command(args)

    def cmd_bind(self,args):
        function=args.shift()
        if not function:
            self.status_buf.append_themed("keybindings",
                        {"tables":self.format_keytables})
            self.status_buf.update()
            return
        arg2=args.shift()
        if arg2:
            arg3=args.shift()
            if arg3:
                table,keyname=arg2,arg3
            else:
                table,keyname=None,arg2
        else:
            table=None
            keyname=None
        args.finish()
        if not keyname:
            self.__logger.error("Not implemented yet (you must give keyname argument).")
            return
        ui.bind(keyname,function,table)

    def cmd_unbind(self,args):
        arg1=args.shift()
        arg2=args.shift()
        args.finish()
        if arg2:
            table,keyname=arg1,arg2
        else:
            table,keyname=None,arg1
        ui.unbind(keyname,table)

    def cmd_buffer_list(self,args):
        args.finish()
        formatted_list=[]
        i=1
        for b in ui_buffer.buffer_list:
            if not b:
                continue
            formatted_list+=self.theme_manager.format_string("buffer_on_list",b.info)
            i+=1
        params={
                "buffers_on_list": formatted_list,
                "buffer_count": len(ui_buffer.buffer_list),
        }
        self.status_buf.append_themed("buffer_list",params)
        self.status_buf.update(1)

    def cmd_load_plugin(self,args):
        name=args.shift()
        args.finish()
        if not name:
            self.__logger.error("Plugin name missing.")
            return
        self.load_plugin(name)

    def cmd_unload_plugin(self,args):
        name=args.shift()
        args.finish()
        if not name:
            self.__logger.error("Plugin name missing.")
            return
        self.unload_plugin(name)

    def cmd_reload_plugin(self,args):
        name=args.shift()
        args.finish()
        if not name:
            self.__logger.error("Plugin name missing.")
            return
        self.reload_plugin(name)

    def format_keytables(self,attr,params):
        r=[]
        for table in ui_keytable.keytables:
            p={ "name": table.name, "priority": table.prio,
                "bindings": self.format_keybindings,
                "unbound": self.format_unbound_keyfunctions}
            r+=self.theme_manager.format_string("keytable",p)
        return r

    def format_keybindings(self,attr,params):
        table=ui_keytable.lookup_table(params["name"])
        r=[]
        for keyname,funame,desc in table.get_bindings():
            p={ "table": table.name, "key": keyname,
                "function": funame, "description": desc}
            r+=self.theme_manager.format_string("keybinding",p)
        return r

    def format_unbound_keyfunctions(self,attr,params):
        table=ui_keytable.lookup_table(params["name"])
        r=[]
        for f in table.get_unbound_functions():
            p={ "table": table.name, "function": f.name,
                "description": f.descr}
            if f.accepts_arg:
                p["function"]=f.name+"(<arg>)"
            r+=self.theme_manager.format_string("keyfunction",p)
        return r

    def exit_request(self,reason):
        if self.stream:
            if self.disconnecting:
                self.force_disconnect()
            else:
                self.disconnecting=1
                if reason:
                    self.__logger.info(u"Disconnecting (%s)..." % (reason,))
                else:
                    self.__logger.info(u"Disconnecting...")
                self.send_event("disconnect request",reason)
                time.sleep(self.settings["disconnect_delay"])
                self.disconnect()
        self.state_changed.acquire()
        self.exiting=time.time()
        self.state_changed.notify()
        self.state_changed.release()

    def exit_time(self):
        if not self.exiting:
            return 0
        if not self.stream:
            return 1
        if self.exiting>time.time()+self.settings["disconnect_timeout"]:
            return 1
        return 0

    def ui_loop_prof(self):
        import profile
        p=profile.Profile()
        p.runcall(self.ui_loop)
        p.create_stats()
        p.dump_stats("cjc-ui.prof")

    def ui_loop(self):
        last_time=datetime.datetime.now()
        last_active=last_time
        idle=0
        while not self.exit_time():
            try:
                act=ui.keypressed()
            except (KeyboardInterrupt,SystemExit),e:
                self.exit_request(str(e))
                self.__logger.exception("Exception:")
                act=1
            except common.non_errors:
                raise
            except:
                self.__logger.exception("Exception:")
                act=0
            now=datetime.datetime.now()
            if now.day!=last_time.day:
                self.send_event("day changed")
            if act:
                self.send_event("keypressed")
                last_active=now
                idle=0
            else:
                dif=now-last_active
                if dif>datetime.timedelta(seconds=idle):
                    idle=dif.seconds+24L*60*60*dif.days
                    self.send_event("idle",idle)
            last_time=now
        self.__logger.debug("UI loop exiting")

    def stream_loop_prof(self):
        import profile
        p=profile.Profile()
        p.runcall(self.stream_loop)
        p.create_stats()
        p.dump_stats("cjc-stream.prof")

    def stream_loop(self):
        while not self.exit_time():
            self.state_changed.acquire()
            stream=self.stream
            if not stream:
                self.state_changed.wait(1)
                stream=self.stream
            self.state_changed.release()
            if not stream:
                continue
            try:
                self.stream.loop_iter(1)
            except (pyxmpp.FatalStreamError,pyxmpp.StreamEncryptionRequired),e:
                self.state_changed.acquire()
                try:
                    self.__logger.error(str(e))
                    try:
                        self.stream.close()
                    except:
                        pass
                    self.stream=None
                    self.state_changed.notify()
                finally:
                    self.state_changed.release()
            except pyxmpp.StreamError,e:
                self.__logger.error(str(e))
            except (KeyboardInterrupt,SystemExit),e:
                self.exit_request(unicode(str(e)))
                self.__logger.exception("Exception:")
            except common.non_errors:
                raise
            except:
                self.__logger.error("Other error cought")
                self.__logger.exception("Exception:")
        self.__logger.debug("Stream loop exiting")

    def main_loop(self):
        while not self.exit_time():
            try:
                self.state_changed.acquire()
                self.state_changed.wait(1)
                self.state_changed.release()
            except (KeyboardInterrupt,SystemExit),e:
                self.exit_request(unicode(str(e)))
                self.__logger.exception("Exception:")
        self.__logger.debug("Main loop exiting")

    def get_user(self,name):
        if name.find("@")>=0:
            if self.roster:
                try:
                    ritems=self.roster.items_by_name(name,self.settings["case_sensitive"])
                except KeyError:
                    ritems=None
                if ritems:
                    if len(ritems)==1:
                        return ritems[0].jid
            try:
                return pyxmpp.JID(name)
            except pyxmpp.JIDError:
                self.__logger.error(u"Invalid JID: %s" % (name,))
                return None

        if not self.roster:
            self.__logger.error(u"%s not found in roster" % (name,))
            return None

        try:
            ritems=self.roster.items_by_name(name,self.settings["case_sensitive"])
        except KeyError:
            try:
                jid=pyxmpp.JID(name)
                return self.roster.item_by_jid(jid).jid()
            except (ValueError,pyxmpp.JIDError,KeyError):
                pass
            self.__logger.error(u"%s not found in roster" % (name,))
            return None

        if ritems:
            if len(ritems)>1:
                self.__logger.error("ambiguous user name")
                return None
            else:
                return ritems[0].jid
        self.__logger.error(u"%s not found in roster" % (name,))
        return None

    def get_bare_user_info(self,jid,var=None):
        if jid.resource:
            jid=jid.bare()
        if not self.user_info.has_key(jid):
            return None
        if var is None:
            return self.user_info[jid]
        return self.user_info[jid].get(var)

    def get_user_info(self,jid,var=None):
        uinf=self.get_bare_user_info(jid)
        if uinf is None:
            return None
        uinf=uinf.copy()
        if uinf.has_key("resources") and uinf["resources"].has_key(jid.resource):
            uinf.update(uinf["resources"][jid.resource])
        if var is None:
            return uinf
        return uinf.get(var)

    def set_user_info(self,jid,var,val):
        bare=jid.bare()
        if self.user_info.has_key(bare):
            uinf=self.user_info[bare]
            if not uinf.has_key("resources"):
                uinf["resources"]={}
        else:
            uinf={"resources":{},"jid":bare}
            self.user_info[bare]=uinf

        if uinf["resources"].has_key(jid.resource):
            fuinf=uinf["resources"][jid.resource]
        else:
            fuinf={"jid":jid}
            uinf["resources"][jid.resource]=fuinf
        fuinf[var]=val

    def set_bare_user_info(self,jid,var,val):
        bare=jid.bare()
        if self.user_info.has_key(bare):
            uinf=self.user_info[bare]
        else:
            uinf={"jid":bare}
            self.user_info[bare]=uinf
        uinf[var]=val

    def roster_updated(self,jid=None):
        if jid is None:
            self.__logger.info("Got roster")
        else:
            self.__logger.debug("Roster updated")
        self.send_event("roster updated",jid)

    def stream_state_changed(self,state,arg):
        if state=="resolving":
            self.__logger.info("Resolving %r..." % (arg,))
        if state=="resolving srv":
            self.__logger.info("Resolving SRV for %r on %r..." % (arg[1],arg[0]))
        elif state=="connecting":
            self.__logger.info("Connecting to %s:%i..." % (arg[0],arg[1]))
        elif state=="connected":
            self.__logger.info("Connected to %s:%i." % (arg[0],arg[1]))
        elif state=="authenticating":
            self.__logger.info("Authenticating as %s..." % (arg,))
        elif state=="binding":
            self.__logger.info("Binding to resource %s..." % (arg,))
        elif state=="authorized":
            self.__logger.info("Authorized as %s." % (arg,))
        elif state=="tls connecting":
            self.__logger.info("Doing TLS handhake with %s." % (arg,))

    def show_error(self,s):
        self.status_buf.append_themed("error",s)
        self.status_buf.update(1)

    def show_warning(self,s):
        self.status_buf.append_themed("warning",s)
        self.status_buf.update(1)

    def show_info(self,s):
        self.status_buf.append_themed("info",s)
        self.status_buf.update(1)

    def show_debug(self,s):
        self.status_buf.append_themed("debug",s)
        self.status_buf.update(1)

    def xml_error_handler(self,ctx,error):
        self.__logger.debug(u"XML error: "+unicode(error,"utf-8","strict"))

ui.KeyTable("default",0,(
    ui.KeyFunction("command()",
        Application.key_command,
        "Execute command '<arg>'"),
    )).install()
ui.KeyTable("global",100,(
    ui.KeyFunction("resize",
        Application.resize_handler,
        "Proces terminal resize request",
        "RESIZE"),
    )).install()

ui.CommandTable("global",10,(
    ui.Command("quit",Application.cmd_quit,
        "/quit [reason]",
        "Exit CJC",
        ("text",)),
    ui.CommandAlias("exit","quit"),
    ui.Command("set",Application.cmd_set,
        "/set [setting] [value]",
        "Changes one of the settings."
        " Without any arguments shows all current settings."
        " With only one argument shows description and current value of given settings.",
        ("setting","opaque")),
    ui.Command("unset",Application.cmd_unset,
        "/unset [setting]",
        "Unsets one of settings.",
        ("setting",)),
    ui.Command("connect",Application.cmd_connect,
        "/connect",
        "Connect to a Jabber server"),
    ui.Command("disconnect",Application.cmd_disconnect,
        "/disconnect [reason]",
        "Disconnect from a Jabber server",
        ("text",)),
    ui.Command("save",Application.cmd_save,
        "/save [filename]",
        "Save current settings to a file (default: ~/.cjc/config)",
        ("config",)),
    ui.Command("load",Application.cmd_load,
        "/load [filename]",
        "Load settings from a file (default: ~/.cjc/config)",
        ("config",)),
    ui.Command("redraw",Application.cmd_redraw,
        "/redraw",
        "Redraw screen"),
    ui.Command("info",Application.cmd_info,
        "/info jid",
        "Show information known about given jid",
        ("user",)),
    ui.Command("help",Application.cmd_help,
        "/help [command]",
        "Show simple help",
        ("command",)),
    ui.Command("theme",Application.cmd_theme,
        ("/theme load [filename]","/theme save [filename]"),
        "Theme management. Default theme filename is \"~/.cjc/theme\"",
        ("load|save","theme")),
    ui.Command("alias",Application.cmd_alias,
        "/alias name command [arg...]",
        "Defines an alias for command. When the alias is used $1, $2, etc."
        " are replaced with alias arguments.",
        ("opaque","command","text")),
    ui.Command("unalias",Application.cmd_unalias,
        "/unalias name",
        "Undefines an alias for command.",
        ("alias",)),
    ui.Command("bind",Application.cmd_bind,
        "/bind [function [[table] keyname]]",
        "Without arguments - shows current keybindings otherwise binds"
        " given function to a key. If keyname is not given user will be"
        " asked to press one. If a table is given only the function is bound"
        " in that table, otherwise in all tables that define it."),
    ui.Command("unbind",Application.cmd_unbind,
        "/unbind [table] keyname",
        "Unbinds given key."),
    ui.Command("buffer_list",Application.cmd_buffer_list,
        "/buffer_list",
        "List all buffers"),
    ui.CommandAlias("listbuf","buffer_list"),
    ui.CommandAlias("buflist","buffer_list"),
    ui.Command("load_plugin",Application.cmd_load_plugin,
        "/load_plugin name",
        "Loads a plugin."),
    ui.Command("unload_plugin",Application.cmd_unload_plugin,
        "/unload_plugin name",
        "Unloads a plugin. Loaded code is still remembered, but not active."),
    ui.Command("reload_plugin",Application.cmd_reload_plugin,
        "/reload_plugin name",
        "Reloads a plugin."),
    )).install()

def usage():
    print
    print "Console Jabber Client (c) 2003 Jacek Konieczny <jajcus@bnet.pl>"
    print
    print "Usage:"
    print "  %s [OPTIONS]" % (sys.argv[0],)
    print
    print "Options:"
    print "  -c filename"
    print "  --config-file=filename   Config file to load. If filename doesn't contain"
    print "               slashes the file is assumed to be in ~/.cjc or wherever"
    print "               --config-directory option points"
    print "               default: 'config'"
    print "  -C dir"
    print "  --config-directory=dir   Directory, where config files, themes, logs etc."
    print "               will be stored"
    print "               default: '~/.cjc'"
    print "  -t filename"
    print "  --theme-file=filename    Theme file to load. If filename doesn't contain"
    print "               slashes the file is assumed to be in ~/.cjc/themes"
    print "               default: 'default'"
    print "  -l filename"
    print "  --log-file=filename      File where debug log should be written"
    print "  -L filename"
    print "  --append-log-file=filename  File where debug log should be appended"
    print "  -P"
    print "  --profile                Write profiling statistics"

def main(base_dir,profile=False):
    logger=logging.getLogger()
    logger.setLevel(logging.DEBUG)
    libxml2.debugMemory(1)
    locale.setlocale(locale.LC_ALL,"")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hc:C:t:l:",
                    ["help","config-file=","config-directory=","theme-file=","log-file="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    if args:
        usage()
        sys.exit(2)

    config_file="default"
    theme_file="default"
    config_dir=None
    for o,a in opts:
        if o in ("-c","--config-file"):
            config_file=a
        elif o in ("-C","--config-directory"):
            config_dir=a
        elif o in ("-t","--theme-file"):
            theme_file=a
        elif o in ("-l","--log-file","-L","--append-log-file"):
            if o in ("-L","--append-log-file"):
                mode="a"
            else:
                mode="w"
            if a=="-":
                hdlr=logging.StreamHandler(sys.stderr)
            else:
                hdlr=logging.FileHandler(a,mode)
            formatter=cjclogging.UnicodeFormatter("utf-8",u'%(asctime)s %(levelname)s %(message)s')
            hdlr.setFormatter(formatter)
            logger.addHandler(hdlr)
        else:
            usage()
            sys.exit(0)
    app=Application(base_dir,config_file,theme_file,home_dir=config_dir,profile=profile)
    try:
        screen=ui.init()
        app.run(screen)
    finally:
        #logging.debug("Cleaning up")
        ui.deinit()
        #logging.debug("Cleaned up")

# vi: sts=4 et sw=4
