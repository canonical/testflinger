from sanity.agent.style import gen_head_string
from sanity.agent.deploy import login, boot_login, deploy
from sanity.agent.cmd import syscmd
from sanity.agent.err import FAILED


def start(plan, con):
    for stage in plan:
        if isinstance(stage, str):
            if stage == "login":
                print(gen_head_string("normal login"))
                login(con)
            elif stage == "run_login":
                print(gen_head_string("run mode login"))
                boot_login(con)
            elif stage == "reboot":
                con.write_con_no_wait("sudo reboot")
                boot_login(con)

        elif isinstance(stage, dict):
            if "initial_login" in stage.keys():
                print(gen_head_string("init login"))
                status = boot_login(
                    con,
                    stage["initial_login"].get("method"),
                    True,
                    stage["initial_login"].get("timeout", 600),
                )

                if status["code"] == FAILED:
                    break

            elif "reboot_install" in stage.keys():
                con.write_con_no_wait("sudo snap reboot --install")
                boot_login(
                    con,
                    stage["reboot_install"].get("method"),
                    True,
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
                    break
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
