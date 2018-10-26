# Copyright 2018 Wind River
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess

from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_service import periodic_task

from dcorch.common import consts
from dcorch.common import context
from dcorch.common import exceptions
from dcorch.common.i18n import _
from dcorch.common import manager
from dcorch.common import utils
from dcorch.drivers.openstack import sdk_platform as sdk
from dcorch.objects import subcloud as subcloud_obj


FERNET_REPO_MASTER_ID = "keys"
KEY_ROTATE_CMD = "/usr/bin/keystone-fernet-keys-rotate-active"

CONF = cfg.CONF

LOG = logging.getLogger(__name__)


class FernetKeyManager(manager.Manager):
    """Manages tasks related to fernet key management"""

    def __init__(self, gsm, *args, **kwargs):
        LOG.debug(_('FernetKeyManager initialization...'))

        super(FernetKeyManager, self).__init__(service_name="fernet_manager",
                                               *args, **kwargs)
        self.gsm = gsm
        self.context = context.get_admin_context()
        self.endpoint_type = consts.ENDPOINT_TYPE_PLATFORM
        self.resource_type = consts.RESOURCE_TYPE_SYSINV_FERNET_REPO

    @classmethod
    def to_resource_info(cls, key_list):
        return dict((getattr(key, 'id'), getattr(key, 'key'))
                    for key in key_list)

    @classmethod
    def from_resource_info(cls, keys):
        key_list = [dict(id=k, key=v) for k, v in keys.items()]
        return key_list

    @classmethod
    def get_resource_hash(cls, resource_info):
        return hash(tuple(sorted(hash(x) for x in resource_info.items())))

    def _schedule_work(self, operation_type, subcloud=None):
        keys = self._get_master_keys()
        if not keys:
            LOG.info(_("No fernet keys returned from %s") % consts.CLOUD_0)
            return
        try:
            resource_info = FernetKeyManager.to_resource_info(keys)
            utils.enqueue_work(self.context,
                               self.endpoint_type,
                               self.resource_type,
                               FERNET_REPO_MASTER_ID,
                               operation_type,
                               resource_info=jsonutils.dumps(resource_info),
                               subcloud=subcloud)
            # wake up sync thread
            if self.gsm:
                self.gsm.sync_request(self.context, self.endpoint_type)
        except Exception as e:
            LOG.error(_("Exception in schedule_work: %s") % e.message)

    @staticmethod
    def _get_master_keys():
        """get the keys from the local fernet key repo"""
        keys = []
        try:
            os_client = sdk.OpenStackDriver(consts.CLOUD_0)
            keys = os_client.sysinv_client.get_fernet_keys()
        except (exceptions.ConnectionRefused, exceptions.NotAuthorized,
                exceptions.TimeOut):
            LOG.info(_("Retrieving the fernet keys from %s timeout") %
                     consts.CLOUD_0)
        except Exception as e:
            LOG.info(_("Fail to retrieve the master fernet keys: %s") %
                     e.message)
        return keys

    def periodic_tasks(self, context, raise_on_error=False):
        """Periodic tasks are run at pre-specified intervals."""
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task(
        spacing=CONF.fernet.key_rotation_interval * 3600)
    def _rotate_fernet_keys(self, context):
        """Rotate fernet keys."""

        with open(os.devnull, "w") as fnull:
            try:
                subprocess.check_call(KEY_ROTATE_CMD,
                                      stdout=fnull,
                                      stderr=fnull)
            except subprocess.CalledProcessError:
                msg = _("Failed to rotate the keys")
                LOG.exception(msg)
                raise exceptions.InternalError(msg)

        self._schedule_work(consts.OPERATION_TYPE_PUT)

    def distribute_keys(self, ctxt, subcloud_name):
        subcloud = None
        subclouds = subcloud_obj.SubcloudList.get_all(ctxt)
        for sc in subclouds:
            if sc.region_name == subcloud_name:
                subcloud = sc
                break
        self._schedule_work(consts.OPERATION_TYPE_CREATE, subcloud)
