
import curses

from widget import Widget
from cjc import common

class StatusBar(Widget):
    def __init__(self,theme_manager,format,dict):
        Widget.__init__(self)
        self.theme_manager=theme_manager
        self.format=format
        self.dict=dict
        self.current_content=None

    def get_height(self):
        return 1

    def get_dict(self):
        return self.dict

    def set_parent(self,parent):
        Widget.set_parent(self,parent)
        self.screen.lock.acquire()
        try:
            self.win=curses.newwin(self.h,self.w,self.y,self.x)
            self.win.leaveok(1)
            self.win.bkgdset(ord(" "),self.theme_manager.attrs["bar"])
        finally:
            self.screen.lock.release()

    def update(self,now=1,redraw=0):
        self.screen.lock.acquire()
        try:
            content=self.theme_manager.format_string(self.format,self.dict)
            if content==self.current_content and not redraw:
                return
            self.current_content=content
            self.win.move(0,0)
            x=0
            for attr,s in content:
                s=s.replace("\n"," ").replace("\r"," ").replace("\t"," ").replace("\f"," ")
                x+=len(s)
                if x>=self.w:
                    s=s[:-(x-self.w+1)]
                s=s.encode(self.screen.encoding,"replace")
                self.win.addstr(s,attr)
                if x>=self.w:
                    break
            self.win.clrtoeol()
            if now:
                self.win.refresh()
                self.screen.cursync()
            else:
                self.win.noutrefresh()
        finally:
            self.screen.lock.release()

# vi: sts=4 et sw=4
