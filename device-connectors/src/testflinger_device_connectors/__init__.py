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
"""General functions used by device connectors."""

import bz2
import gzip
import json
import logging
import lzma
import os
import shutil
import socket
import string
import subprocess
import sys
import time
import urllib.request

IMAGEFILE = "install.img"

logger = logging.getLogger(__name__)


class CmdTimeoutError(Exception):
    """Exception for timeout running running commands."""


def get_test_opportunity(job_data="testflinger.json"):
    """Read the json test opportunity data from testflinger.json.

    :param job_data:
        Filename and path of the json data if not the default
    :return test_opportunity:
        Dictionary of values read from the json file
    """
    with open(job_data, encoding="utf-8") as job_data_json:
        test_opportunity = json.load(job_data_json)
    return test_opportunity


def filetype(filename):
    """Attempt to determine the compression type of a specified file."""
    magic_headers = {
        b"\x1f\x8b\x08": "gz",
        b"\x42\x5a\x68": "bz2",
        b"\xfd\x37\x7a\x58\x5a\x00": "xz",
        b"\x51\x46\x49\xfb": "qcow2",
    }
    with open(filename, "rb") as checkfile:
        filehead = checkfile.read(1024)
    ftype = "unknown"
    for k, val in magic_headers.items():
        if filehead.startswith(k):
            ftype = val
            break
    return ftype


def download(url, filename=None):
    """Download the at the specified URL.

    :param url:
        URL of the file to download
    :param filename:
        Filename to save the file as, defaults to the basename from the url
    :return filename:
        Filename of the downloaded core image
    """
    logger.info("Downloading file from %s", url)
    if filename is None:
        filename = os.path.basename(url)
    urllib.request.urlretrieve(url, filename)
    return filename


def delayretry(func, args, max_retries=3, delay=0):
    """Retry the called function with a delay inserted between attempts.

    :param func:
        Function to retry
    :param args:
        List of args to pass to func()
    :param max_retries:
        Maximum number of times to retry
    :delay:
        Time (in seconds) to delay between attempts
    """
    for retry_count in range(max_retries):
        try:
            ret = func(*args)
        except Exception:
            time.sleep(delay)
            if retry_count == max_retries - 1:
                raise
            continue
        return ret


def get_test_username(job_data="testflinger.json", default="ubuntu"):
    """If the test_data specifies a default username, use it. Otherwise
    allow the provisioning method pick a default, or use ubuntu as a safe bet.

    :return username:
        Returns the test image username
    """
    testflinger_data = get_test_opportunity(job_data)
    try:
        user = testflinger_data["test_data"]["test_username"]
    except KeyError:
        user = default
    return user


def get_test_password(job_data="testflinger.json", default="ubuntu"):
    """If the test_data specifies a default password, use it. Otherwise
    allow the provisioning method pick a default, or use ubuntu as a safe bet.

    :return password:
        Returns the test image password
    """
    testflinger_data = get_test_opportunity(job_data)
    try:
        password = testflinger_data["test_data"]["test_password"]
    except KeyError:
        password = default
    return password


def get_image(job_data="testflinger.json"):
    """Read the json data for a test opportunity from SPI and retrieve or
    create the requested image.

    :return compressed_filename:
        Returns the filename of the compressed image, or empty string if
        there was an error
    """
    testflinger_data = get_test_opportunity(job_data)
    provision_data = testflinger_data.get("provision_data")
    if "url" not in provision_data:
        logger.error('provision_data needs to contain "url" for the image')
        return ""
    url = testflinger_data["provision_data"]["url"]
    try:
        image = download(url, IMAGEFILE)
    except OSError:
        logger.exception('Error getting "%s":', url)
        return ""
    return compress_file(image)


def get_local_ip_addr():
    """Return our default IP address for another system to connect to.

    :return ipaddr:
        Returns the ip address of this system
    """
    # Use SOCK_DGRAM since we don't need to send any data and to avoid timeout
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("10.0.0.0", 0))
        ipaddr = sock.getsockname()[0]
    return ipaddr


