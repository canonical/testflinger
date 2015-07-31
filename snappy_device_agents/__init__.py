# Copyright (C) 2015 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json


def get_test_opportunity(spi_file='spi_test_opportunity.json'):
    with open(spi_file, encoding='utf-8') as spi_json:
        test_opportunity = json.load(spi_json)
    # test_payload and image_reference may contain json in a string
    # XXX: This can be removed in the future when arbitrary json is
    # supported
    try:
        test_opportunity['test_payload'] = json.loads(
            test_opportunity['test_payload'])
    except:
        # If this fails, we simply leave the field alone
        pass
    try:
        test_opportunity['image_reference'] = json.loads(
            test_opportunity['image_reference'])
    except:
        # If this fails, we simply leave the field alone
        pass
    return test_opportunity
