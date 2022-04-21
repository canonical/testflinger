# Copyright (C) 2020-2022 Canonical
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

"""
Testflinger config module
"""

import configparser
import os
from collections import OrderedDict
import xdg


class TestflingerCliConfig:
    """TestflingerCliConfig class load values from files, env, and params"""
    def __init__(self, configfile=None):
        config = configparser.ConfigParser()
        if not configfile:
            os.makedirs(xdg.XDG_CONFIG_HOME, exist_ok=True)
            configfile = os.path.join(
                xdg.XDG_CONFIG_HOME, "testflinger-cli.conf")
        config.read(configfile)
        # Default empty config in case there's no config file
        self.data = OrderedDict()
        if 'testflinger-cli' in config.sections():
            self.data = OrderedDict(config['testflinger-cli'])
        self.configfile = configfile

    def get(self, key):
        """Get config item"""
        return self.data.get(key)

    def set(self, key, value):
        """Set config item"""
        self.data[key] = value
        self._save()

    def _save(self):
        """Save config back to the config file"""
        config = configparser.ConfigParser()
        config.read_dict({'testflinger-cli': self.data})
        with open(self.configfile, 'w', encoding='utf-8',
                  errors='ignore') as config_file:
            config.write(config_file)
