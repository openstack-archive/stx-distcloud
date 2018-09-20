# Copyright (c) 2018 Wind River Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from dcorch.common.i18n import _
import eventlet
from oslo_log import log as logging
from oslo_service import service
import signal
import sys

LOG = logging.getLogger(__name__)


class DCOrchLauncher(service.ProcessLauncher):

    def _pipe_watcher(self):
        # This will block until the write end is closed when the parent
        # dies unexpectedly
        self.readpipe.read(1)

        LOG.info('Parent process has died unexpectedly, exiting')

        # add alarm watching that allows up to 1 second to shutdown
        if self.signal_handler.is_signal_supported('SIGALRM'):
            signal.alarm(1)

        eventlet.wsgi.is_accepting = False

        if self.launcher:
            self.launcher.stop()

        sys.exit(1)


def launch(conf, service, workers, restart_method='reload'):
    """Launch a service with a given number of workers.

    :param conf: an instance of ConfigOpts
    :param service: a service to launch, must be an instance of
           :class:`oslo_service.service.ServiceBase`
    :param workers: a number of processes in which a service will be running
    :param restart_method: Passed to the constructed launcher. If 'reload', the
        launcher will call reload_config_files on SIGHUP. If 'mutate', it will
        call mutate_config_files on SIGHUP. Other values produce a ValueError.
    :returns: instance of a launcher that was used to launch the service
    """
    if workers is not None and workers <= 0:
        raise ValueError(_("Number of workers should be positive!"))

    if workers is None or workers == 1:
        launcher = service.ServiceLauncher(conf, restart_method=restart_method)
    else:
        launcher = DCOrchLauncher(conf, restart_method=restart_method)
    launcher.launch_service(service, workers=workers)

    return launcher
