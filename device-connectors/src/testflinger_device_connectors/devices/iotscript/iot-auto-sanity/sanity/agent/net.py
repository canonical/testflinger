import time
import ipaddress
from sanity.agent.cmd import syscmd
from sanity.agent.err import FAILED, SUCCESS
from sanity.agent.data import dev_data


def get_ip(con):
    retry = 0

    while True:
        retry += 1
        try:
            ADDR = con.write_con(
                f'ip address show {dev_data.IF} | grep "inet " | '
                "head -n 1 | cut -d ' ' -f 6 | cut -d  \"/\" -f 1"
            )
            ADDR = ADDR.splitlines()[-1]
            ipaddress.ip_address(ADDR)
            return ADDR
        except Exception:
            if retry > 15:
                return FAILED

        time.sleep(1)


def check_net_connection(ADDR):
    retry = 0
    status = -1

    while status != 0:
        retry += 1
        if retry > 10:
            return FAILED

        status = syscmd("ping -c 1 " + ADDR)

    return SUCCESS
