# Copyright (c) 2017 Ericsson AB.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# Copyright (c) 2019 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from oslo_config import cfg
from oslo_log import log as logging

import pecan
from pecan import expose
from pecan import request
from pecan import response

from dbsync.api.controllers import restcomm
from dbsync.common import exceptions
from dbsync.common.i18n import _
from dbsync.db.identity import api as db_api

import json

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class AssignmentsController(object):
    VERSION_ALIASES = {
        'Newton': '1.0',
    }

    def __init__(self):
        super(AssignmentsController, self).__init__()

    # to do the version compatibility for future purpose
    def _determine_version_cap(self, target):
        version_cap = 1.0
        return version_cap

    @expose(generic=True, template='json')
    def index(self):
        # Route the request to specific methods with parameters
        pass

    @index.when(method='GET', template='json')
    def get(self, assignment_ref=None):
        """Get a list of role assignment."""
        context = restcomm.extract_context_from_environ()

        try:
            if assignment_ref is None:
                return db_api.assignment_get_all(context)

            else:
                args = {}
                assignment_tags = assignment_ref.split('_')
                # target_id (project id or domain id)
                args.update({'target_id': assignment_tags[0]})

                # actor_id (user id or group id)
                args.update({'actor_id': assignment_tags[1]})

                # role_id (role id)
                args.update({'role_id': assignment_tags[2]})

                assignment = db_api.assignment_get(context, **args)
                return assignment

        except IndexError:
            pecan.abort(404, _('Invalid project role assignment ID'))

        except exceptions.ProjectRoleAssignmentNotFound as e:
            pecan.abort(404, _('Project role assignment with id %s'
                               ' does not exist.') % assignment_ref)

        except Exception as e:
            LOG.exception(e)
            pecan.abort(500, _('Unable to get project role assignment'))

    @index.when(method='POST', template='json')
    def post(self):
        """Create a new role assignment."""

        context = restcomm.extract_context_from_environ()

        # Convert JSON string in request to Python dict
        try:
            payload = json.loads(request.body)
        except ValueError:
            pecan.abort(400, _('Request body decoding error'))

        if not payload:
            pecan.abort(400, _('Body required'))

        try:
            # Insert the role assignment into DB tables
            assignment_ref = db_api.assignment_create(context, payload)
            response.status = 201
            return db_api.assignment_db_model_to_dict(assignment_ref)

        except Exception as e:
            LOG.exception(e)
            pecan.abort(500, _('Unable to create role assignment'))
