# Copyright (C) 2016 Canonical
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

import logging
import json
import os
import requests
import subprocess
import sys
import time

from urllib.parse import urljoin

import testflinger_agent

logger = logging.getLogger()


def process_jobs():
    """Coordinate checking for new jobs and handling them if they exists"""
    TEST_PHASES = ['setup', 'provision', 'test']
    job_data = check_jobs()
    if not job_data:
        return
    logger.info("Starting job %s", job_data.get('job_id'))
    rundir = os.path.join(testflinger_agent.config.get('execution_basedir'),
                          job_data.get('job_id'))
    os.makedirs(rundir)
    # Dump the job data to testflinger.json in our execution directory
    with open(os.path.join(rundir, 'testflinger.json'), 'w') as f:
        json.dump(job_data, f)

    for phase in TEST_PHASES:
        run_test_phase(phase, rundir)


def check_jobs():
    """Check for new jobs for on the Testflinger server

    :return: Dict with job data, or None if no job found
    """
    try:
        server = testflinger_agent.config.get('server_address')
        if not server.lower().startswith('http'):
            server = 'http://' + server
        job_uri = urljoin(server, '/v1/job')
        logger.info(server)
        queue_list = testflinger_agent.config.get('job_queues')
        logger.debug("Requesting a job")
        job_request = requests.get(job_uri, params={'queue': queue_list})
        if job_request.content:
            return job_request.json()
        else:
            return None
    except Exception as e:
        logger.exception(e)
        # Wait a little extra before trying again
        time.sleep(60)


def run_test_phase(phase, rundir):
    cmd = testflinger_agent.config.get(phase+'_command')
    if not cmd:
        return
    phase_log = os.path.join(rundir, phase+'.log')
    logger.info('Running %s_command: %s' % (phase, cmd))
    run_with_log(cmd, phase_log, rundir)


def run_with_log(cmd, logfile, cwd=None):
    with open(logfile, 'w') as f:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   shell=True, cwd=cwd)
        while process.poll() is None:
            line = process.stdout.readline()
            if line:
                sys.stdout.write(line.decode())
                f.write(line.decode())
                f.flush()
        line = process.stdout.read()
        if line:
            sys.stdout.write(line.decode())
            f.write(line.decode())
