
import threading
from types import StringType,UnicodeType

from cjc import common
from input import InputError
import cmdtable

buffer_list=[]
activity_handlers=[]

class Buffer:
    def __init__(self,info,descr_format="default_buffer_descr",
            command_table=None,command_table_object=None):
        self.preference=10
        self.command_table=command_table
        self.command_table_object=command_table_object
        try:
            buffer_list[buffer_list.index(None)]=self
        except ValueError:
            buffer_list.append(self)
        if type(info) in (StringType,UnicodeType):
            self.info={"buffer_name": info}
        else:
            self.info=info
        self.info["buffer_num"]=self.get_number()
        self.info["buffer_descr"]=descr_format
        self.window=None
        self.lock=threading.RLock()
        self.active=0
        for f in activity_handlers:
            f()
        self.input_widget=None
        self.question_handler=None
        self.question_abort_handler=None
        self.question_handler_arg=None
        self.question=None

    def set_window(self,win):
        self.lock.acquire()
        try:
            self.window=win
            if win:
                self.activity(0)
            if self.command_table:
                if win:
                    cmdtable.activate(self.command_table,
                            self.command_table_object)
                else:
                    cmdtable.deactivate(self.command_table,
                            self.command_table_object)
        finally:
            self.lock.release()

    def update_info(self,info):
        self.info.update(info)
        if self.window:
            self.window.update_status(self.info)

    def close(self):
        self.active=0
        n=buffer_list.index(self)
        if self.window:
            window=self.window
            self.window=None
            common.debug("Buffer has window")
            i=n
            while i>0:
                i-=1
                if buffer_list[i] and not buffer_list[i].window:
                    common.debug("Setting window's buffer to "+`buffer_list[i]`)
                    window.set_buffer(buffer_list[i])
                    window.update()
                    window=None
                    break
            if window:
                window.set_buffer(None)
                window.update()
                window=None
        buffer_list[n]=None
        for f in activity_handlers:
            f()

    def get_number(self):
        return buffer_list.index(self)+1

    def format(self,width,height):
        pass

    def update(self,now=1):
        window=self.window
        if window:
            window.update(now)

    def redraw(self,now=1):
        window=self.window
        if window:
            window.redraw(now)

    def user_input(self,s):
        return 0

    def keypressed(self,ch,escape):
        return 0

    def activity(self,val):
        if self.window and self.active>0:
            self.active=0
        elif val>self.active and not self.window:
            self.active=val
        else:
            return
        for f in activity_handlers:
            f()

    def ask_question(self,question,type,default,handler,abort_handler,arg,
                                values=None,required=1):
        import text_input
        import bool_input
        import choice_input
        import list_input

        if abort_handler:
            abortable=1
        else:
            abortable=0
        if type=="text-single":
            self.input_widget=text_input.TextInput(abortable,required,default,0)
        elif type=="boolean":
            self.input_widget=bool_input.BooleanInput(abortable,required,default)
        elif type=="choice":
            if not values:
                raise InputError,"Values required for 'choice' input."
            self.input_widget=choice_input.ChoiceInput(abortable,required,default,values)
        elif type=="list-single":
            self.input_widget=list_input.ListInput(abortable,required,default,values)
        elif type=="list-multi":
            self.input_widget=list_input.ListInput(abortable,required,default,values,1)
        else:
            raise InputError,"Unknown input type: "+type
        self.question_handler=handler
        self.question_abort_handler=abort_handler
        self.question_handler_arg=arg
        self.question=question
        if self.window and self.window.active:
            self.window.screen.input_handler.current_buffer_changed(self)
        self.activity(2)

    def unask_question(self):
        self.question_handler=None
        self.question_abort_handler=None
        self.question_handler_arg=None
        self.question=None
        self.input_widget=None
        if self.window and self.window.active:
            self.window.screen.input_handler.current_buffer_changed(self)

def get_by_number(n):
    if n==0:
        n=10
    try:
        return buffer_list[n-1]
    except IndexError:
        return None

def move(oldnum,newnum):
    global buffer_list
    mn=max(oldnum,newnum)
    if mn>=len(buffer_list):
        buffer_list+=(mn-len(buffer_list))*[None]
    buffer_list[newnum-1],buffer_list[oldnum-1]=buffer_list[oldnum-1],buffer_list[newnum-1]
    if buffer_list[newnum-1]:
        buffer_list[newnum-1].update_info({"buffer_num":newnum})
    if buffer_list[oldnum-1]:
        buffer_list[oldnum-1].update_info({"buffer_num":oldnum})
    for f in activity_handlers:
        f()
# vi: sts=4 et sw=4
