# Copyright (c) 2017 Ericsson AB.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
# Copyright (c) 2019 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#


from dbsync.dbsyncclient import base
from dbsync.dbsyncclient.base import get_json
from dbsync.dbsyncclient import exceptions


class Assignment(base.Resource):
    resource_name = 'assignment'

    def __init__(self, manager, type, actor_id, target_id, role_id,
                 inherited):
        self.manager = manager
        self.type = type
        self.actor_id = actor_id
        self.target_id = target_id
        self.role_id = role_id
        self.inherited = inherited

    def info(self):
        resource_info = dict()
        resource_info.update({self.resource_name:
                             {'type': self.type,
                              'actor_id': self.actor_id,
                              'target_id': self.target_id,
                              'role_id': self.role_id,
                              'inherited': self.inherited}})
        return resource_info


class assignment_manager(base.ResourceManager):
    resource_class = Assignment

    def assignment_create(self, url, data):
        resp = self.http_client.post(url, data)

        # Unauthorized
        if resp.status_code == 401:
            raise exceptions.Unauthorized('Unauthorized request')
        if resp.status_code != 201:
            self._raise_api_exception(resp)

        # Converted into python dict
        json_object = get_json(resp)
        return json_object

    def assignments_list(self, url):
        resp = self.http_client.get(url)

        # Unauthorized
        if resp.status_code == 401:
            raise exceptions.Unauthorized('Unauthorized request')
        if resp.status_code != 200:
            self._raise_api_exception(resp)

        # Converted into python dict
        json_objects = get_json(resp)

        assignments = []
        for json_object in json_objects:
            assignment = Assignment(
                self,
                type=json_object['type'],
                actor_id=json_object['actor_id'],
                target_id=json_object['target_id'],
                role_id=json_object['role_id'],
                inherited=json_object['inherited'])

            assignments.append(assignment)

        return assignments

    def _assignment_detail(self, url):
        resp = self.http_client.get(url)

        # Unauthorized
        if resp.status_code == 401:
            raise exceptions.Unauthorized('Unauthorized request')
        if resp.status_code != 200:
            self._raise_api_exception(resp)

        # Return assignment details in original json format,
        # ie, without convert it into python dict
        return resp.content

    def add_assignment(self, data):
        url = '/identity/assignments/'
        return self.assignment_create(url, data)

    def list_assignments(self):
        url = '/identity/assignments/'
        return self.assignments_list(url)

    def assignment_detail(self, assignment_ref):
        url = '/identity/assignments/%s' % assignment_ref
        return self._assignment_detail(url)
