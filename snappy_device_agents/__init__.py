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

import bz2
import gzip
import json
import logging
import lzma
import netifaces
import os
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import time
import urllib.request

IMAGEFILE = 'snappy.img'

logger = logging.getLogger()


class TimeoutError(Exception):
    pass


def get_test_opportunity(job_data='testflinger.json'):
    """
    Read the json test opportunity data from testflinger.json.

    :param job_data:
        Filename and path of the json data if not the default
    :return test_opportunity:
        Dictionary of values read from the json file
    """
    with open(job_data, encoding='utf-8') as job_data_json:
        test_opportunity = json.load(job_data_json)
    return test_opportunity


def filetype(filename):
    magic_headers = {
        b"\x1f\x8b\x08": "gz",
        b"\x42\x5a\x68": "bz2",
        b"\xfd\x37\x7a\x58\x5a\x00": "xz"}
    with open(filename, 'rb') as f:
        filehead = f.read(1024)
    filetype = "unknown"
    for k, v in magic_headers.items():
        if filehead.startswith(k):
            filetype = v
            break
    return filetype


def download(url, filename=None):
    """
    Download the at the specified URL

    :param url:
        URL of the file to download
    :param filename:
        Filename to save the file as, defaults to the basename from the url
    :return filename:
        Filename of the downloaded snappy core image
    """
    logger.info('Downloading file from %s', url)
    if filename is None:
        filename = os.path.basename(url)
    urllib.request.urlretrieve(url, filename)
    return filename


