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
        cmd = self.client.config.get(phase+'_command')
        if not cmd:
            return 0
        phase_log = os.path.join(rundir, phase+'.log')
        logger.info('Running %s_command: %s' % (phase, cmd))
        # Set the exitcode to some failed status in case we get interrupted
        exitcode = 99
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
        with open(logfile, 'w', encoding='utf-8') as f:
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
            buf = process.stdout.read().decode(sys.stdout.encoding)
            if buf:
                sys.stdout.write(buf)
                live_output_buffer += buf
                f.write(buf)
            if live_output_buffer:
                self.client.post_live_output(self.job_id, live_output_buffer)
            return process.returncode


def set_nonblock(fd):
    """Set the specified fd to nonblocking output

    :param fd:
        File descriptor that should be set to nonblocking mode
    """

    # XXX: This is only used in one place right now, may want to consider
    # moving it if it gets wider use in the future
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
