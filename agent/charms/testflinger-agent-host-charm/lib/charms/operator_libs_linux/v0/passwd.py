# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Simple library for managing Linux users and groups.

The `passwd` module provides convenience methods and abstractions around users and groups on a
Linux system, in order to make adding and managing users and groups easy.

Example of adding a user named 'test':

```python
import passwd
passwd.add_group(name='special_group')
passwd.add_user(username='test', secondary_groups=['sudo'])

if passwd.user_exists('some_user'):
    do_stuff()
```
"""

import grp
import logging
import pwd
from subprocess import STDOUT, check_output
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# The unique Charmhub library identifier, never change it
LIBID = "cf7655b2bf914d67ac963f72b930f6bb"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 4


def user_exists(user: Union[str, int]) -> Optional[pwd.struct_passwd]:
    """Check if a user exists.

    Args:
        user: username or gid of user whose existence to check

    Raises:
        TypeError: where neither a string or int is passed as the first argument
    """
    try:
        if type(user) is int:
            return pwd.getpwuid(user)
        elif type(user) is str:
            return pwd.getpwnam(user)
        else:
            raise TypeError("specified argument '%r' should be a string or int", user)
    except KeyError:
        logger.info("specified user '%s' doesn't exist", str(user))
        return None


def group_exists(group: Union[str, int]) -> Optional[grp.struct_group]:
    """Check if a group exists.

    Args:
        group: username or gid of user whose existence to check

    Raises:
        TypeError: where neither a string or int is passed as the first argument
    """
    try:
        if type(group) is int:
            return grp.getgrgid(group)
        elif type(group) is str:
            return grp.getgrnam(group)
        else:
            raise TypeError("specified argument '%r' should be a string or int", group)
    except KeyError:
        logger.info("specified group '%s' doesn't exist", str(group))
        return None


def add_user(
    username: str,
    password: Optional[str] = None,
    shell: str = "/bin/bash",
    system_user: bool = False,
    primary_group: str = None,
    secondary_groups: List[str] = None,
    uid: int = None,
    home_dir: str = None,
    create_home: bool = True,
) -> str:
    """Add a user to the system.

    Will log but otherwise succeed if the user already exists.

    Arguments:
        username: Username to create
        password: Password for user; if ``None``, create a system user
        shell: The default shell for the user
        system_user: Whether to create a login or system user
        primary_group: Primary group for user; defaults to username
        secondary_groups: Optional list of additional groups
        uid: UID for user being created
        home_dir: Home directory for user
        create_home: Force home directory creation

    Returns:
        The password database entry struct, as returned by `pwd.getpwnam`
    """
    try:
        if uid:
            user_info = pwd.getpwuid(int(uid))
            logger.info("user '%d' already exists", uid)
            return user_info
        user_info = pwd.getpwnam(username)
        logger.info("user with uid '%s' already exists", username)
        return user_info
    except KeyError:
        logger.info("creating user '%s'", username)

    cmd = ["useradd", "--shell", shell]

    if uid:
        cmd.extend(["--uid", str(uid)])
    if home_dir:
        cmd.extend(["--home", str(home_dir)])
    if password:
        cmd.extend(["--password", password])
    if create_home:
        cmd.append("--create-home")
    if system_user or password is None:
        cmd.append("--system")

    if not primary_group:
        try:
            grp.getgrnam(username)
            primary_group = username  # avoid "group exists" error
        except KeyError:
            pass

    if primary_group:
        cmd.extend(["-g", primary_group])
    if secondary_groups:
        cmd.extend(["-G", ",".join(secondary_groups)])

    cmd.append(username)
    check_output(cmd, stderr=STDOUT)
    user_info = pwd.getpwnam(username)
    return user_info


def add_group(group_name: str, system_group: bool = False, gid: int = None):
    """Add a group to the system.

    Will log but otherwise succeed if the group already exists.

    Args:
        group_name: group to create
        system_group: Create system group
        gid: GID for user being created

    Returns:
        The group's password database entry struct, as returned by `grp.getgrnam`
    """
    try:
        group_info = grp.getgrnam(group_name)
        logger.info("group '%s' already exists", group_name)
        if gid:
            group_info = grp.getgrgid(gid)
            logger.info("group with gid '%d' already exists", gid)
    except KeyError:
        logger.info("creating group '%s'", group_name)
        cmd = ["addgroup"]
        if gid:
            cmd.extend(["--gid", str(gid)])
        if system_group:
            cmd.append("--system")
        else:
            cmd.extend(["--group"])
        cmd.append(group_name)
        check_output(cmd, stderr=STDOUT)
        group_info = grp.getgrnam(group_name)
    return group_info


def add_user_to_group(username: str, group: str):
    """Add a user to a group.

    Args:
        username: user to add to specified group
        group: name of group to add user to

    Returns:
        The group's password database entry struct, as returned by `grp.getgrnam`
    """
    if not user_exists(username):
        raise ValueError("user '{}' does not exist".format(username))
    if not group_exists(group):
        raise ValueError("group '{}' does not exist".format(group))

    logger.info("adding user '%s' to group '%s'", username, group)
    check_output(["gpasswd", "-a", username, group], stderr=STDOUT)
    return grp.getgrnam(group)


def remove_user(user: Union[str, int], remove_home: bool = False) -> bool:
    """Remove a user from the system.

    Args:
        user: the username or uid of the user to remove
        remove_home: indicates whether the user's home directory should be removed
    """
    u = user_exists(user)
    if not u:
        logger.info("user '%s' does not exist", str(u))
        return True

    cmd = ["userdel"]
    if remove_home:
        cmd.append("-f")
    cmd.append(u.pw_name)

    logger.info("removing user '%s'", u.pw_name)
    check_output(cmd, stderr=STDOUT)
    return True


def remove_group(group: Union[str, int], force: bool = False) -> bool:
    """Remove a user from the system.

    Args:
        group: the name or gid of the group to remove
        force: force group removal even if it's the primary group for a user
    """
    g = group_exists(group)
    if not g:
        logger.info("group '%s' does not exist", str(g))
        return True

    cmd = ["groupdel"]
    if force:
        cmd.append("-f")
    cmd.append(g.gr_name)

    logger.info("removing group '%s'", g.gr_name)
    check_output(cmd, stderr=STDOUT)
    return True
