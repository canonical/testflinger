import schedule
import sys
import time
import threading
from sanity.agent.style import columns


class scheduler:
    WORK_FLAG = False
    last_line = 0

    def __init__(self, act):
        task = threading.Thread(target=self.schedule_task_runner)
        task.start()
        self.do_schedule(act)

    def schedule_task_runner(self):
        while True:
            schedule.run_pending()
            time.sleep(10)

    def wakeup_work(self):
        global WORK_FLAG
        WORK_FLAG = True
        print("====scheduled work start====".center(columns))

    def do_schedule(self, act):
        global WORK_FLAG

        if len(act) < 2:
            print("Wrong PERIODIC format")
            sys.exit()

        match act.get("mode"):
            case "test":
                schedule.every().minute.do(self.wakeup_work)
            case "hour":
                schedule.every().hour.at(":00").do(self.wakeup_work)
            case "day":
                var = act.get("time", "00:00")
                schedule.every().day.at(var).do(self.wakeup_work)
            case "week":
                var = act.get("time", "00:00")

                match act.get("day"):
                    case "mon":
                        schedule.every().monday.at(act[3]).do(self.wakeup_work)
                    case "tue":
                        schedule.every().tuesday.at(act[3]).do(
                            self.wakeup_work
                        )
                    case "wed":
                        schedule.every().wednesday.at(act[3]).do(
                            self.wakeup_work
                        )
                    case "thu":
                        schedule.every().thursday.at(act[3]).do(
                            self.wakeup_work
                        )
                    case "fri":
                        schedule.every().friday.at(act[3]).do(self.wakeup_work)
                    case "sat":
                        schedule.every().saturday.at(act[3]).do(
                            self.wakeup_work
                        )
                    case "sun":
                        schedule.every().sunday.at(act[3]).do(self.wakeup_work)
                    case None:
                        print("unknown day " + act[2])
                        sys.exit()

        WORK_FLAG = False
        while WORK_FLAG is False:
            print(
                (
                    "====== Current time: {} Next job on: {} ======".format(
                        time.strftime("%Y-%m-%d  %H:%M"),
                        str(schedule.next_run()),
                    )
                ).center(columns),
                end="\r",
            )
            time.sleep(30)
