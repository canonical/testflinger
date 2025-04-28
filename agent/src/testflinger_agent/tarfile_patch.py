"""
Extends `TarFile` so that `extractall` supports filtering.

Uses a *minimal* subset of code from:
github.com/python/cpython/blob/3.8/Lib/tarfile.py
"""

import copy
import os
from tarfile import ExtractError, TarError, TarFile


class FilterError(TarError):
    pass


class AbsolutePathError(FilterError):
    def __init__(self, tarinfo):
        self.tarinfo = tarinfo
        super().__init__(f"member {tarinfo.name!r} has an absolute path")


class OutsideDestinationError(FilterError):
    def __init__(self, tarinfo, path):
        self.tarinfo = tarinfo
        self._path = path
        super().__init__(
            f"{tarinfo.name!r} would be extracted to {path!r}, "
            + "which is outside the destination"
        )


class SpecialFileError(FilterError):
    def __init__(self, tarinfo):
        self.tarinfo = tarinfo
        super().__init__(f"{tarinfo.name!r} is a special file")


class AbsoluteLinkError(FilterError):
    def __init__(self, tarinfo):
        self.tarinfo = tarinfo
        super().__init__(f"{tarinfo.name!r} is a link to an absolute path")


class LinkOutsideDestinationError(FilterError):
    def __init__(self, tarinfo, path):
        self.tarinfo = tarinfo
        self._path = path
        super().__init__(
            f"{tarinfo.name!r} would link to {path!r}, "
            + "which is outside the destination"
        )


def _get_filtered_attrs(member, dest_path, for_data=True):
    new_attrs = {}
    name = member.name
    dest_path = os.path.realpath(dest_path)
    # Strip leading / (tar's directory separator) from filenames.
    # Include os.sep (target OS directory separator) as well.
    if name.startswith(("/", os.sep)):
        name = new_attrs["name"] = member.path.lstrip("/" + os.sep)
    if os.path.isabs(name):
        # Path is absolute even after stripping.
        # For example, 'C:/foo' on Windows.
        raise AbsolutePathError(member)
    # Ensure we stay in the destination
    target_path = os.path.realpath(os.path.join(dest_path, name))
    if os.path.commonpath([target_path, dest_path]) != dest_path:
        raise OutsideDestinationError(member, target_path)
    # Limit permissions (no high bits, and go-w)
    mode = member.mode
    if mode is not None:
        # Strip high bits & group/other write bits
        mode = mode & 0o755
        if for_data:
            # For data, handle permissions & file types
            if member.isreg() or member.islnk():
                if not mode & 0o100:
                    # Clear executable bits if not executable by user
                    mode &= ~0o111
                # Ensure owner can read & write
                mode |= 0o600
            elif member.isdir() or member.issym():
                # Ignore mode for directories & symlinks
                mode = None
            else:
                # Reject special files
                raise SpecialFileError(member)
        if mode != member.mode:
            new_attrs["mode"] = mode
    if for_data:
        # Ignore ownership for 'data'
        if member.uid is not None:
            new_attrs["uid"] = None
        if member.gid is not None:
            new_attrs["gid"] = None
        if member.uname is not None:
            new_attrs["uname"] = None
        if member.gname is not None:
            new_attrs["gname"] = None
        # Check link destination for 'data'
        if member.islnk() or member.issym():
            if os.path.isabs(member.linkname):
                raise AbsoluteLinkError(member)
            if member.issym():
                target_path = os.path.join(
                    dest_path, os.path.dirname(name), member.linkname
                )
            else:
                target_path = os.path.join(dest_path, member.linkname)
            target_path = os.path.realpath(target_path)
            if os.path.commonpath([target_path, dest_path]) != dest_path:
                raise LinkOutsideDestinationError(member, target_path)
    return new_attrs


_KEEP = object()


