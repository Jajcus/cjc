import string
from cjc.plugin import PluginBase
import pyxmpp

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
		p=self.cjc.get_user_info(jid,"presence")
		if not p or p.get_type() and p.get_type()!="available":
			attr="unavailable"
		else:
			show=p.get_show()
			if show in ("chat","away","xa"):
				attr=show
			else:
				attr="online"
		ask=item.ask()
		if not ask:
			aflag=" "
		elif ask=="unsubscribe":
			aflag="-"
		else:
			aflag="?"
		subs=item.subscription()
		if subs=="both":
			sflag=" "
		elif subs=="from":
			sflag="<"
		elif subs=="to":
			sflag=">"
		else:
			sflag="-"
		self.cjc.roster_buf.append_line(u"%c%c%s (%s)" % (
					aflag,sflag,name,jid.as_unicode()),attr)

	def update(self):
		self.cjc.roster_buf.clear()
		groups=self.cjc.roster.groups()
		groups.sort()
		for group in groups:
			if group:
				self.cjc.roster_buf.append(group+u":\n","default")
			else:
				self.cjc.roster_buf.append(u"unfiled:\n","default")
			for item in self.cjc.roster.items_by_group(group):
				self.write_item(item)
		self.cjc.roster_buf.redraw()

	def session_started(self,stream):
		self.cjc.request_roster()
