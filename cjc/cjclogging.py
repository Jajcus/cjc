
import logging

class UnicodeFormatter(logging.Formatter):
    def __init__(self,encoding,fmt=None,datefmt=None):
        logging.Formatter.__init__(self,fmt,datefmt)
        self.encoding=encoding
    def format(self,record):
        s=logging.Formatter.format(self,record)
        return s.encode(self.encoding,"replace")

class ScreenHandler(logging.Handler):
    def __init__(self,app,level=logging.NOTSET):
        logging.Handler.__init__(self,level=level)
        self.app=app
    def emit(self,record):
        msg=self.format(record)
        if record.levelno==logging.ERROR:
            self.app.show_error(msg)
        elif record.levelno==logging.WARNING:
            self.app.show_warning(msg)
        elif record.levelno==logging.DEBUG:
            self.app.show_debug(msg)
        else:
            self.app.show_info(msg)

# vi: sts=4 et sw=4