def replace(
    tarinfo,
    *,
    name=_KEEP,
    mtime=_KEEP,
    mode=_KEEP,
    linkname=_KEEP,
    uid=_KEEP,
    gid=_KEEP,
    uname=_KEEP,
    gname=_KEEP,
    deep=True,
    _KEEP=_KEEP,  # noqa: N803
):
    """Return a deep copy of self with the given attributes replaced."""
    if deep:
        result = copy.deepcopy(tarinfo)
    else:
        result = copy.copy(tarinfo)
    if name is not _KEEP:
        result.name = name
    if mtime is not _KEEP:
        result.mtime = mtime
    if mode is not _KEEP:
        result.mode = mode
    if linkname is not _KEEP:
        result.linkname = linkname
    if uid is not _KEEP:
        result.uid = uid
    if gid is not _KEEP:
        result.gid = gid
    if uname is not _KEEP:
        result.uname = uname
    if gname is not _KEEP:
        result.gname = gname
    return result


def data_filter(member, dest_path):
    new_attrs = _get_filtered_attrs(member, dest_path, True)
    if new_attrs:
        return replace(member, **new_attrs, deep=False)
    return member


def fully_trusted_filter(member, dest_path):
    return member


class TarFilePatched(TarFile):
    def _get_extract_tarinfo(self, member, filter_function, path):
        """Get filtered TarInfo (or None) from member, which might be a str."""
        if isinstance(member, str):
            tarinfo = self.getmember(member)
        else:
            tarinfo = member

        unfiltered = tarinfo
        try:
            tarinfo = filter_function(tarinfo, path)
        except (OSError, FilterError) as e:
            self._handle_fatal_error(e)
        except ExtractError as e:
            self._handle_nonfatal_error(e)
        if tarinfo is None:
            self._dbg(2, "tarfile: Excluded %r" % unfiltered.name)
            return None
        # Prepare the link target for makelink().
        if tarinfo.islnk():
            tarinfo = copy.copy(tarinfo)
            tarinfo._link_target = os.path.join(path, tarinfo.linkname)
        return tarinfo

    def _extract_one(self, tarinfo, path, set_attrs, numeric_owner):
        """Extract from filtered tarinfo to disk."""
        self._check("r")

        try:
            self._extract_member(
                tarinfo,
                os.path.join(path, tarinfo.name),
                set_attrs=set_attrs,
                numeric_owner=numeric_owner,
            )
        except OSError as e:
            self._handle_fatal_error(e)
        except ExtractError as e:
            self._handle_nonfatal_error(e)

    def extractall(
        self,
        path=".",
        members=None,
        *,
        numeric_owner=False,
        filter=None,  # noqa: A002
    ):
        """Extract all members from the archive to the current working
        directory and set owner, modification time and permissions on
        directories afterwards. `path' specifies a different directory
        to extract to. `members' is optional and must be a subset of the
        list returned by getmembers(). If `numeric_owner` is True, only
        the numbers for user/group names are used and not the names.

        The `filter` function will be called on each member just
        before extraction.
        It can return a changed TarInfo or None to skip the member.
        String names of common filters are accepted.
        """
        directories = []

        filter_function = filter if filter else fully_trusted_filter
        if members is None:
            members = self

        for member in members:
            tarinfo = self._get_extract_tarinfo(member, filter_function, path)
            if tarinfo is None:
                continue
            if tarinfo.isdir():
                # For directories, delay setting attributes until later,
                # since permissions can interfere with extraction and
                # extracting contents can reset mtime.
                directories.append(tarinfo)
            self._extract_one(
                tarinfo,
                path,
                set_attrs=not tarinfo.isdir(),
                numeric_owner=numeric_owner,
            )

        # Reverse sort directories.
        directories.sort(key=lambda a: a.name, reverse=True)

        # Set correct owner, mtime and filemode on directories.
        for tarinfo in directories:
            dirpath = os.path.join(path, tarinfo.name)
            try:
                self.chown(tarinfo, dirpath, numeric_owner=numeric_owner)
                self.utime(tarinfo, dirpath)
                self.chmod(tarinfo, dirpath)
            except ExtractError as e:
                self._handle_nonfatal_error(e)

    def chmod(self, tarinfo, targetpath):
        """Set file permissions of targetpath according to tarinfo."""
        if tarinfo.mode is None:
            return
        try:
            os.chmod(targetpath, tarinfo.mode)
        except OSError as err:
            raise ExtractError("could not change mode") from err


# make sure `open` is available when this module is imported and it
# returns a `TarFilePatched` object instead of a `TarFile` one
# (`open` is "exported" in the same manner in the original source)
open = TarFilePatched.open  # noqa: A001
