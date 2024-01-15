import serial
import time
import os
from sanity.agent.cmd import syscmd


class console:
    con = None
    device_uname = ""

    # record log
    RECORD = False
    LOG = ""

    def __init__(self, uname, com_port="/dev/ttyUSB0", brate=115200):
        global con
        global RECORD
        global device_uname
        RECORD = False
        device_uname = uname

        try:
            os.stat(com_port)
        except OSError:
            raise SystemExit("{} not exist".format(com_port))

        while True:
            try:
                syscmd("sudo chmod 666 " + com_port)
                con = serial.Serial(
                    port=com_port,
                    baudrate=brate,
                    stopbits=serial.STOPBITS_ONE,
                    interCharTimeout=None,
                    timeout=5,
                )
                break
            except serial.SerialException as e:
                print("{} retrying.....".format(e))
                syscmd("fuser -k " + com_port)
                time.sleep(1)

    # due to command will not return "xxx@ubuntu"
    # we need to using different function to handle
    def write_con_no_wait(self, message=""):
        global con
        con.flushOutput()
        time.sleep(0.1)
        con.write(bytes((message + "\n").encode()))
        time.sleep(1)

    def wait_response(self):
        global device_uname
        res = ""
        while True:
            mesg = self.read_con()
            if mesg.find(device_uname + "@") != -1:
                return res
            res = res + "\n" + mesg

    def write_con(self, message=""):
        global con
        con.flushOutput()
        con.flushInput()
        con.write(bytes((message + "\n").encode()))
        time.sleep(1)
        mesg = self.wait_response()
        return mesg

    def record(self, enable):
        global RECORD
        global LOG
        if enable:
            LOG = ""
        else:
            with open("log.txt", "w") as file:
                file.write(LOG)

        RECORD = enable

    def read_con(self, HANDLE_EMPTY=True):
        global RECORD
        global LOG
        global con

        while True:
            mesg = (con.readline()).decode("utf-8", errors="ignore").strip()
            if HANDLE_EMPTY is False or mesg != "":
                break

        if RECORD:
            LOG = LOG + mesg + "\n"

        print(mesg)
        return mesg
