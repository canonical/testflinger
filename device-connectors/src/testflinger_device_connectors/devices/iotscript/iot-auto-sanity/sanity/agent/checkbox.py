import os
import time
from sanity.agent.cmd import syscmd
from sanity.agent.err import FAILED, SUCCESS
from sanity.agent.net import get_ip, check_net_connection
from sanity.agent.data import dev_data


def run_checkbox(con, cbox, runner_cfg, secure_id, desc):
    SCP_CMD = (
        'scp -v -o "UserKnownHostsFile=/dev/null" '
        '-o "StrictHostKeyChecking=no"'
    )

    ADDR = get_ip(con)
    if ADDR == FAILED:
        return {
            "code": FAILED,
            "mesg": f"{dev_data.project} auto sanity was failed,"
            f"target device DHCP failed.",
        }

    if check_net_connection(ADDR) == FAILED:
        return {
            "code": FAILED,
            "mesg": f"{dev_data.project} auto sanity was failed,"
            f"target device connection timeout.",
        }

    syscmd(
        f"sshpass -p  {dev_data.device_pwd} {SCP_CMD} {runner_cfg} "
        f"{dev_data.device_uname}@{ADDR}:~/"
    )
    con.write_con(f"sudo snap set {cbox} slave=disabled")
    con.write_con_no_wait(f"sudo {cbox}.checkbox-cli {runner_cfg}")

    while True:
        mesg = con.read_con()
        if f"file:///home/{dev_data.device_uname}/report.tar.xz" in mesg:
            syscmd(
                f"sshpass -p  {dev_data.device_pwd} {SCP_CMD} "
                f"{dev_data.device_uname}@{ADDR}:report.tar.xz ."
            )
            fileT = time.strftime("%Y%m%d%H%M")
            mailT = time.strftime("%Y/%m/%d %H:%M")

            if os.path.exists("report.tar.xz"):
                report_name = f"report-{fileT}.tar.xz"
                upload_command = (
                    f'checkbox.checkbox-cli submit -m "{desc}" '
                    f"{secure_id} {report_name}"
                )
                syscmd(f"mv report.tar.xz {report_name}")
                print(upload_command)
                syscmd(upload_command)
                print("auto sanity is finished")
                return {
                    "code": SUCCESS,
                    "mesg": f"{dev_data.project} run {runner_cfg},"
                    f" auto sanity was finished on {mailT}",
                    "log": report_name,
                }

            else:
                print("auto sanity is failed")

                return {
                    "code": FAILED,
                    "mesg": f"{dev_data.project} auto sanity was failed,"
                    f" checkbox report is missing. {mailT}",
                }