def delayretry(func, args, max_retries=3, delay=0):
    """
    Retry the called function with a delay inserted between attempts

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
        except:
            time.sleep(delay)
            if retry_count == max_retries-1:
                raise
            continue
        return ret


def udf_create_image(params):
    """
    Create a new snappy core image with ubuntu-device-flash

    :param params:
        Command-line parameters to pass after 'sudo ubuntu-device-flash'
    :return filename:
        Returns the filename of the image
    """
    imagepath = os.path.join(os.getcwd(), IMAGEFILE)
    cmd = params.split()
    cmd.insert(0, 'ubuntu-device-flash')
    cmd.insert(0, 'sudo')

    # A shorter tempdir path is needed than the one provided by SPI
    # because of a bug in kpartx that makes it have trouble deleting
    # mappings with long paths
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_imagepath = os.path.join(tmpdir, IMAGEFILE)
        try:
            output_opt = cmd.index('-o')
            cmd[output_opt + 1] = imagepath
        except:
            # if we get here, -o was already not in the image
            cmd.append('-o')
            cmd.append(tmp_imagepath)

        logger.info('Creating snappy image with: %s', cmd)
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logger.error('Image Creation Output:\n %s', e.output)
            raise
        logger.info('Image Creation Output:\n %s', output)
        shutil.move(tmp_imagepath, imagepath)

    return(imagepath)


def get_test_username(job_data='testflinger.json'):
    """
    Read the json data for a test opportunity from SPI and return the
    username in specified for the test image (default: ubuntu)

    :return username:
        Returns the test image username
    """
    testflinger_data = get_test_opportunity(job_data)
    return testflinger_data.get('test_data').get('test_username', 'ubuntu')


def get_test_password(job_data='testflinger.json'):
    """
    Read the json data for a test opportunity from SPI and return the
    password in specified for the test image (default: ubuntu)

    :return password:
        Returns the test image password
    """
    testflinger_data = get_test_opportunity(job_data)
    return testflinger_data.get('test_data').get('test_password', 'ubuntu')


def get_image(job_data='testflinger.json'):
    """
    Read the json data for a test opportunity from SPI and retrieve or
    create the requested image.

    :return compressed_filename:
        Returns the filename of the compressed image, or empty string if
        there was an error
    """
    testflinger_data = get_test_opportunity(job_data)
    image_keys = testflinger_data.get('provision_data').keys()
    if 'download_files' in image_keys:
        for url in testflinger_data.get(
                'provision_data').get('download_files'):
                    download(url)
    if 'url' in image_keys:
        try:
            url = testflinger_data.get('provision_data').get('url')
            image = download(url, IMAGEFILE)
        except Exception as e:
            logger.error('Error getting "%s": %s', url, e)
            return ''
    elif 'udf-params' in image_keys:
        udf_params = testflinger_data.get('provision_data').get('udf-params')
        image = delayretry(udf_create_image, [udf_params],
                           max_retries=3, delay=60)
    else:
        logger.error('provision_data needs to contain "url" for the image '
                     'or "udf-params"')
        return ''
    return compress_file(image)


def get_local_ip_addr():
    """
    Return our default IP address for another system to connect to

    :return ip:
        Returns the ip address of this system
    """
    gateways = netifaces.gateways()
    default_interface = gateways['default'][netifaces.AF_INET][1]
    ip = netifaces.ifaddresses(default_interface)[netifaces.AF_INET][0]['addr']
    return ip


def serve_file(q, filename):
    """
    Wait for a connection, then send the specified file one time

    :param q:
        multiprocessing queue used to send the port number back
    :param filename:
        The file to transmit
    """
    server = socket.socket()
    server.bind(("0.0.0.0", 0))
    port = server.getsockname()[1]
    q.put(port)
    server.listen(1)
    (client, addr) = server.accept()
    with open(filename, mode='rb') as f:
        while True:
            data = f.read(16 * 1024 * 1024)
            if not data:
                break
            client.send(data)
    client.close()
    server.close()


def compress_file(filename):
    """
    Gzip the specified file, return the filename of the compressed image

    :param filename:
        The file to compress
    :return compressed_filename:
        The filename of the compressed file
    """
    compressed_filename = "{}.xz".format(filename)
    try:
        # Remove the compressed_filename if it exists, just in case
        os.unlink(compressed_filename)
    except FileNotFoundError:
        pass
    if filetype(filename) is 'xz':
        # just hard link it so we can unlink later without special handling
        os.rename(filename, compressed_filename)
    elif filetype(filename) is 'gz':
        with lzma.open(compressed_filename, 'wb') as compressed_image:
            with gzip.GzipFile(filename, 'rb') as old_compressed:
                shutil.copyfileobj(old_compressed, compressed_image)
    elif filetype(filename) is 'bz2':
        with lzma.open(compressed_filename, 'wb') as compressed_image:
            with bz2.BZ2File(filename, 'rb') as old_compressed:
                shutil.copyfileobj(old_compressed, compressed_image)
    else:
        # filetype is 'unknown' so assumed to be raw image
        with open(filename, 'rb') as uncompressed_image:
            with lzma.open(compressed_filename, 'wb') as compressed_image:
                shutil.copyfileobj(uncompressed_image, compressed_image)
    try:
        # Remove the original file, unless we already did
        os.unlink(filename)
    except FileNotFoundError:
        pass
    return compressed_filename


def configure_logging(config):
    class AgentFilter(logging.Filter):
        def __init__(self, agent_name):
            super(AgentFilter, self).__init__()
            self.agent_name = agent_name

        def filter(self, record):
            record.agent_name = self.agent_name
            return True

    logging.basicConfig(
        format='%(asctime)s %(agent_name)s %(levelname)s: '
               'DEVICE AGENT: '
               '%(message)s')
    agent_name = config.get('agent_name', "")
    logger.addFilter(AgentFilter(agent_name))
    logstash_host = config.get('logstash_host', None)

    if logstash_host is not None:
        try:
            import logstash
        except ImportError:
            print(
                'Install python-logstash if you want to use logstash logging')
        else:
            logger.addHandler(logstash.LogstashHandler(logstash_host, 5959, 1))


def logmsg(level, msg, *args, **kwargs):
    """
    Front end to logging that splits messages into 4096 byte chunks

    :param level:
        log level
    :param msg:
        log message
    :param args:
        args for filling message variables
    :param kwargs:
        key/value args, not currently used, but can be used through logging
    """

    if args:
        msg = msg % args
    logger.log(level, msg[:4096])
    if len(msg) > 4096:
        logmsg(level, msg[4096:])


def runcmd(cmd, env={}, timeout=None):
    """
    Run a command and stream the output to stdout

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
    env = {x: y for x, y in env.items() if y}

    if timeout:
        deadline = time.time() + timeout
    else:
        deadline = None
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               shell=True, env=env)
    while process.poll() is None:
        if deadline and time.time() > deadline:
            process.terminate()
            raise TimeoutError
        line = process.stdout.readline()
        if line:
            sys.stdout.write(line.decode(errors='replace'))
    line = process.stdout.read()
    if line:
        sys.stdout.write(line.decode(errors='replace'))
    return process.returncode


