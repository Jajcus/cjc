
import threading
import locale
import curses
import logging

from cjc import common
import buffer
import cmdtable
import keytable
import complete

class Screen:
    def __init__(self,screen):
        self.__logger=logging.getLogger("cjc.ui.Screen")
        self.scr=screen
        self.screen=self
        self.attrs={}
        self.pairs={}
        self.next_pair=1
        self.content=None
        self.active_window=None
        self.windows=[]
        self.input_handler=None
        self.escape=0
        self.lock=threading.RLock()
        lc,self.encoding=locale.getlocale()
        if self.encoding is None:
            self.encoding="us-ascii"
        keytable.activate("screen",self,input_window=self.scr)
        cmdtable.activate("screen",self)
        complete.ActiveBufferDefinedCompletion(self).register("text")

    def set_background(self,char,attr):
        self.lock.acquire()
        try:
            if attr is not None:
                self.scr.bkgdset(ord(char),attr)
            else:
                self.scr.bkgdset(ord(char))
        finally:
            self.lock.release()

    def size(self):
        self.lock.acquire()
        try:
            h,w=self.scr.getmaxyx()
        finally:
            self.lock.release()
        return w,h

    def set_content(self,widget):
        self.content=widget
        self.windows=[]
        widget.set_parent(self)
        for b in buffer.buffer_list:
            if b is None:
                continue
            if b.window and b.window not in self.windows:
                b.set_window(None)

    def place(self,child):
        w,h=self.size()
        if child is self.content:
            return 0,0,w,h
        raise "%r is not a child of mine" % (child,)

    def update(self,now=0,redraw=0):
        self.lock.acquire()
        try:
            if redraw:
                self.scr.clear()
                self.scr.noutrefresh()
            if self.content:
                self.content.update(0,redraw)
            elif not redraw:
                self.scr.erase()
            if now:
                curses.doupdate()
                self.screen.cursync()
        finally:
            self.lock.release()

    def redraw(self):
        self.update(1,1)

    def _beep(self):
        try:
            curses.beep()
        except curses.error:
            pass

    def beep(self):
        self.lock.acquire()
        try:
            self._beep()
        finally:
            self.lock.release()

    def set_input_handler(self,h):
        self.input_handler=h

    def set_resize_handler(self,h):
        self.resize_handler=h

    def add_window(self,win):
        if not self.windows:
            win.set_active(1)
            self.active_window=win
        self.windows.append(win)
        self.lock.acquire()
        try:
            curses.doupdate()
        finally:
            self.lock.release()

    def focus_window(self,win):
        if not win or win is self.active_window:
            return

        self.active_window.set_active(0)
        win.set_active(1)
        self.active_window=win
        self.lock.acquire()
        try:
            curses.doupdate()
        finally:
            self.lock.release()

    def cmd_next(self,args=None):
        if len(self.windows)<=1:
            return

        for i in range(0,len(self.windows)):
            if self.windows[i] is self.active_window:
                if i==len(self.windows)-1:
                    win=self.windows[0]
                else:
                    win=self.windows[i+1]
                self.focus_window(win)
                break

    def cmd_prev(self,args=None):
        if len(self.windows)<=1:
            return

        for i in range(0,len(self.windows)):
            if self.windows[i] is self.active_window:
                if i==0:
                    win=self.windows[-1]
                else:
                    win=self.windows[i-1]
                self.focus_window(win)
                break

    def cmd_nextbuf(self,args=None):
        if args:
            args.finish()
        if not self.active_window:
            self.beep()
            return
        buf=self.active_window.buffer
        next=None
        wasbuf=0
        for b in buffer.buffer_list:
            if b is None:
                continue
            if b is buf:
                wasbuf=1
                continue
            if b.window:
                continue
            if not wasbuf and not next:
                next=b
                continue
            if wasbuf:
                next=b
                break
        if next:
            self.active_window.set_buffer(next)
            self.active_window.update()
        else:
            self.beep()

    def cmd_prevbuf(self,args=None):
        if args:
            args.finish()
        if args:
            args.finish()
        if not self.active_window:
            self.beep()
            return
        buf=self.active_window.buffer
        next=None
        wasbuf=0
        lst=list(buffer.buffer_list)
        lst.reverse()
        for b in lst:
            if b is None:
                continue
            if b is buf:
                wasbuf=1
                continue
            if b.window:
                continue
            if not wasbuf and not next:
                next=b
                continue
            if wasbuf:
                next=b
                break
        if next:
            self.active_window.set_buffer(next)
            self.active_window.update()
        else:
            self.beep()

    def cmd_move(self,args):
        num1=args.shift()
        if not num1:
            self.beep()
            return
        num2=args.shift()
        if num2:
            oldnum,newnum=int(num1),int(num2)
        else:
            if not self.active_window or not self.active_window.buffer:
                self.self()
                return
            newnum=int(num1)
            oldnum=self.active_window.buffer.get_number()
        buffer.move(oldnum,newnum)

    def cmd_beep(self,args):
        self.beep()

    def cursync(self):
        if self.input_handler:
            self.input_handler.cursync()

    def user_input(self,s):
        try:
            self.do_user_input(s)
        except common.non_errors:
            raise
        except:
            self.__logger.exception("Exception during user input processing")

    def do_user_input(self,s):
        if not s:
            return
        if not s.startswith(u"/"):
            if s.startswith(u"\\") and s[1:2] in ("\\","/",""):
                s=s[1:]
            if self.active_window and self.active_window.user_input(s):
                return
            return
        cmd=s[1:]
        if not cmd:
            return
        s=cmd.split(None,1)
        if len(s)>1:
            cmd,args=s
        else:
            cmd,args=s[0],None
        args=cmdtable.CommandArgs(args)
        cmdtable.run_command(cmd,args)

    def display_buffer(self,buffer):
        if buffer.window:
            return buffer.window
        if self.active_window and not self.active_window.locked:
            self.active_window.set_buffer(buffer)
            self.active_window.update()
            return self.active_window
        for w in self.windows:
            if not w.locked:
                w.set_buffer(buffer)
                w.update()
                return w
        return None

keytable.KeyTable("screen",20,(
        keytable.KeyBinding("command(next)","M-^I"),
        keytable.KeyFunction("redraw-screen",Screen.redraw,"Redraw the screen","^L"),
    )).install()

cmdtable.CommandTable("screen",90,(
    cmdtable.Command("next",Screen.cmd_next,
        "/next",
        "Change active window to the next one"),
    cmdtable.Command("prev",Screen.cmd_prev,
        "/previous",
        "Change active window to the previous one"),
    cmdtable.Command("nextbuf",Screen.cmd_nextbuf,
        "/nextbuf",
        "Change buffer in active window to next available"),
    cmdtable.Command("prevbuf",Screen.cmd_prevbuf,
        "/nextbuf",
        "Change buffer in active window to next available"),
    cmdtable.Command("move",Screen.cmd_move,
        "/move [oldnumber] number",
        "Change buffer order"),
    cmdtable.Command("beep",Screen.cmd_beep,
        "/beep",
        "Makes the terminal 'beep'"),
    )).install()
# vi: sts=4 et sw=4
