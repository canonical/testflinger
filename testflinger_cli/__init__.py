# Copyright (C) 2017-2020 Canonical
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
import inspect
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
    """Show the status of a specified JOB_ID"""
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
    """Tell the server to cancel a specified JOB_ID"""
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
    """Submit a new test job to the server"""
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
    job_id = submit_job_data(conn, data)
    if quiet:
        print(job_id)
    else:
        print('Job submitted successfully!')
        print('job_id: {}'.format(job_id))
    if poll_opt:
        ctx.invoke(poll, job_id=job_id)


def submit_job_data(conn, data):
    """ Submit data that was generated or read from a file as a test job
    """
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
    return job_id


@cli.command()
@click.argument('job_id', nargs=1)
@click.pass_context
def show(ctx, job_id):
    """Show the requested job JSON for a specified JOB_ID"""
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
    """Get results JSON for a completed JOB_ID"""
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
    """Download a tarball of artifacts saved for a specified job"""
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
    """Poll for output from a job until it is complete"""
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


@cli.command()
@click.pass_context
def queues(ctx):
    """List the advertised queues on the current Testflinger server"""
    conn = ctx.obj['conn']
    try:
        queues = conn.get_queues()
    except client.HTTPError as e:
        if e.status == 404:
            raise SystemExit('Received 404 error from server. Are you sure '
                             'this is a testflinger server?')
    except Exception:
        raise SystemExit(
            'Error communicating with server, check connection and retry')
    print('Advertised queues on this server:')
    for name, description in sorted(queues.items()):
        print(' {} - {}'.format(name, description))


@cli.command()
@click.option('--queue', '-q',
              help='Name of the queue to use')
@click.option('--image', '-i',
              help='Name of the image to use for provisioning')
@click.option('--key', '-k', 'ssh_keys', multiple=True,
              help='Ssh key(s) to use for reservation '
                   '(ex: -k lp:userid -k gh:userid)')
@click.pass_context
def reserve(ctx, queue, image, ssh_keys):
    """Install and reserve a system"""
    conn = ctx.obj['conn']
    if not queue:
        try:
            queues = conn.get_queues()
        except Exception:
            print("WARNING: unable to get a list of queues from the server!")
            queues = {}
        queue = _get_queue(queues)
    if not image:
        try:
            images = conn.get_images(queue)
        except Exception:
            print("WARNING: unable to get a list of images from the server!")
            images = {}
        image = _get_image(images)
    if not ssh_keys:
        ssh_keys = _get_ssh_keys()
    template = inspect.cleandoc("""job_queue: {queue}
                                   provision_data:
                                     {image}
                                   reserve_data:
                                     ssh_keys:""")
    for ssh_key in ssh_keys:
        template += "\n    - {}".format(ssh_key)
    job_data = template.format(queue=queue, image=image)
    print("\nThe following yaml will be submitted:")
    print(job_data)
    answer = input("Proceed? (Y/n) ")
    if answer in ("Y", "y", ""):
        job_id = submit_job_data(conn, job_data)
        print('Job submitted successfully!')
        print('job_id: {}'.format(job_id))
        ctx.invoke(poll, job_id=job_id)


def _get_queue(queues):
    queue = ""
    while not queue or queue == "?":
        queue = input("\nWhich queue do you want to use? ('?' to list) ")
        if not queue:
            continue
        if queue == "?":
            print("\nAdvertised queues on this server:")
            for name, description in sorted(queues.items()):
                print(" {} - {}".format(name, description))
            queue = _get_queue(queues)
        if queue not in queues.keys():
            print("WARNING: '{}' is not in the list of known "
                  "queues".format(queue))
            answer = input("Do you still want to use it? (y/N) ")
            if answer.lower() != "y":
                queue = ""
    return queue


def _get_image(images):
    image = ""
    while not image or image == "?":
        image = input("\nEnter the name of the image you want to use "
                      "('?' to list) ")
        if image == "?":
            for image_id in sorted(images.keys()):
                print(" " + image_id)
            continue
        if image not in images.keys():
            print("ERROR: '{}' is not in the list of known images for that "
                  "queue, please select another.".format(image))
            image = ""
    return images.get(image)


def _get_ssh_keys():
    ssh_keys = ""
    while not ssh_keys.strip():
        ssh_keys = input("\nEnter the ssh key(s) you wish to use: "
                         "(ex: lp:userid, gh:userid) ")
        key_list = [ssh_key.strip() for ssh_key in ssh_keys.split(",")]
        for ssh_key in key_list:
            if not ssh_key.startswith("lp:") and not ssh_key.startswith("gh:"):
                ssh_keys = ""
                print("Please enter keys in the form lp:userid or gh:userid")
    return key_list


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