def run_test_cmds(cmds, config=None, env={}):
    """
    Run the test commands provided
    This is just a frontend to determine the type of cmds we
    were passed and do the right thing with it

    :param cmds:
        Commands to run as a string or list of strings
    :param config:
        Config data for the device which can be used for filling templates
    :param env:
        Environment to pass when running the commands
    """

    if not env:
        env = os.environ.copy()
    config_env = config.get('env', {})
    env.update(config_env)
    if type(cmds) is list:
        return _run_test_cmds_list(cmds, config, env)
    elif type(cmds) is str:
        return _run_test_cmds_str(cmds, config, env)
    else:
        logmsg(logging.ERROR, "test_cmds field must be a list or string")
        return 1


def _process_cmds_template_vars(cmds, config=None):
    """
    Fill in templated values for test command string. Ignore any values
    in braces for which we don't have a config item.

    :param cmds:
        Commands to run as a list of strings
    :param config:
        Config data for the device which can be used for filling templates
    """
    class IgnoreUnknownFormatter(string.Formatter):
        def vformat(self, format_string, args, kwargs):
            tokens = []
            for (literal, field_name, spec, conv) in self.parse(format_string):
                # replace double braces if parse removed them
                literal = literal.replace('{', '{{').replace('}', '}}')
                # if parse didn't find field name in braces, just add the string
                if not field_name:
                    tokens.append(literal)
                else:
                    #if conf and spec are not defined, set to ''
                    conv = '!' + conv if conv else ''
                    spec = ':' + spec if spec else ''
                    # only consider field before index
                    field = field_name.split('[')[0].split('.')[0]
                    # If this field is one we've defined, fill template value
                    if field in kwargs:
                        tokens.extend([literal, '{', field_name, conv, spec, '}'])
                    else:
                        # If not, the use escaped braces to pass it through
                        tokens.extend([literal, '{{', field_name, conv, spec, '}}'])
            format_string = ''.join(tokens)
            return string.Formatter.vformat(self, format_string, args, kwargs)
    # Ensure config is a dict
    if not isinstance(config, dict):
        config = {}
    formatter = IgnoreUnknownFormatter()
    return formatter.format(cmds, **config)


def _run_test_cmds_list(cmds, config=None, env={}):
    """
    Run the test commands provided

    :param cmds:
        Commands to run as a list of strings
    :param config:
        Config data for the device which can be used for filling templates
    :param env:
        Environment to pass when running the commands
    :return returncode:
        Return 0 if everything succeeded, 4 if any command in the list
        failed, or 20 if there was a formatting error
    """

    exitcode = 0
    for cmd in cmds:
        # Settings from the device yaml configfile like device_ip can be
        # formatted in test commands like "foo {device_ip}"
        cmd = _process_cmds_template_vars(cmd, config)

        logmsg(logging.INFO, "Running: %s", cmd)
        rc = runcmd(cmd, env)
        if rc:
            exitcode = 4
            logmsg(logging.WARNING, "Command failed, rc=%d", rc)
    return exitcode


def _run_test_cmds_str(cmds, config=None, env={}):
    """
    Run the test commands provided

    :param cmds:
        Commands to run as a string
    :param config:
        Config data for the device which can be used for filling templates
    :param env:
        Environment to pass when running the commands
    :return returncode:
        Return the value of the return code from the script, or 20 if there
        was an error formatting the script
    """

    # If cmds doesn't specify an interpreter, pick a safe default
    if not cmds.startswith('#!'):
        cmds = "#!/bin/bash\n" + cmds

    cmds = _process_cmds_template_vars(cmds, config)
    with open('tf_cmd_script', mode='w', encoding='utf-8') as tf_cmd_script:
        tf_cmd_script.write(cmds)
    os.chmod('tf_cmd_script', 0o775)
    rc = runcmd('./tf_cmd_script', env)
    if rc:
        logmsg(logging.WARNING, "Tests failed, rc=%d", rc)
    return rc
