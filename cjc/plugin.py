
class PluginBase:
	def __init__(self,cjc):
		self.cjc=cjc
		self.info=cjc.info
		self.debug=cjc.debug
		self.warning=cjc.warning
		self.error=cjc.error
		self.set_user_info=cjc.set_user_info
		self.set_bare_user_info=cjc.set_bare_user_info
		self.get_user_info=cjc.get_user_info
		self.get_bare_user_info=cjc.get_bare_user_info
		self.stream=None

	def session_started(self,stream):
		self.stream=stream

	def session_ended(self,stream):
		self.stream=None
