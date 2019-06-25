# Copyright (C) 2017-2019 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


import click
import json
import os
import sys
import time

from testflinger_cli import client


# Make it easier to run from a checkout
basedir = os.path.abspath(os.path.join(__file__, '..'))
if os.path.exists(os.path.join(basedir, 'setup.py')):
    sys.path.insert(0, basedir)


@click.group()
@click.option('--server', default='https://testflinger.canonical.com',
              help='Testflinger server to use')
@click.pass_context
def cli(ctx, server):
    ctx.obj = {}
    env_server = os.environ.get('TESTFLINGER_SERVER')
    if env_server:
        server = env_server
    ctx.obj['conn'] = client.Client(server)


@cli.command()
@click.argument('job_id', nargs=1)
@click.pass_context
def status(ctx, job_id):
    conn = ctx.obj['conn']
    try:
        job_state = conn.get_status(job_id)
    except client.HTTPError as e:
        if e.status == 204:
            raise SystemExit('No data found for that job id. Check the job '
                             'id to be sure it is correct')
        if e.status == 400:
            raise SystemExit('Invalid job id specified. Check the job id to '
                             'be sure it is correct')
        if e.status == 404:
            raise SystemExit('Received 404 error from server. Are you sure '
                             'this is a testflinger server?')
    except Exception:
        raise SystemExit(
            'Error communicating with server, check connection and retry')
    print(job_state)


@cli.command()
@click.argument('job_id', nargs=1)
@click.pass_context
def cancel(ctx, job_id):
    conn = ctx.obj['conn']
    try:
        job_state = conn.get_status(job_id)
    except client.HTTPError as e:
        if e.status == 204:
            raise SystemExit('Job {} not found. Check the job id to be sure '
                             'it is correct.'.format(job_id))
        if e.status == 400:
            raise SystemExit('Invalid job id specified. Check the job id to '
                             'be sure it is correct.')
        if e.status == 404:
            raise SystemExit('Received 404 error from server. Are you sure '
                             'this is a testflinger server?')
    except Exception:
        raise SystemExit(
            'Error communicating with server, check connection and retry')
    if job_state in ('complete', 'cancelled'):
        raise SystemExit('Job {} is already in {} state and cannot be '
                         'cancelled.'.format(job_id, job_state))
    conn.post_job_state(job_id, 'cancelled')


@cli.command()
@click.argument('filename', nargs=1)
@click.option('--poll', '-p', 'poll_opt', is_flag=True)
@click.option('--quiet', '-q', is_flag=True)
@click.pass_context
def submit(ctx, filename, quiet, poll_opt):
    conn = ctx.obj['conn']
    if filename == '-':
        data = sys.stdin.read()
    else:
        try:
            with open(filename) as f:
                data = f.read()
        except FileNotFoundError:
            raise SystemExit('File not found: {}'.format(filename))
        except Exception:
            raise SystemExit('Unable to read file: {}'.format(filename))
    try:
        job_id = conn.submit_job(data)
    except client.HTTPError as e:
        if e.status == 400:
            raise SystemExit('The job you submitted contained bad data or '
                             'bad formatting, or did not specify a '
                             'job_queue.')
        if e.status == 404:
            raise SystemExit('Received 404 error from server. Are you sure '
                             'this is a testflinger server?')
        # This shouldn't happen, so let's get more information
        raise SystemExit('Unexpected error status from testflinger '
                         'server: {}'.format(e.status))
    if quiet:
        print(job_id)
    else:
        print('Job submitted successfully!')
        print('job_id: {}'.format(job_id))
    if poll_opt:
        ctx.invoke(poll, job_id=job_id)


@cli.command()
@click.argument('job_id', nargs=1)
@click.pass_context
def show(ctx, job_id):
    conn = ctx.obj['conn']
    try:
        results = conn.show_job(job_id)
    except client.HTTPError as e:
        if e.status == 204:
            raise SystemExit('No data found for that job id.')
        if e.status == 400:
            raise SystemExit('Invalid job id specified. Check the job id to '
                             'be sure it is correct')
        if e.status == 404:
            raise SystemExit('Received 404 error from server. Are you sure '
                             'this is a testflinger server?')
        # This shouldn't happen, so let's get more information
        raise SystemExit('Unexpected error status from testflinger '
                         'server: {}'.format(e.status))
    print(json.dumps(results, sort_keys=True, indent=4))