def serve_file(queue, filename):
    """Wait for a connection, then send the specified file one time.

    :param queue:
        multiprocessing queue used to send the port number back
    :param filename:
        The file to transmit
    """
    server = socket.socket()
    server.bind(("0.0.0.0", 0))  # noqa: S104
    port = server.getsockname()[1]
    queue.put(port)
    server.listen(1)
    (client, _) = server.accept()
    with open(filename, mode="rb") as imagefile:
        while True:
            data = imagefile.read(16 * 1024 * 1024)
            if not data:
                break
            client.send(data)
    client.close()
    server.close()


def compress_file(filename):
    """Gzip the specified file, return the filename of the compressed image.

    :param filename:
        The file to compress
    :return compressed_filename:
        The filename of the compressed file
    """
    compressed_filename = f"{filename}.xz"
    try:
        # Remove the compressed_filename if it exists, just in case
        os.unlink(compressed_filename)
    except FileNotFoundError:
        pass
    if filetype(filename) == "xz":
        # just hard link it so we can unlink later without special handling
        os.rename(filename, compressed_filename)
    elif filetype(filename) == "gz":
        with lzma.open(compressed_filename, "wb") as compressed_image:
            with gzip.GzipFile(filename, "rb") as old_compressed:
                shutil.copyfileobj(old_compressed, compressed_image)
    elif filetype(filename) == "bz2":
        with lzma.open(compressed_filename, "wb") as compressed_image:
            with bz2.BZ2File(filename, "rb") as old_compressed:
                shutil.copyfileobj(old_compressed, compressed_image)
    elif filetype(filename) == "qcow2":
        raw_filename = f"{filename}.raw"
        try:
            # Remove the original file, unless we already did
            os.unlink(raw_filename)
        except FileNotFoundError:
            pass
        cmd = ["qemu-img", "convert", "-O", "raw", filename, raw_filename]
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            logger.error("Image Conversion Output:\n %s", exc.output)
            raise
        with open(raw_filename, "rb") as uncompressed_image:
            with lzma.open(compressed_filename, "wb") as compressed_image:
                shutil.copyfileobj(uncompressed_image, compressed_image)
        os.unlink(raw_filename)
    else:
        # filetype is 'unknown' so assumed to be raw image
        with open(filename, "rb") as uncompressed_image:
            with lzma.open(compressed_filename, "wb") as compressed_image:
                shutil.copyfileobj(uncompressed_image, compressed_image)
    try:
        # Remove the original file, unless we already did
        os.unlink(filename)
    except FileNotFoundError:
        pass
    return compressed_filename


def configure_logging(config):
    """Set up logging."""

    class AgentFormatter(logging.Formatter):
        """Add agent_name to log records."""

        def __init__(self, fmt, agent_name):
            super().__init__(fmt)
            self.agent_name = agent_name

        def format(self, record):
            record.agent_name = self.agent_name
            return super().format(record)

    agent_name = config.get("agent_name", "")
    fmt = (
        "%(asctime)s %(agent_name)s %(levelname)s: DEVICE CONNECTOR: "
        "%(message)s"
    )
    formatter = AgentFormatter(fmt, agent_name)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def runcmd(cmd, env=None, timeout=None):
    """Run a command and stream the output to stdout.

    :param cmd:
        Command to run
    :param env:
        Environment to pass to Popen
    :param timeout:
        Seconds after which we should timeout
    :return returncode:
        Return value from running the command
    """
    # Sanitize the environment, eliminate null values or Popen may choke
    if not env:
        env = {}
    env = {x: y for x, y in env.items() if y}

    if timeout:
        deadline = time.time() + timeout
    else:
        deadline = None
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        env=env,
    ) as process:
        while process.poll() is None:
            if deadline and time.time() > deadline:
                process.terminate()
                raise CmdTimeoutError
            line = process.stdout.readline()
            if line:
                sys.stdout.write(line.decode(errors="replace"))
        line = process.stdout.read()
        if line:
            sys.stdout.write(line.decode(errors="replace"))
    return process.returncode


