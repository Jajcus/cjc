
class PluginBase:
    def __init__(self,cjc):
        """
        Initialize the plugin.
        """
        self.settings={}
        self.available_settings={}
        self.cjc=cjc
        self.info=cjc.info
        self.debug=cjc.debug
        self.warning=cjc.warning
        self.error=cjc.error

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
