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
from collections import OrderedDict
from pathlib import Path

from xdg_base_dirs import xdg_config_home


class TestflingerCliConfig:
    """TestflingerCliConfig class load values from files, env, and params"""

    def __init__(self, configfile: Path | None = None):
        if configfile is None:
            config_home = xdg_config_home()
            config_home.mkdir(parents=True, exist_ok=True)
            configfile = config_home / "testflinger-cli.conf"
        self.configfile = Path(configfile)

        config = configparser.ConfigParser()
        config.read(configfile)
        try:
            self.data = OrderedDict(config["testflinger-cli"])
        except KeyError:
            # Default empty config in case there's no config file
            self.data = OrderedDict()

    def get(self, key, default=None):
        """Get config item"""
        return self.data.get(key, default)

    def set(self, key, value):
        """Set config item"""
        self.data[key] = value
        self._save()

    def _save(self):
        """Save config back to the config file"""
        config = configparser.ConfigParser()
        config.read_dict({"testflinger-cli": self.data})
        with self.configfile.open(
            "w", encoding="utf-8", errors="ignore"
        ) as config_file:
            config.write(config_file)
