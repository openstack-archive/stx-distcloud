# Copyright 2017 Ericsson AB.
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

from oslo_log import log as logging

from dbsync.dbsyncclient import exceptions as dbsync_exceptions
from dcorch.common import consts
from dcorch.common import exceptions
from dcorch.engine.subcloud import SubCloudEngine
from dcorch.objects import subcloud

LOG = logging.getLogger(__name__)


class GenericSyncManager(object):
    """Manages tasks related to resource management."""

    def __init__(self, *args, **kwargs):
        super(GenericSyncManager, self).__init__()
        self.subcloud_engines = {}

    def init_from_db(self, context):
        subclouds = subcloud.SubcloudList.get_all(context)
        for sc in subclouds:
            engine = SubCloudEngine(subcloud=sc)
            LOG.info('loading subcloud %(sc)s' %
                     {'sc': sc.region_name})
            self.subcloud_engines[sc.region_name] = engine
            engine.spawn_sync_threads()

    def add_subcloud(self, context, name, version):
        LOG.info('adding subcloud %(sc)s' % {'sc': name})
        subcloud_engine = SubCloudEngine(
            context=context, name=name, version=version)
        self.subcloud_engines[name] = subcloud_engine
        subcloud_engine.spawn_sync_threads()

    def del_subcloud(self, context, subcloud_name):
        try:
            subcloud_engine = self.subcloud_engines[subcloud_name]
            LOG.info('deleting subcloud %(sc)s' % {'sc': subcloud_name})
            subcloud_engine.delete()
            del self.subcloud_engines[subcloud_name]
        except KeyError:
            raise exceptions.SubcloudNotFound(region_name=subcloud_name)

    def sync_request(self, ctxt, endpoint_type):
        # Someone has enqueued a sync job.  Wake the subcloud engines.
        for subcloud_engine in self.subcloud_engines.values():
            subcloud_engine.wake(endpoint_type)

    def enable_subcloud(self, context, subcloud_name):
        try:
            subcloud_engine = self.subcloud_engines[subcloud_name]
            LOG.info('enabling subcloud %(sc)s' % {'sc': subcloud_name})
            subcloud_engine.enable()
        except KeyError:
            raise exceptions.SubcloudNotFound(region_name=subcloud_name)

    def disable_subcloud(self, context, subcloud_name):
        try:
            subcloud_engine = self.subcloud_engines[subcloud_name]
            LOG.info('disabling subcloud %(sc)s' % {'sc': subcloud_name})
            subcloud_engine.disable()
        except KeyError:
            raise exceptions.SubcloudNotFound(region_name=subcloud_name)

    def update_subcloud_version(self, context, subcloud_name, sw_version):
        try:
            subcloud_engine = self.subcloud_engines[subcloud_name]
            LOG.info('updating subcloud %(sc)s version to %(ver)s' %
                     {'sc': subcloud_name, 'ver': sw_version})
            subcloud_engine.set_version(sw_version)
        except KeyError:
            raise exceptions.SubcloudNotFound(region_name=subcloud_name)

    def run_sync_audit(self):
        for subcloud_engine in self.subcloud_engines.values():
            subcloud_engine.run_sync_audit()

    def _get_users(self, client, filtered_list):
        filtered_users = []
        # get users from DB API
        users = client.list_users()
        for user in users:
            user_name = user.local_user.name
            if all(user_name != filtered for filtered in filtered_list):
                    filtered_users.append(user)

        return filtered_users

    def _sync_users(self, sync_thread, m_users, sc_users):
        m_client = sync_thread.m_dbs_client.identity_manager
        sc_client = sync_thread.sc_dbs_client.identity_manager

        for m_user in m_users:
            for sc_user in sc_users:
                if (m_user.local_user.name == sc_user.local_user.name and
                        m_user.domain_id == sc_user.domain_id and
                        m_user.id != sc_user.id):
                    user_records = m_client.user_detail(m_user.id)
                    if not user_records:
                        LOG.error("No data retrieved from master cloud for"
                                  " user {} to update its equivalent in"
                                  " subcloud.".format(m_user.id))
                        raise exceptions.SyncRequestFailed
                    # update the user by pushing down the DB records to
                    # subcloud
                    try:
                        user_ref = sc_client.update_user(sc_user.id,
                                                         user_records)
                    # Retry once if unauthorized
                    except dbsync_exceptions.Unauthorized as e:
                        LOG.info("Update user {} request failed for {}: {}."
                                 .format(sc_user.id,
                                         sync_thread.subcloud_engine.subcloud.
                                         region_name, str(e)))
                        sync_thread.reinitialize_sc_clients()
                        user_ref = sc_client.update_user(sc_user.id,
                                                         user_records)

                    if not user_ref:
                        LOG.error("No user data returned when updating user {}"
                                  " in subcloud.".format(sc_user.id))
                        raise exceptions.SyncRequestFailed
                    # If admin user get synced, the client need to
                    # re-authenticate.
                    if sc_user.local_user.name == "admin":
                        sync_thread.reinitialize_sc_clients()

    def _get_projects(self, client, filtered_list):
        # get projects from DB API
        projects = client.list_projects()
        filtered_projects = [project for project in projects if
                             all(project.name != filtered for
                                 filtered in filtered_list)]

        return filtered_projects

    def _sync_projects(self, sync_thread, m_projects, sc_projects):
        m_client = sync_thread.m_dbs_client.project_manager
        sc_client = sync_thread.sc_dbs_client.project_manager

        for m_project in m_projects:
            for sc_project in sc_projects:
                if (m_project.name == sc_project.name and
                        m_project.domain_id == sc_project.domain_id and
                        m_project.id != sc_project.id):
                    project_records = m_client.project_detail(m_project.id)
                    if not project_records:
                        LOG.error("No data retrieved from master cloud for"
                                  " project {} to update its equivalent in"
                                  " subcloud.".format(m_project.id))
                        raise exceptions.SyncRequestFailed
                    # update the project by pushing down the DB records to
                    # subcloud
                    try:
                        project_ref = sc_client.update_project(sc_project.id,
                                                               project_records)
                    # Retry once if unauthorized
                    except dbsync_exceptions.Unauthorized as e:
                        LOG.info("Update project {} request failed for {}: {}."
                                 .format(sc_project.id,
                                         sync_thread.subcloud_engine.subcloud.
                                         region_name, str(e)))
                        sync_thread.reinitialize_sc_clients()
                        project_ref = sc_client.update_project(sc_project.id,
                                                               project_records)

                    if not project_ref:
                        LOG.error("No project data returned when updating"
                                  " project {} in subcloud.".
                                  format(sc_project.id))
                        raise exceptions.SyncRequestFailed
                    # If admin project get synced, the client need to
                    # re-authenticate.
                    if sc_project.name == "admin":
                        sync_thread.reinitialize_sc_clients()

    def initial_sync(self, context, subcloud_name, endpoint_type):
        try:
            subcloud_engine = self.subcloud_engines[subcloud_name]
        except KeyError:
            raise exceptions.SubcloudNotFound(region_name=subcloud_name)

        sync_thread = None
        for thread in subcloud_engine.sync_threads:
            if thread.endpoint_type == endpoint_type:
                sync_thread = thread
                break
        if sync_thread is None:
                raise exceptions.ThreadNotFound(thread_name=endpoint_type,
                                                region_name=subcloud_name)

        sync_thread.initialize_sc_clients()

        # sync users
        m_client = sync_thread.m_dbs_client.identity_manager
        sc_client = sync_thread.sc_dbs_client.identity_manager

        # get users from master cloud
        try:
            m_users = sync_thread._get_users_resource(m_client)
        except dbsync_exceptions.Unauthorized as e:
            LOG.info("Get resource users request failed for {}: {}."
                     .format(consts.VIRTUAL_MASTER_CLOUD, str(e)))
            # In case of token expires, re-authenticate and retry once
            sync_thread.reinitialize_m_clients()
            m_users = sync_thread._get_users_resource(m_client)

        if not m_users:
            LOG.error("No users returned from {}".
                      format(consts.VIRTUAL_MASTER_CLOUD))
            raise exceptions.SyncRequestFailed

        # get users from the subcloud
        try:
            sc_users = sync_thread._get_users_resource(sc_client)
        except dbsync_exceptions.Unauthorized as e:
            LOG.info("Get resource users request failed for {}: {}."
                     .format(subcloud_name, str(e)))
            # In case of token expires, re-authenticate and retry once
            sync_thread.reinitialize_sc_clients()
            sc_users = sync_thread._get_users_resource(sc_client)

        if not sc_users:
            LOG.error("No users returned from subcloud {}".
                      format(subcloud_name))
            raise exceptions.SyncRequestFailed

        self._sync_users(sync_thread, m_users, sc_users)

        # sync projects
        m_client = sync_thread.m_dbs_client.project_manager
        sc_client = sync_thread.sc_dbs_client.project_manager

        # get projects from master cloud
        try:
            m_projects = sync_thread._get_projects_resource(m_client)
        except dbsync_exceptions.Unauthorized as e:
            LOG.info("Get resource projects request failed for {}: {}."
                     .format(consts.VIRTUAL_MASTER_CLOUD, str(e)))
            # In case of token expires, re-authenticate and retry once
            sync_thread.reinitialize_m_clients()
            m_projects = sync_thread._get_projects_resource(m_client)

        if not m_projects:
            LOG.error("No projects returned from {}".
                      format(consts.VIRTUAL_MASTER_CLOUD))
            raise exceptions.SyncRequestFailed

        # get projects from the subcloud
        try:
            sc_projects = sync_thread._get_projects_resource(sc_client)
        except dbsync_exceptions.Unauthorized as e:
            LOG.info("Get resource projects request failed for {}: {}."
                     .format(subcloud_name, str(e)))
            # In case of token expires, re-authenticate and retry once
            sync_thread.reinitialize_sc_clients()
            sc_projects = sync_thread._get_projects_resource(sc_client)

        if not sc_projects:
            LOG.error("No projects returned from subcloud {}".
                      format(subcloud_name))
            raise exceptions.SyncRequestFailed

        self._sync_projects(sync_thread, m_projects, sc_projects)
