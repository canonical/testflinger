import sys
import serial
from sanity.agent import agent
from sanity.agent.console import console
from sanity.agent.data import dev_data
from sanity.launcher.parser import LauncherParser


def start_agent(cfg):
    lanncher_parser = LauncherParser(cfg)
    launcher_data = lanncher_parser.data

    if "config" not in launcher_data.keys():
        print("No CFG in your plan, please read the README")
        sys.exit()

    cfg_data = launcher_data["config"]

    dev_data.project = cfg_data.get("project_name")
    dev_data.device_uname = cfg_data.get("username")
    dev_data.device_pwd = cfg_data.get("password")
    con = console(
        dev_data.device_uname,
        cfg_data["serial_console"]["port"],
        cfg_data["serial_console"]["baud_rate"],
    )
    dev_data.IF = cfg_data["network"]

    if cfg_data.get("hostname"):
        dev_data.hostname = cfg_data.get("hostname")

    try:
        agent.start(launcher_data.get("run_stage"), con)
    except serial.SerialException as e:
        print(
            "device disconnected or multiple access on port?"
            " error code {}".format(e)
        )
