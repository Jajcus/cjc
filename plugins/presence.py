# Console Jabber Client
# Copyright (C) 2004-2009  Jacek Konieczny
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

import string
import time

import pyxmpp

from cjc.plugin import PluginBase
from cjc import ui
from cjc import cjc_globals

theme_formats=(
    ("presence.available","%[info][%(T:timestamp)s] %(J:user)s (%(J:user:rostername)s) is %(J:user:show)s: %(J:user:status)s\n"),
    ("presence.unavailable","%[info][%(T:timestamp)s] %(J:user)s (%(J:user:rostername)s) is unavailable\n"),
    ("presence.subscribe","%[info][%(T:timestamp)s] %(J:user)s sent you a presence subscription request\n"),
    ("presence.subscribe_buffer","Subscription request from %(J:user)s"),
    ("presence.subscribe_accepted","%[info][%(T:timestamp)s] You have accepted presence subscription request from %(J:user)s\n"),
    ("presence.subscribe_denied","%[info][%(T:timestamp)s] You have denied presence subscription request from %(J:user)s\n"),
    ("presence.unsubscribe","%[info][%(T:timestamp)s] %(J:user)s unsubscribed from your presence\n"),
    ("presence.subscribed","%[info][%(T:timestamp)s] %(J:user)s accepted your presence subscription request\n"),
    ("presence.unsubscribed","%[info][%(T:timestamp)s] %(J:user)s denied your presence subscription\n"),
)

show_weight = {"xa": 0, "away": 1, "dnd": 2, None: 3, "chat": 4}

