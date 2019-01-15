# Copyright (c) 2015 Ericsson AB.
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

'''
Interface for database access.

SQLAlchemy is currently the only supported backend.
'''

from oslo_config import cfg
from oslo_db import api


CONF = cfg.CONF

_BACKEND_MAPPING = {'sqlalchemy': 'dbsync.db.identity.sqlalchemy.api'}

IMPL = api.DBAPI.from_config(CONF, backend_mapping=_BACKEND_MAPPING)


def get_engine():
    return IMPL.get_engine()


def get_session():
    return IMPL.get_session()


###################

# user db methods

###################

def user_get_all(context):
    """Retrieve all users."""
    return IMPL.user_get_all(context)


def user_get(context, user_id):
    """Retrieve details of a user."""
    return IMPL.user_get(context, user_id)


def user_create(context, payload):
    """Create a user."""
    return IMPL.user_create(context, payload)


def user_update(context, user_ref, payload):
    """Update a user"""
    return IMPL.user_update(context, user_ref, payload)


def user_db_model_to_dict(user_ref):
    """Convert user db model to dictionary."""

    result = {
        'user_id': user_ref.id,
        'user_extra': user_ref.extra,
        'user_enabled': user_ref._enabled,
        'user_default_project_id': user_ref.default_project_id,
        'user_created_at': user_ref.created_at,
        'user_last_active_at': user_ref.last_active_at,
        'user_domain_id': user_ref.domain_id,
        'local_user_name': user_ref.local_user.name,
        'local_user_user_id': user_ref.local_user.user_id,
        'local_user_domain_id': user_ref.local_user.domain_id,
        'local_user_failed_auth_count': user_ref.local_user.failed_auth_count,
        'local_user_failed_auth_at': user_ref.local_user.failed_auth_at,
    }

    return result


###################

# project db methods

###################

def project_get_all(context):
    """Retrieve all projects."""
    return IMPL.project_get_all(context)


def project_get(context, project_id):
    """Retrieve details of a project."""
    return IMPL.project_get(context, project_id)


def project_create(context, payload):
    """Create a project."""
    return IMPL.project_create(context, payload)


def project_update(context, project_ref, payload):
    """Update a project"""
    return IMPL.project_update(context, project_ref, payload)


def project_db_model_to_dict(project_ref):
    """Convert project db model to dictionary."""

    result = {
        'project_id': project_ref.id,
        'domain_id': project_ref.domain_id,
        'name': project_ref.name,
        'extra': project_ref.extra,
        'description': project_ref.description,
        'enabled': project_ref.enabled,
        'parent_id': project_ref.parent_id,
        'is_domain': project_ref.is_domain,
    }

    return result


###################

# role db methods

###################

def role_get_all(context):
    """Retrieve all roles."""
    return IMPL.role_get_all(context)


def role_get(context, role_id):
    """Retrieve details of a role."""
    return IMPL.role_get(context, role_id)


def role_create(context, payload):
    """Create a role."""
    return IMPL.role_create(context, payload)


def role_update(context, role_ref, payload):
    """Update a role"""
    return IMPL.role_update(context, role_ref, payload)


def role_db_model_to_dict(role_ref):
    """Convert role db model to dictionary."""

    result = {
        'role_id': role_ref.id,
        'domain_id': role_ref.domain_id,
        'name': role_ref.name,
        'extra': role_ref.extra,
    }

    return result


###################

# assignment db methods

###################

def assignment_get_all(context):
    """Retrieve all role assignment."""
    return IMPL.assignment_get_all(context)


def assignment_get(context, type=None, actor_id=None, target_id=None,
                   role_id=None, inherited=None, first=True):
    """Retrieve details of a role assignment."""
    return IMPL.assignment_get(context, type=type, actor_id=actor_id,
                               target_id=target_id, role_id=role_id,
                               inherited=inherited, first=first)


def assignment_create(context, payload):
    """Create a role."""
    return IMPL.assignment_create(context, payload)


def assignment_db_model_to_dict(assignment_ref):
    """Convert assignment db model to dictionary."""

    result = {
        'type': assignment_ref.type,
        'actor_id': assignment_ref.actor_id,
        'target_id': assignment_ref.target_id,
        'role_id': assignment_ref.role_id,
        'inherited': assignment_ref.inherited,
    }

    return result


###################

# revoke_event db methods

###################

def revoke_event_get_all(context):
    """Retrieve all token revocation events."""
    return IMPL.revoke_event_get_all(context)


def revoke_event_get(context, id=None, project_id=None, user_id=None,
                     role_id=None, audit_id=None, issued_before=None):
    """Retrieve details of a token revocation event."""
    return IMPL.revoke_event_get(context, id=id, project_id=project_id,
                                 user_id=user_id, role_id=role_id,
                                 audit_id=audit_id,
                                 issued_before=issued_before)


def revoke_event_create(context, payload):
    """Create a token revocation event."""
    return IMPL.revoke_event_create(context, payload)


def revoke_event_delete(context, id=None, user_id=None, audit_id=None,
                        issued_before=None):
    """Delete a tokem revocation event."""
    return IMPL.revoke_event_delete(context, user_id=user_id,
                                    audit_id=audit_id,
                                    issued_before=issued_before)


def revoke_event_db_model_to_dict(revoke_event_ref):
    """Convert token revoke event db model to dictionary."""

    result = {
        'id': revoke_event_ref.id,
        'project_id': revoke_event_ref.project_id,
        'user_id': revoke_event_ref.user_id,
        'role_id': revoke_event_ref.role_id,
        'issued_before': revoke_event_ref.issued_before,
        'audit_id': revoke_event_ref.audit_id,
    }

    return result
