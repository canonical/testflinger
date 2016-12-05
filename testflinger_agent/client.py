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
import shutil
import subprocess
import sys
import tempfile
import time

from urllib.parse import urljoin

import testflinger_agent

from testflinger_agent.errors import TFServerError

logger = logging.getLogger()


def process_jobs():
    """Coordinate checking for new jobs and handling them if they exists"""
    TEST_PHASES = ['setup', 'provision', 'test']

    # First, see if we have any old results that we couldn't send last time
    retry_old_results()

    job_data = check_jobs()
    while job_data:
        job_id = job_data.get('job_id')
        logger.info("Starting job %s", job_id)
        rundir = os.path.join(
            testflinger_agent.config.get('execution_basedir'), job_id)
        os.makedirs(rundir)
        # Dump the job data to testflinger.json in our execution directory
        with open(os.path.join(rundir, 'testflinger.json'), 'w') as f:
            json.dump(job_data, f)
        # Create json outcome file where phases will store their output
        with open(os.path.join(rundir, 'testflinger-outcome.json'), 'w') as f:
            json.dump({}, f)

        for phase in TEST_PHASES:
            # Try to update the job_state on the testflinger server
            try:
                post_result(job_id, {'job_state': phase})
            except TFServerError:
                pass
            exitcode = run_test_phase(phase, rundir)
            # exit code 46 is our indication that recovery failed!
            # In this case, we need to mark the device offline
            if exitcode == 46:
                testflinger_agent.mark_device_offline()
                repost_job(job_data)
                shutil.rmtree(rundir)
                # Return NOW so we don't keep trying to process jobs
                return
            if exitcode:
                logger.debug('Phase %s failed, aborting job' % phase)
                break
        try:
            transmit_job_outcome(rundir)
        except Exception as e:
            # TFServerError will happen if we get other-than-good status
            # Other errors can happen too for things like connection problems
            logger.exception(e)
            results_basedir = testflinger_agent.config.get('results_basedir')
            shutil.move(rundir, results_basedir)

        job_data = check_jobs()


def retry_old_results():
    """Retry sending results that we previously failed to send"""

    results_dir = testflinger_agent.config.get('results_basedir')
    # List all the directories in 'results_basedir', where we store the
    # results that we couldn't transmit before
    old_results = [os.path.join(results_dir, d)
                   for d in os.listdir(results_dir)
                   if os.path.isdir(os.path.join(results_dir, d))]
    for result in old_results:
        try:
            logger.info('Attempting to send result: %s' % result)
            transmit_job_outcome(result)
        except TFServerError:
            # Problems still, better luck next time?
            pass


def check_jobs():
    """Check for new jobs for on the Testflinger server

    :return: Dict with job data, or None if no job found
    """
    try:
        server = testflinger_agent.config.get('server_address')
        if not server.lower().startswith('http'):
            server = 'http://' + server
        job_uri = urljoin(server, '/v1/job')
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
    """Run the specified test phase in rundir

    :param phase:
        Name of the test phase (setup, provision, test, ...)
    :param rundir:
        Directory in which to run the command defined for the phase
    :return:
        Returncode from the command that was executed, 0 will be returned
        if there was no command to run
    """
    cmd = testflinger_agent.config.get(phase+'_command')
    if not cmd:
        return 0
    phase_log = os.path.join(rundir, phase+'.log')
    logger.info('Running %s_command: %s' % (phase, cmd))
    # Set the exitcode to some failed status in case we get interrupted
    exitcode = 99
    try:
        exitcode = run_with_log(cmd, phase_log, rundir)
    finally:
        # Save the output log in the json file no matter what
        with open(os.path.join(rundir, 'testflinger-outcome.json')) as f:
            outcome_data = json.load(f)
        if os.path.exists(phase_log):
            with open(phase_log) as f:
                outcome_data[phase+'_output'] = f.read()
        outcome_data[phase+'_status'] = exitcode
        with open(os.path.join(rundir, 'testflinger-outcome.json'), 'w') as f:
            json.dump(outcome_data, f)
        return exitcode


def repost_job(job_data):
    server = testflinger_agent.config.get('server_address')
    if not server.lower().startswith('http'):
        server = 'http://' + server
    job_uri = urljoin(server, '/v1/job')
    logger.info('Resubmitting job for job: %s' % job_data.get('job_id'))
    job_request = requests.post(job_uri, json=job_data)
    if job_request.status_code != 200:
        logging.error('Unable to re-post job to: %s (error: %s)' %
                      (job_uri, job_request.status_code))
        raise TFServerError(job_request.status_code)


def post_result(job_id, data):
    """Post data to the testflinger server result for this job

    :param job_id:
        id for the job on which we want to post results
    :param data:
        dict with data to be posted in json
    """
    server = testflinger_agent.config.get('server_address')
    if not server.lower().startswith('http'):
        server = 'http://' + server
    result_uri = urljoin(server, '/v1/result/')
    result_uri = urljoin(result_uri, job_id)
    job_request = requests.post(result_uri, json=data)
    if job_request.status_code != 200:
        logging.error('Unable to post results to: %s (error: %s)' %
                      (result_uri, job_request.status_code))
        raise TFServerError(job_request.status_code)


def transmit_job_outcome(rundir):
    """Post job outcome json data to the testflinger server

    :param rundir:
        Execution dir where the results can be found
    """
    server = testflinger_agent.config.get('server_address')
    if not server.lower().startswith('http'):
        server = 'http://' + server
    # Create uri for API: /v1/result/<job_id>
    with open(os.path.join(rundir, 'testflinger.json')) as f:
        job_data = json.load(f)
    job_id = job_data.get('job_id')
    # Do not retransmit outcome if it's already been done and removed
    outcome_file = os.path.join(rundir, 'testflinger-outcome.json')
    if os.path.exists(outcome_file):
        logger.info('Submitting job outcome for job: %s' % job_id)
        with open(outcome_file) as f:
            data = json.load(f)
            data['job_state'] = 'complete'
            post_result(job_id, data)
        # Remove the outcome file so we don't retransmit
        os.unlink(outcome_file)
    artifacts_dir = os.path.join(rundir, 'artifacts')
    # If we find an 'artifacts' dir under rundir, archive it, and transmit it
    # to the Testflinger server
    if os.path.exists(artifacts_dir):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_file = os.path.join(tmpdir, 'artifacts')
            shutil.make_archive(artifact_file, format='gztar',
                                root_dir=rundir, base_dir='artifacts')
            artifact_uri = urljoin(
                server, '/v1/result/{}/artifact'.format(job_id))
            with open(artifact_file+'.tar.gz', 'rb') as tarball:
                file_upload = {'file': ('file', tarball, 'application/x-gzip')}
                artifact_request = requests.post(
                    artifact_uri, files=file_upload)
            if artifact_request.status_code != 200:
                logging.error('Unable to post results to: %s (error: %s)' %
                              (artifact_uri, artifact_request.status_code))
                raise TFServerError(artifact_request.status_code)
            else:
                shutil.rmtree(artifacts_dir)
    shutil.rmtree(rundir)


def run_with_log(cmd, logfile, cwd=None):
    """Execute command in a subprocess and log the output

    :param cmd:
        Command to run
    :param logfile:
        Filename to save the output in
    :param cwd:
        Path to run the command from
    :return:
        returncode from the process
    """
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
        return process.returncode