class Plugin(PluginBase):
    def __init__(self,app,name):
        PluginBase.__init__(self,app,name)
        cjc_globals.theme_manager.set_default_formats(theme_formats)
        self.available_settings={
            "priority": ("Priority of current resource",int),
            "chat_priority": ("Priority of current resource in ready-for-chat"
                    " mode",(int,None)),
            "dnd_priority": ("Priority of current resource in dnd mode",
                    (int,None)),
            "away_priority": ("Priority of current resource in away mode",
                    (int,None)),
            "xa_priority": ("Priority of current resource in xa mode",
                    (int,None)),
            "auto_away": ("Time in minutes after set presence should be set"
                    " to 'away' (unset or 0 to disable)",(int,None)),
            "auto_xa": ("Time in minutes after set presence should be set"
                    " to 'xa' (unset or 0 to disable)",(int,None)),
            "auto_away_msg": ("Auto-away status description (if empty and"
                    " presence.keep_description is set then status description"
                    " is not changed",(unicode,None)),
            "auto_xa_msg": ("Auto-away status description (if empty and "
                    "presence.keep_description is set then status description"
                    " is not changed)",(unicode,None)),
            "show_changes": ("Auto-away status description",(int,None)),
            "show_errors": ("Auto-away status description",(int,None)),
            "buffer_preference": ("Preference of presence subscription buffers"
                    " when switching to the next active buffer. If 0 then"
                    " the buffer is not even shown in active buffer list.",int),
            "auto_popup": ("When enabled each new presence subscription buffer"
                    " is automatically made active.",bool),
            "keep_description": ("When changing status (online,away,etc.) keep"
                    " status description (reason).",bool),
            "no_auto_away_when": ("Modes in which now auto-away or auto-xa"
                    " should happen.",list),
            }
        self.settings={
            "priority": 1,
            "auto_away": 5,
            "auto_xa": 15,
            "auto_away_msg": u"Automatically away after %i minutes of inactivity",
            "auto_xa_msg": u"Automatically xa after %i minutes of inactivity",
            "show_changes": 1,
            "show_errors": 1,
            "buffer_preference": 50,
            "auto_popup": False,
            "keep_description": False,
            "no_auto_away_when": ["away","xa","dnd"]
            }
        app.add_info_handler("resources",self.info_resources)
        app.add_info_handler("presence",self.info_presence)
        app.add_info_handler("weight",self.info_weight)
        app.add_event_handler("disconnect request",self.ev_disconnect_request)
        app.add_event_handler("idle",self.ev_idle)
        ui.activate_cmdtable("presence",self)
        self.away_saved_presence=None

    def info_weight(self,k,v):
        return "Weight", `v`
    
    def info_resources(self,k,v):
        if not v:
            return None
        resources = []
        for r in v.keys():
            p = v[r].get("presence")
            if p is None or (p.get_type() and p.get_type() != "available"):
                continue
            if not r:
                r = u"<empty>"
            r += " (prio=%i)" % (p.get_priority(), )
            resources.append(r)
        if resources:
            return "Available resources", string.join(resources, ", ")

    def info_presence(self,k,v):
        if not v:
            return None

        name = "Presence"
        if not v.get_type() or v.get_type() == "available":
            value = "Available"
            value += " (prio=%i)" % (v.get_priority(), )
            if v.get_show():
                value += " [%s]" % (v.get_show(), )
            if v.get_status():
                value += " %s" % (v.get_status(), )
        elif v.get_type() == "unavailable":
            value = "Not Available"
            if v.get_status():
                value += " %s" % (v.get_status(), )
        elif v.get_type() == "error":
            value = "Error"
            e = v.get_error()
            if e:
                c = e.get_condition()
                if c:
                    value += ": %s" % (c.serialize(), )
        else:
            return None
        return name,value

    def session_started(self,stream):
        self.cjc.stream.set_presence_handler("error",self.presence_error)
        self.cjc.stream.set_presence_handler(None,self.presence_available)
        self.cjc.stream.set_presence_handler("unavailable",self.presence_unavailable)
        self.cjc.stream.set_presence_handler("subscribe",self.presence_subscribe)
        self.cjc.stream.set_presence_handler("unsubscribe",self.presence_subscription_change)
        self.cjc.stream.set_presence_handler("subscribed",self.presence_subscription_change)
        self.cjc.stream.set_presence_handler("unsubscribed",self.presence_subscription_change)
        self.set_presence(pyxmpp.Presence(priority=self.settings["priority"]))

    def ev_disconnect_request(self,event,arg):
        p=pyxmpp.Presence(stanza_type="unavailable",status=arg)
        self.set_presence(p)

    def ev_idle(self,event,arg):
        if not self.cjc.stream:
            return
        auto_away = self.settings.get("auto_away")
        auto_xa = self.settings.get("auto_xa")
        if auto_away and auto_xa:
            minidle=min(auto_away,auto_xa)
        elif auto_away:
            minidle=auto_away
        elif auto_xa:
            minidle=auto_xa
        else:
            return
        idle=int(arg/60)
        if idle<minidle:
            return
        p=self.cjc.get_user_info(self.cjc.jid,"presence")
        if (not p or p.get_type()=="unavailable"
            or (p.get_show() in self.settings["no_auto_away_when"]
                    and not self.away_saved_presence)):
            return

        if not self.away_saved_presence:
            self.away_saved_presence = p.copy()
            self.away_saved_presence.set_to(None)

        insert_time=False

        if auto_xa and idle>=auto_xa:
            if p.get_show()=="xa":
                return
            show="xa"
            prio=self.settings.get("xa_priority",
                    self.settings.get("away_priority",
                            self.settings.get("priority",0)))
            status=self.settings.get("auto_xa_msg","")
            if status:
                insert_time=True
            elif self.settings.get("keep_description"):
                status=p.get_status()
        elif auto_away and idle>=auto_away:
            if p.get_show()=="away":
                return
            show="away"
            prio=self.settings.get("away_priority",self.settings.get("priority",0))
            status=self.settings.get("auto_away_msg","")
            if status:
                insert_time=True
            elif self.settings.get("keep_description"):
                status=p.get_status()
        else:
            return

        self.cjc.add_event_handler("keypressed",self.ev_keypressed)
        if insert_time and "%i" in status:
            p=pyxmpp.Presence(priority=prio, show=show, status=status % (idle,))
        else:
            p=pyxmpp.Presence(priority=prio, show=show, status=status)
        self.set_presence(p)

    def ev_keypressed(self,event,arg):
        self.cjc.remove_event_handler(event,self.ev_keypressed)
        if self.away_saved_presence:
            if self.cjc.stream:
                self.set_presence(self.away_saved_presence)
            self.away_saved_presence=None

    def change_status(self,mode,args,default_priority=None):
        if self.away_saved_presence:
            self.away_saved_presence=None
            self.cjc.remove_event_handler("keypressed",self.ev_keypressed)
        if not self.cjc.stream:
            self.error("Connect first!")
            return
        to=None
        priority=default_priority
        keep=self.settings.get("keep_description")
        while 1:
            opt=args.get()
            if opt=="-keep":
                keep=True
                args.shift()
                continue
            elif opt=="-clear":
                keep=False
                args.shift()
                continue
            elif opt=="-to":
                args.shift()
                to=args.shift()
                if not to:
                    self.error("'/%s -to' without any argument",mode)
                    return
                try:
                    to=pyxmpp.JID(to)
                except ValueError:
                    return
                continue
            break

        reason=args.all()

        current=self.cjc.get_user_info(self.cjc.jid,"presence")
        if keep and not reason:
            reason=current.get_status()
        if mode=="offline":
            p=pyxmpp.Presence(status=reason,to_jid=to,stanza_type="unavailable")
        else:
            if priority is None:
                priority=self.settings.get("priority",1)
            if mode=="online":
                show=None
            elif mode=="chatready":
                show="chat"
            else:
                show=mode
            p=pyxmpp.Presence(show=show,status=reason,to_jid=to,priority=priority)
        self.set_presence(p)

    def cmd_online(self,args):
        self.change_status("online",args)

    def cmd_away(self,args):
        self.change_status("away",args,self.settings.get("away_priority"))

    def cmd_xa(self,args):
        priority=self.settings.get("xa_priority")
        if not priority:
            priority=self.settings.get("away_priority")
        self.change_status("xa",args,priority)

    def cmd_dnd(self,args):
        self.change_status("dnd",args,self.settings.get("dnd_priority"))

    def cmd_chatready(self,args):
        self.change_status("chatready",args,self.settings.get("chat_priority"))

    def cmd_offline(self,args):
        self.change_status("offline",args)

    def cmd_subscribe(self,args):
        user=args.shift()
        if not user:
            self.error("/subscribe without an argument")
            return

        args.finish()

        user=self.cjc.get_user(user)
        if user is None:
            return
        if user.bare()==self.cjc.stream.me.bare():
            self.error("Self presence subscription is automatic."
                    " Cannot subscribe own presence.")
            return
        p=pyxmpp.Presence(stanza_type="subscribe",to_jid=user)
        self.cjc.stream.send(p)

    def cmd_unsubscribe(self,args):
        user=args.shift()
        if not user:
            self.error("/unsubscribe without an argument")
            return
        args.finish()

        user=self.cjc.get_user(user)
        if user is None:
            return
        if user.bare()==self.cjc.stream.me.bare():
            self.error("Self presence subscription is automatic."
                    " Cannot unsubscribe own presence.")
            return

        p=pyxmpp.Presence(stanza_type="unsubscribe",to_jid=user)
        self.cjc.stream.send(p)

    def cmd_cancel(self,args):
        user=args.shift()
        if not user:
            self.error("/cancel without an argument")
            return

        args.finish()

        user=self.cjc.get_user(user)
        if user is None:
            return
        if user.bare()==self.cjc.stream.me.bare():
            self.error("Self presence subscription is automatic."
                    " Cannot cancel own presence subscription.")
            return
        p=pyxmpp.Presence(stanza_type="unsubscribed",to_jid=user)
        self.cjc.stream.send(p)

    def set_presence(self,p):
        if not self.cjc.stream:
            self.error("Cannot change presence: Disconnected.")
            return
        self.cjc.stream.send(p)
        if not p.get_to():
            self.cjc.set_user_info(self.cjc.jid,"presence",p)
            self.compute_current_resource(self.cjc.jid.bare())
            self.cjc.send_event("presence changed",self.cjc.jid)

    def presence_error(self,stanza):
        fr=stanza.get_from()
        msg=u"Presence error from: "+fr.as_unicode()
        err=stanza.get_error()
        emsg=err.get_message()
        if emsg:
            msg+=": %s" % emsg
        etxt=err.get_text()
        if etxt:
            msg+=" ('%s')" % etxt
        self.debug(stanza.get_error().serialize())

        if self.cjc.get_user_info(fr) and self.settings.get("show_errors"):
            self.warning(msg)
        else:
            self.debug(msg)
        if fr.resource:
            self.cjc.set_user_info(fr,"presence",stanza.copy())
            self.compute_current_resource(fr.bare())
        elif not self.cjc.get_bare_user_info(fr,"resources"):
            self.cjc.set_bare_user_info(fr,"presence",stanza.copy())
        self.cjc.send_event("presence changed",fr)
        return 1

    def presence_available(self,stanza):
        fr=stanza.get_from()
        p=self.cjc.get_user_info(fr, "presence")
        self.cjc.set_user_info(fr, "presence", stanza.copy())
        self.compute_current_resource(fr.bare())
        self.cjc.send_event("presence changed", fr)
        if (not p or p!=stanza) and self.settings.get("show_changes"):
            self.cjc.status_buf.append_themed("presence.available", {"user":fr})
            self.cjc.status_buf.update()
        else:
            self.debug(fr.as_unicode()+u" is unavailable")
        return 1

    def presence_unavailable(self,stanza):
        fr=stanza.get_from()
        if self.cjc.get_user_info(fr) and self.settings.get("show_changes"):
            self.cjc.status_buf.append_themed("presence.unavailable", {"user":fr})
            self.cjc.status_buf.update()
        else:
            self.debug(fr.as_unicode()+u" is unavailable")
        self.cjc.set_user_info(fr,"presence",stanza.copy())
        self.compute_current_resource(fr.bare())
        self.cjc.send_event("presence changed",fr)
        return 1

    def compute_current_resource(self, jid):
        resources = self.cjc.get_bare_user_info(jid, "resources")
        if not resources:
            p = self.cjc.get_bare_user_info(jid, "presence")
            if p and p.get_type() != "error" and p.get_from().resource:
                self.cjc.set_bare_user_info(jid, "presence", None)
            self.cjc.set_bare_user_info(jid, "weight", None)
            return
        presence = None
        max_prio = -129
        for r, d in resources.items():
            fjid = pyxmpp.JID(jid.node, jid.domain, r, check = 0)
            if not d.has_key("presence"):
                continue
            p = d["presence"]
            if not p:
                continue
            typ = p.get_type()
            if typ and typ != "available":
                continue
            prio = p.get_priority()
            if prio > max_prio:
                max_prio = prio
                presence = p
        if presence:
            weight = show_weight.get(presence.get_show(), show_weight[None]) * 1000 + max_prio
        else:
            weight = 0
        if max_prio < 0:
            weight -= 10000
        self.cjc.set_bare_user_info(jid, "presence", presence)
        self.cjc.set_bare_user_info(jid, "weight", weight)

    def presence_subscribe(self,stanza):
        fr=stanza.get_from()
        if fr.bare()==self.cjc.stream.me.bare():
            self.debug("Ignoring own presence subscription request")
            return
        reason=stanza.get_status()
        buf=ui.TextBuffer({"user":fr},"presence.subscribe_buffer")
        buf.preference=self.settings["buffer_preference"]
        buf.append_themed("presence.subscribe",{"user":fr,"reason":reason})
        stanza_copy = stanza.copy()
        def callback(response):
            return self.subscribe_decision(response, stanza_copy, buf)
        buf.ask_question("Accept?", "boolean", None, callback, None, None, 1)
        if self.settings.get("auto_popup"):
            cjc_globals.screen.display_buffer(buf)

    def subscribe_decision(self, accept, stanza, buf):
        fr=stanza.get_from()
        if accept:
            p=stanza.make_accept_response()
            self.cjc.stream.send(p)
            self.cjc.status_buf.append_themed("presence.subscribe_accepted",{"user":fr})
            try:
                item=self.cjc.roster.get_item_by_jid(fr)
            except KeyError:
                item=None
            if item and item.subscription in ("both","to"):
                buf.close()
                stanza.free()
            else:
                stanza_copy = stanza.copy()
                def callback(response):
                    return self.subscribe_back_decision(response, stanza_copy, buf)
                buf.ask_question(u"Subscribe to %s?" % (fr.as_unicode(),),
                        "boolean", None, callback, None, None, 1)
        else:
            p=stanza.make_deny_response()
            self.cjc.stream.send(p)
            self.cjc.status_buf.append_themed("presence.subscribe_denied",{"user":fr})
            buf.close()
            stanza.free()

    def subscribe_back_decision(self, accept, stanza, buf):
        if accept:
            p=pyxmpp.Presence(stanza_type="subscribe",to_jid=stanza.get_from())
            self.cjc.stream.send(p)
        buf.close()
        stanza.free()

    def presence_subscription_change(self,stanza):
        fr=stanza.get_from()
        if fr.bare()==self.cjc.stream.me.bare():
            self.debug("Ignoring own presence subscription change request")
            return
        typ=stanza.get_type()
        self.cjc.status_buf.append_themed("presence.%s" % (typ,),{"user":fr})
        p=stanza.make_accept_response()
        self.cjc.stream.send(p)

