# Copyright (C) 2020 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import configparser
import os
import xdg
from collections import OrderedDict


class TestflingerCliConfig:
    def __init__(self, configfile=None):
        config = configparser.ConfigParser()
        if not configfile:
            configfile = os.path.join(
                xdg.XDG_CONFIG_HOME, "testflinger-cli.conf")
        config.read(configfile)
        # Default empty config in case there's no config file
        self.data = OrderedDict()
        if 'testflinger-cli' in config.sections():
            self.data = OrderedDict(config['testflinger-cli'])
        self.configfile = configfile

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        self._save()

    def _save(self):
        config = configparser.ConfigParser()
        config.read_dict({'testflinger-cli': self.data})
        with open(self.configfile, 'w') as f:
            config.write(f)
