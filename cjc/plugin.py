
class PluginBase:
	def __init__(self,cjc):
		self.cjc=cjc
		self.info=cjc.info
		self.debug=cjc.debug
		self.warning=cjc.warning
		self.error=cjc.error

	def session_started(self,stream):
		pass

	def session_ended(self,stream):
		pass
