
class PluginBase:
    def __init__(self,cjc):
        self.settings={}
        self.available_settings={}
        self.cjc=cjc
        self.info=cjc.info
        self.debug=cjc.debug
        self.warning=cjc.warning
        self.error=cjc.error

    def session_started(self,stream):
        pass

    def session_ended(self,stream):
        pass
# vi: sts=4 et sw=4
