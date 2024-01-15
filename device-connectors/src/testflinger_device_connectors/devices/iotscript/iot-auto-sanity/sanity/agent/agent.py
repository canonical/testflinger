import time
from sanity.agent.mail import mail
from datetime import datetime
from sanity.agent.style import gen_head_string
from sanity.agent.checkbox import run_checkbox
from sanity.agent.deploy import login, run_login, init_mode_login, deploy
from sanity.agent.cmd import syscmd
from sanity.agent.err import FAILED


def notify(status):
    code = status["code"]
    content = ""
    log_file = ""

    if "mesg" in status:
        content = status["mesg"]

    if "log" in status:
        log_file = status["log"]

    mail.send_mail(
        code,
        content,
        log_file,
    )


def start(plan, con, sched=None):
    while True:
        for stage in plan:
            if isinstance(stage, str):
                if stage == "login":
                    print(gen_head_string("normal login"))
                    login(con)
                elif stage == "run_login":
                    print(gen_head_string("run mode login"))
                    run_login(con)
                elif stage == "reboot":
                    con.write_con_no_wait("sudo reboot")
                    run_login(con)

            elif isinstance(stage, dict):
                if "initial_login" in stage.keys():
                    print(gen_head_string("init login"))
                    status = init_mode_login(
                        con,
                        stage["initial_login"].get("method"),
                        stage["initial_login"].get("timeout", 600),
                    )

                    if status["code"] == FAILED:
                        notify(status)
                        break

                elif "reboot_install" in stage.keys():
                    con.write_con_no_wait("sudo snap reboot --install")
                    init_mode_login(
                        con,
                        stage["reboot_install"].get("method"),
                        stage["reboot_install"].get("timeout", 600),
                    )

                elif "deploy" in stage.keys():
                    print(gen_head_string("deploy procedure"))
                    status = deploy(
                        con,
                        stage["deploy"].get("utility"),
                        stage["deploy"].get("method"),
                        stage["deploy"].get("update_boot_assets", False),
                        stage["deploy"].get("timeout", 600),
                    )

                    if status["code"] == FAILED:
                        notify(status)
                        break
                elif "checkbox" in stage.keys():
                    print(gen_head_string("run checkbox"))
                    status = run_checkbox(
                        con,
                        stage["checkbox"].get("snap_name"),
                        stage["checkbox"].get("launcher"),
                        stage["checkbox"].get("secure_id"),
                        stage["checkbox"].get(
                            "submission_description", "auto sanity test"
                        ),
                    )
                    notify(status)
                elif "eof_commands" in stage.keys():
                    print(gen_head_string("custom command start"))
                    for cmd in stage["eof_commands"]:
                        result = con.write_con(cmd.get("cmd"))
                        expected = cmd.get("expected", None)
                        if expected and expected not in result:
                            print("commands result unmatch expected")
                            break

                    print(gen_head_string("custom command end"))
                elif "sys_commands" in stage.keys():
                    print(gen_head_string("sys comand start"))
                    all_cmd = ";".join(
                        [cmd.strip() for cmd in stage["sys_commands"]]
                    )
                    print(all_cmd)
                    syscmd(all_cmd)
                    print(gen_head_string("sys comand end"))
        if sched:
            sched.WORK_FLAG = False
            while sched.WORK_FLAG is False:
                cur_time = datetime.now().strftime("%Y-%m-%d  %H:%M")
                output_str = (
                    f"Current time: {cur_time}  Next job on: "
                    f"{str(sched.next_run())}"
                )
                print(gen_head_string(output_str), end="\r")
                time.sleep(30)
        else:
            break
