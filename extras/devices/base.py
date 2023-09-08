import logging

logger = logging


class AbstractDevice:
    fw_update_type = ""
    vendor = ""

    def __init__(self, ipaddr, user, password):
        self.ipaddr = ipaddr
        self.user = user
        self.password = password
        self.fw_info = []

    def run_cmd(self):
        pass

    def get_fw_info(self):
        pass

    def upgrade(self):
        pass

    def downgrade(self):
        pass

    def check_results(self):
        pass

    def check_connectable(self):
        pass

    def reboot(self):
        pass