def run_test_cmds(cmds, config=None, env=None):
    """Run the test commands provided.

    This is just a frontend to determine the type of cmds we
    were passed and do the right thing with it.

    :param cmds:
        Commands to run as a string or list of strings
    :param config:
        Config data for the device which can be used for filling templates
    :param env:
        Environment to pass when running the commands
    """
    if not env:
        env = os.environ.copy()
    config_env = config.get("env", {})
    env.update(config_env)
    if isinstance(cmds, list):
        return _run_test_cmds_list(cmds, config, env)
    if isinstance(cmds, str):
        return _run_test_cmds_str(cmds, config, env)
    logger.error("test_cmds field must be a list or string")
    return 1


def _process_cmds_template_vars(cmds, config=None):
    """Fill in templated values for test command string. Ignore any values
    in braces for which we don't have a config item.

    :param cmds:
        Commands to run as a list of strings
    :param config:
        Config data for the device which can be used for filling templates
    """
    logger.warning("DEPRECATED - Detected use of double-braces in test_cmds")

    class IgnoreUnknownFormatter(string.Formatter):
        """Try to allow both double and single curly braces."""

        def vformat(self, format_string, args, kwargs):
            tokens = []
            for literal, field_name, spec, conv in self.parse(format_string):
                # replace double braces if parse removed them
                format_literal = literal.replace("{", "{{").replace("}", "}}")
                # if the field is {}, just add escaped empty braces
                if field_name == "":
                    tokens.extend([format_literal, "{{}}"])
                    continue
                # if field name was None, we just add the literal token
                if field_name is None:
                    tokens.extend([format_literal])
                    continue
                # if conf and spec are not defined, set to ''
                conv = "!" + conv if conv else ""  # noqa: PLW2901
                spec = ":" + spec if spec else ""  # noqa: PLW2901
                # only consider field before index
                field = field_name.split("[")[0].split(".")[0]
                # If this field is one we've defined, fill template value
                if field in kwargs:
                    tokens.extend(
                        [format_literal, "{", field_name, conv, spec, "}"]
                    )
                else:
                    # If not, the use escaped braces to pass it through
                    tokens.extend(
                        [format_literal, "{{", field_name, conv, spec, "}}"]
                    )
            format_string = "".join(tokens)
            return string.Formatter.vformat(self, format_string, args, kwargs)

    # Ensure config is a dict
    if not isinstance(config, dict):
        config = {}
    formatter = IgnoreUnknownFormatter()
    return formatter.format(cmds, **config)


def _run_test_cmds_list(cmds, config=None, env=None):
    """Run the test commands provided.

    :param cmds:
        Commands to run as a list of strings
    :param config:
        Config data for the device which can be used for filling templates
    :param env:
        Environment to pass when running the commands
    :return returncode:
        Return 0 if everything succeeded, or exit code from failed command
    """
    if not env:
        env = {}
    for cmd in cmds:
        # Settings from the device yaml configfile like device_ip can be
        # formatted in test commands like "foo {device_ip}"
        if "{{" in cmd:
            cmd = _process_cmds_template_vars(cmd, config)  # noqa: PLW2901

        logger.info("Running: %s", cmd)
        result = runcmd(cmd, env)
        if result:
            logger.warning("Command failed, rc=%d", result)
    return result


def _run_test_cmds_str(cmds, config=None, env=None):
    """Run the test commands provided.

    :param cmds:
        Commands to run as a string
    :param config:
        Config data for the device which can be used for filling templates
    :param env:
        Environment to pass when running the commands
    :return returncode:
        Return the value of the return code from the script
    """
    if not env:
        env = {}
    # If cmds doesn't specify an interpreter, pick a safe default
    if not cmds.startswith("#!"):
        cmds = "#!/bin/bash\n" + cmds

    if "{{" in cmds:
        cmds = _process_cmds_template_vars(cmds, config)
    with open("tf_cmd_script", mode="w", encoding="utf-8") as tf_cmd_script:
        tf_cmd_script.write(cmds)
    os.chmod("tf_cmd_script", 0o775)  # noqa: S103
    result = runcmd("./tf_cmd_script", env)
    if result:
        logger.warning("Tests failed, rc=%d", result)
    return result