@cli.command()
@click.argument('job_id', nargs=1)
@click.pass_context
def results(ctx, job_id):
    conn = ctx.obj['conn']
    try:
        results = conn.get_results(job_id)
    except client.HTTPError as e:
        if e.status == 204:
            raise SystemExit('No results found for that job id.')
        if e.status == 400:
            raise SystemExit('Invalid job id specified. Check the job id to '
                             'be sure it is correct')
        if e.status == 404:
            raise SystemExit('Received 404 error from server. Are you sure '
                             'this is a testflinger server?')
        # This shouldn't happen, so let's get more information
        raise SystemExit('Unexpected error status from testflinger '
                         'server: {}'.format(e.status))
    except Exception:
        raise SystemExit(
            'Error communicating with server, check connection and retry')

    print(json.dumps(results, sort_keys=True, indent=4))


@cli.command()
@click.argument('job_id', nargs=1)
@click.option('--filename', default='artifacts.tgz')
@click.pass_context
def artifacts(ctx, job_id, filename):
    conn = ctx.obj['conn']
    print('Downloading artifacts tarball...')
    try:
        conn.get_artifact(job_id, filename)
    except client.HTTPError as e:
        if e.status == 204:
            raise SystemExit('No artifacts tarball found for that job id.')
        if e.status == 400:
            raise SystemExit('Invalid job id specified. Check the job id to '
                             'be sure it is correct')
        if e.status == 404:
            raise SystemExit('Received 404 error from server. Are you sure '
                             'this is a testflinger server?')
        # This shouldn't happen, so let's get more information
        raise SystemExit('Unexpected error status from testflinger '
                         'server: {}'.format(e.status))
    except Exception:
        raise SystemExit(
            'Error communicating with server, check connection and retry')
    print('Artifacts downloaded to {}'.format(filename))


@cli.command()
@click.argument('job_id', nargs=1)
@click.option('--oneshot', '-o', is_flag=True,
              help='Get latest output and exit immediately')
@click.pass_context
def poll(ctx, job_id, oneshot):
    conn = ctx.obj['conn']
    if oneshot:
        try:
            output = get_latest_output(conn, job_id)
        except Exception:
            sys.exit(1)
        if output:
            print(output, end='', flush=True)
        sys.exit(0)
    job_state = get_job_state(conn, job_id)
    if job_state == 'waiting':
        print('This job is currently waiting on a node to become available.')
        prev_queue_pos = None
    while job_state != 'complete':
        if job_state == 'waiting':
            try:
                queue_pos = conn.get_job_position(job_id)
                if int(queue_pos) != prev_queue_pos:
                    prev_queue_pos = int(queue_pos)
                    print('Jobs ahead in queue: {}'.format(queue_pos))
            except Exception:
                # Ignore any bad response, this will retry
                pass
        time.sleep(10)
        output = ''
        try:
            output = get_latest_output(conn, job_id)
        except Exception:
            continue
        if output:
            print(output, end='', flush=True)
        job_state = get_job_state(conn, job_id)
    print(job_state)


def get_latest_output(conn, job_id):
    output = ''
    try:
        output = conn.get_output(job_id)
    except client.HTTPError as e:
        if e.status == 204:
            # We are still waiting for the job to start
            pass
    return output


def get_job_state(conn, job_id):
    try:
        return conn.get_status(job_id)
    except client.HTTPError as e:
        if e.status == 204:
            raise SystemExit('No data found for that job id. Check the job '
                             'id to be sure it is correct')
        if e.status == 400:
            raise SystemExit('Invalid job id specified. Check the job id to '
                             'be sure it is correct')
        if e.status == 404:
            raise SystemExit('Received 404 error from server. Are you sure '
                             'this is a testflinger server?')
    except Exception:
        # If we fail to get the job_state here, it could be because of timeout
        # but we can keep going and retrying
        pass
    return 'unknown'
