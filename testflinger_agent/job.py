# Copyright (C) 2017 Canonical
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import fcntl
import json
import logging
import os
import select
import sys
import subprocess
import time

logger = logging.getLogger()


class TestflingerJob:
    def __init__(self, job_data, client):
        """
        :param job_data:
            Dictionary containing data for the test job_data
        :param client:
            Testflinger client object for communicating with the server
        """
        self.client = client
        self.job_data = job_data
        self.job_id = job_data.get('job_id')
        self.phase = 'unknown'

    def run_test_phase(self, phase, rundir):
        """Run the specified test phase in rundir

        :param phase:
            Name of the test phase (setup, provision, test, ...)
        :param rundir:
            Directory in which to run the command defined for the phase
        :return:
            Returncode from the command that was executed, 0 will be returned
            if there was no command to run
        """
        self.phase = phase
        cmd = self.client.config.get(phase+'_command')
        node = self.client.config.get('agent_id')
        if not cmd:
            logger.info('No %s_command configured, skipping...', phase)
            return 0
        if phase == 'provision' and 'provision_data' not in self.job_data:
            logger.info('No provision_data defined in job data, skipping...')
            return 0
        phase_log = os.path.join(rundir, phase+'.log')
        logger.info('Running %s_command: %s', phase, cmd)
        # Set the exitcode to some failed status in case we get interrupted
        exitcode = 99
        for line in self.banner('Starting {} phase on {}'.format(phase, node)):
            self.run_with_log("echo '{}'".format(line), phase_log, rundir)
        try:
            exitcode = self.run_with_log(cmd, phase_log, rundir)
        except Exception as e:
            logger.exception(e)
        finally:
            # Save the output log in the json file no matter what
            with open(os.path.join(rundir, 'testflinger-outcome.json')) as f:
                outcome_data = json.load(f)
            if os.path.exists(phase_log):
                with open(phase_log, encoding='utf-8') as f:
                    outcome_data[phase+'_output'] = f.read()
            outcome_data[phase+'_status'] = exitcode
            with open(os.path.join(rundir, 'testflinger-outcome.json'),
                      'w', encoding='utf-8') as f:
                json.dump(outcome_data, f)
            return exitcode

    def run_with_log(self, cmd, logfile, cwd=None):
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
        global_timeout = self.get_global_timeout()
        output_timeout = self.get_output_timeout()
        start_time = time.time()
        with open(logfile, 'a', encoding='utf-8') as f:
            live_output_buffer = ''
            readpoll = select.poll()
            buffer_timeout = time.time()
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       shell=True, cwd=cwd)
            set_nonblock(process.stdout.fileno())
            readpoll.register(process.stdout, select.POLLIN)
            while process.poll() is None:
                # Check if there's any new data, timeout after 10s
                data_ready = readpoll.poll(10000)
                if data_ready:
                    buf = process.stdout.read().decode(sys.stdout.encoding)
                    if buf:
                        sys.stdout.write(buf)
                        live_output_buffer += buf
                        # Don't spam the server, only flush the buffer if there
                        # is output and it's been more than 10s
                        if time.time() - buffer_timeout > 10:
                            buffer_timeout = time.time()
                            # Try to stream output, if we can't connect, then
                            # keep buffer for the next pass through this
                            if self.client.post_live_output(
                                    self.job_id, live_output_buffer):
                                live_output_buffer = ''
                        f.write(buf)
                        f.flush()
                else:
                    if (self.phase == 'test' and
                            time.time() - buffer_timeout > output_timeout):
                        buf = ('\nERROR: Output timeout reached! '
                               '({}s)\n'.format(output_timeout))
                        live_output_buffer += buf
                        f.write(buf)
                        process.kill()
                        break
                if time.time() - start_time > global_timeout:
                    buf = '\nERROR: Global timeout reached! ({}s)\n'.format(
                        global_timeout)
                    live_output_buffer += buf
                    f.write(buf)
                    process.kill()
                    break
            buf = process.stdout.read()
            if buf:
                buf = buf.decode(sys.stdout.encoding)
                sys.stdout.write(buf)
                live_output_buffer += buf
                f.write(buf)
            if live_output_buffer:
                self.client.post_live_output(self.job_id, live_output_buffer)
            return process.returncode

    def get_global_timeout(self):
        """Get the global timeout for the test run in seconds
        """
        # Default timeout is 4 hours
        default_timeout = 4 * 60 * 60

        # Don't exceed the maximum timeout configured for the device!
        return min(
            self.job_data.get('global_timeout', default_timeout),
            self.client.config.get('global_timeout', default_timeout))

    def get_output_timeout(self):
        """Get the output timeout for the test run in seconds
        """
        # Default timeout is 15 minutes
        default_timeout = 15 * 60

        # Don't exceed the maximum timeout configured for the device!
        return min(
            self.job_data.get('output_timeout', default_timeout),
            self.client.config.get('output_timeout', default_timeout))

    def banner(self, line):
        """Yield text lines to print a banner around a sting

        :param line:
            Line of text to print a banner around
        """
        yield '*' * (len(line) + 4)
        yield '* {} *'.format(line)
        yield '*' * (len(line) + 4)


def set_nonblock(fd):
    """Set the specified fd to nonblocking output

    :param fd:
        File descriptor that should be set to nonblocking mode
    """

    # XXX: This is only used in one place right now, may want to consider
    # moving it if it gets wider use in the future
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