ui.CommandTable("presence",50,(
    ui.Command("online",Plugin.cmd_online,
        "/online [-to jid] [-keep | -clear] [-priority n] [description]",
        "Set availability to 'online' with optional description."
        " '-to' option directs the presence to given user,"
        " '-keep' forces keeping current status description,"
        " '-clear' clears it, '-priority' allows setting the priority"
        " to an integer in range -128 to 127.",
        ("-to jid","-keep","-clear","-priority opaque","text")),
    ui.CommandAlias("back","online"),
    ui.Command("away",Plugin.cmd_away,
        "/away [-to jid] [-keep | -clear] [-priority n] [description]",
        "Set availability to 'away' with optional description."
        " '-to' option directs the presence to given user,"
        " '-keep' forces keeping current status description,"
        " '-clear' clears it, '-priority' allows setting the priority"
        " to an integer in range -128 to 127.",
        ("-to jid","-keep","-clear","-priority opaque","text")),
    ui.Command("xa",Plugin.cmd_xa,
        "/xa [-to jid] [-keep | -clear] [-priority n] [description]",
        "Set availability to 'extended away' with optional description."
        " '-to' option directs the presence to given user,"
        " '-keep' forces keeping current status description,"
        " '-clear' clears it, '-priority' allows setting the priority"
        " to an integer in range -128 to 127.",
        ("-to jid","-keep","-clear","-priority opaque","text")),
    ui.Command("dnd",Plugin.cmd_dnd,
        "/dnd [-to jid] [-keep | -clear] [-priority n] [description]",
        "Set availability to 'do not disturb' with optional description."
        " '-to' option directs the presence to given user,"
        " '-keep' forces keeping current status description,"
        " '-clear' clears it, '-priority' allows setting the priority"
        " to an integer in range -128 to 127.",
        ("-to jid","-keep","-clear","-priority opaque","text")),
    ui.Command("offline",Plugin.cmd_offline,
        "/dnd [-to jid] [-keep | -clear] [description]",
        "Set availability to 'offline' with optional description."
        " '-to' option directs the presence to given user,"
        " '-keep' forces keeping current status description,"
        " '-clear' clears it",
        ("-to jid","-keep","-clear","text")),

    ui.CommandAlias("busy","dnd"),
    ui.Command("chatready",Plugin.cmd_chatready,
        "/chatready [-to jid] [-keep | -clear] [-priority n] [description]",
        "Set availability to 'ready for a chat' with optional description."
        " '-to' option directs the presence to given user,"
        " '-keep' forces keeping current status description,"
        " '-clear' clears it, '-priority' allows setting the priority"
        " to an integer in range -128 to 127.",
        ("-to jid","-keep","-clear","-priority opaque","text")),
    ui.Command("subscribe",Plugin.cmd_subscribe,
        "/subscribe user",
        "Subscribe to user's presence",
        ("user",)),
    ui.Command("unsubscribe",Plugin.cmd_unsubscribe,
        "/unsubscribe user",
        "Unsubscribe from user's presence (this doesn't remove user from roster)",
        ("user",)),
    ui.Command("cancel",Plugin.cmd_cancel,
        "/cancel user",
        "Cancel user's subscription to your presence",
        ("user",)),
    )).install()
# vi: sts=4 et sw=4
