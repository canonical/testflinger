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
import subprocess
import tempfile
import time
import urllib.request

IMAGEFILE = 'snappy.img'

logger = logging.getLogger()


def get_test_opportunity(spi_file='testflinger.json'):
    """
    Read the json test opportunity data from spi_test_opportunity.json.

    :param spi_file:
        Filename and path of the json data if not the default
    :return test_opportunity:
        Dictionary of values read from the json file
    """
    # PWL: TODO: probably get rid of this entire section = we should have all of it as real json already
    with open(spi_file, encoding='utf-8') as spi_json:
        test_opportunity = json.load(spi_json)
    # test_payload and image_reference may contain json in a string
    # XXX: This can be removed in the future when arbitrary json is
    # supported
    """
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
    """
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


def get_test_username(spi_file='testflinger.json'):
    """
    Read the json data for a test opportunity from SPI and return the
    username in specified for the test image (default: ubuntu)

    :return username:
        Returns the test image username
    """
    spi_data = get_test_opportunity(spi_file)
    return spi_data.get('test_data').get('test_username', 'ubuntu')


def get_test_password(spi_file='testflinger.json'):
    """
    Read the json data for a test opportunity from SPI and return the
    password in specified for the test image (default: ubuntu)

    :return password:
        Returns the test image password
    """
    spi_data = get_test_opportunity(spi_file)
    return spi_data.get('test_data').get('test_password', 'ubuntu')


def get_image(spi_file='testflinger.json'):
    """
    Read the json data for a test opportunity from SPI and retrieve or
    create the requested image.

    :return compressed_filename:
        Returns the filename of the compressed image
    """
    spi_data = get_test_opportunity(spi_file)
    image_keys = spi_data.get('provision_data').keys()
    if 'download_files' in image_keys:
        for url in spi_data.get('provision_data').get('download_files'):
            download(url)
    if 'url' in image_keys:
        image = download(spi_data.get('provision_data').get('url'),
                         IMAGEFILE)
    elif 'udf-params' in image_keys:
        udf_params = spi_data.get('provision_data').get('udf-params')
        image = delayretry(udf_create_image, [udf_params],
                           max_retries=3, delay=60)
    else:
        logging.error('provision_data needs to contain "url" for the image '
                      'or "udf-params"')
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
    compressed_filename = "{}.gz".format(filename)
    try:
        # If debug enabled in SPI, an older image could still be there
        os.unlink(compressed_filename)
    except:
        pass
    if filetype(filename) is 'gz':
        # just hard link it so we can unlink later without special handling
        os.link(filename, compressed_filename)
    elif filetype(filename) is 'bz2':
        with gzip.open(compressed_filename, 'wb') as compressed_image:
            with bz2.BZ2File(filename, 'rb') as old_compressed:
                shutil.copyfileobj(old_compressed, compressed_image)
    elif filetype(filename) is 'xz':
        with gzip.open(compressed_filename, 'wb') as compressed_image:
            with lzma.LZMAFile(filename, 'rb') as old_compressed:
                shutil.copyfileobj(old_compressed, compressed_image)
    else:
        # filetype is 'unknown' so assumed to be raw image
        with open(filename, 'rb') as uncompressed_image:
            with gzip.open(compressed_filename, 'wb') as compressed_image:
                shutil.copyfileobj(uncompressed_image, compressed_image)
    os.unlink(filename)
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
        format='%(asctime)s %(agent_name)s %(levelname)s: %(message)s')
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
