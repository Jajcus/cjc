import string
import curses

import pyxmpp

from cjc.plugin import PluginBase

theme_attrs=(
	("roster.available_", curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_BOLD, curses.A_BOLD),
	("roster.available_away", curses.COLOR_BLUE,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_BOLD),
	("roster.available_xa", curses.COLOR_GREEN,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_BOLD),
	("roster.available_chat", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_BOLD),
	("roster.unavailable", curses.COLOR_YELLOW,curses.COLOR_BLACK,curses.A_NORMAL, curses.A_NORMAL),
)

theme_formats=(
	("roster.group", "%(group)s:\n"),
	("roster.unavailable", "%[roster.unavailable] %(aflag)s%(sflag)s%(name)s (%(J:jid)s)\n"),
	("roster.available", "%[roster.available_%(show)s] %(aflag)s%(sflag)s%(name)s (%(J:jid)s)\n"),
)

class Plugin(PluginBase):
	def __init__(self,app):
		PluginBase.__init__(self,app)
		self.available_settings={
			"show": ("Which items show - list of 'available','unavailable','chat',"
					"'online','away','xa' or 'all'",list,None),
			}
		self.settings={"show":["all"]}
		app.add_info_handler("rostername",self.info_rostername)
		app.add_info_handler("rostergroups",self.info_rostergroups)
		app.add_event_handler("roster updated",self.ev_roster_updated)
		app.add_event_handler("presence changed",self.ev_presence_changed)
		app.theme_manager.set_default_attrs(theme_attrs)
		app.theme_manager.set_default_formats(theme_formats)

	def info_rostername(self,k,v):
		if not v:
			return None
			
		return "Roster name",v

	def info_rostergroups(self,k,v):
		if not v:
			return None
		return "Roster groups",string.join(v,",")

	def ev_roster_updated(self,evend,arg):
		self.update()

	def ev_presence_changed(self,event,arg):
		if self.cjc.roster:
			self.update()

	def write_item(self,item):
		jid=item.jid()
		name=item.name()
		if not name:
			name=jid.as_unicode()
		if jid.resource:
			self.cjc.set_user_info(jid,"rostername",name)
		else:
			self.cjc.set_bare_user_info(jid,"rostername",name)
		p={"name":name,"jid":jid}
		pr=self.cjc.get_user_info(jid,"presence")
		if not pr or pr.get_type() and pr.get_type()!="available":
			available=0
		else:
			available=1
			show=pr.get_show()
			if not show:
				show=""
			p["show"]=show
		ask=item.ask()
		p["ask"]=ask
		if not ask:
			p["aflag"]=" "
		elif ask=="unsubscribe":
			p["aflag"]="-"
		else:
			p["aflag"]="?"
		subs=item.subscription()
		p["subscription"]=subs
		if subs=="both":
			p["sflag"]=" "
		elif subs=="from":
			p["sflag"]="<"
		elif subs=="to":
			p["sflag"]=">"
		else:
			p["sflag"]="-"
			
		if available:
			self.cjc.roster_buf.append_themed("roster.available",p)
		else:
			self.cjc.roster_buf.append_themed("roster.unavailable",p)

	def update(self):
		self.cjc.roster_buf.clear()
		groups=self.cjc.roster.groups()
		groups.sort()
		for group in groups:
			if group:
				p={"group":group}
			else:
				p={"group":"unfiled"}
			self.cjc.roster_buf.append_themed("roster.group",p)
			for item in self.cjc.roster.items_by_group(group):
				self.write_item(item)
		self.cjc.roster_buf.redraw()

	def session_started(self,stream):
		self.cjc.request_roster()
