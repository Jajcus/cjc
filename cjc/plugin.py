import logging

class PluginBase:
    def __init__(self,cjc,name):
        """
        Initialize the plugin.
        """
        self.settings={}
        self.available_settings={}
        self.cjc=cjc
        self.name=name
        self.module=None
        self.sys_path=None
        self.logger=logging.getLogger("cjc.plugin."+name)
        self.debug=self.logger.debug
        self.info=self.logger.info
        self.warning=self.logger.warning
        self.error=self.logger.error

    def unload(self):
        """
        Unregister every handler installed etc. and return True if the plugin
        may safely be unloaded.
        """
        return False

    def session_started(self,stream):
        """
        Stream-related plugin setup (stanza handler registration, etc).
        """
        pass

    def session_ended(self,stream):
        """
        Called when a session is closed (the stream has been disconnected).
        """
        pass

# vi: sts=4 et sw=4
