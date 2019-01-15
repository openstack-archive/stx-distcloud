# Copyright (c) 2015 Ericsson AB.
# All Rights Reserved.
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
#
# Copyright (c) 2019 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

"""
Implementation of SQLAlchemy backend.
"""

import sys
import threading

from oslo_db.sqlalchemy import enginefacade
from oslo_log import log as logging

from sqlalchemy.orm import joinedload_all

from datetime import datetime

from dbsync.common import exceptions as exception
from dbsync.common.i18n import _
from dbsync.db.identity.sqlalchemy import assignment_model
from dbsync.db.identity.sqlalchemy import identity_model
from dbsync.db.identity.sqlalchemy import project_model
from dbsync.db.identity.sqlalchemy import role_model
from dbsync.db.identity.sqlalchemy import token_revoke_event_model \
    as revoke_event_model

LOG = logging.getLogger(__name__)

_facade = None

_main_context_manager = None
_CONTEXT = threading.local()


def _get_main_context_manager():
    global _main_context_manager
    if not _main_context_manager:
        _main_context_manager = enginefacade.transaction_context()
    return _main_context_manager


def get_engine():
    return _get_main_context_manager().get_legacy_facade().get_engine()


def get_session():
    return _get_main_context_manager().get_legacy_facade().get_session()


def read_session():
    return _get_main_context_manager().reader.using(_CONTEXT)


def write_session():
    return _get_main_context_manager().writer.using(_CONTEXT)


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


def model_query(context, *args):
    with read_session() as session:
        query = session.query(*args).options(joinedload_all('*'))
        return query


def _session(context):
    return get_session()


def is_admin_context(context):
    """Indicate if the request context is an administrator."""
    if not context:
        LOG.warning(_('Use of empty request context is deprecated'),
                    DeprecationWarning)
        raise Exception('die')
    return context.is_admin


def is_user_context(context):
    """Indicate if the request context is a normal user."""
    if not context:
        return False
    if context.is_admin:
        return False
    if not context.user or not context.project:
        return False
    return True


def require_admin_context(f):
    """Decorator to require admin request context.

    The first argument to the wrapped function must be the context.
    """
    def wrapper(*args, **kwargs):
        if not is_admin_context(args[0]):
            raise exception.AdminRequired()
        return f(*args, **kwargs)

    return wrapper


def require_context(f):
    """Decorator to require *any* user or admin context.

    This does no authorization for user or project access matching, see
    :py:func:`authorize_project_context` and
    :py:func:`authorize_user_context`.
    The first argument to the wrapped function must be the context.

    """
    def wrapper(*args, **kwargs):
        if not is_admin_context(args[0]) and not is_user_context(args[0]):
            raise exception.NotAuthorized()
        return f(*args, **kwargs)

    return wrapper


##########################

# identity users

###################

@require_context
def user_get_all(context):
    return model_query(context, identity_model.User). \
        all()


@require_context
def user_get(context, user_id):
    result = model_query(context, identity_model.User). \
        filter_by(id=user_id). \
        first()

    if not result:
        raise exception.UserNotFound(user_id=user_id)

    return result


@require_admin_context
def user_create(context, payload):
    with write_session() as session:
        passwords = payload.get('local_user').get('passwords')
        passwords_ref = []
        if passwords:
            for password in passwords:
                password_ref = identity_model.Password()
                password_ref.password = password['password']
                if password['_expires_at']:
                    password_ref._expires_at = datetime.strptime(
                        password['_expires_at'], '%Y-%m-%d %H:%M:%S.%f')
                password_ref.self_service = password['self_service']
                password_ref.password_hash = password['password_hash']
                password_ref.created_at_int = datetime.strptime(
                    password['created_at_int'], '%Y-%m-%d %H:%M:%S.%f')
                if password['expires_at_int']:
                    password_ref.expires_at_int = datetime.strptime(
                        password['expires_at_int'], '%Y-%m-%d %H:%M:%S.%f')
                password_ref._created_at = datetime.strptime(
                    password['_created_at'], '%Y-%m-%d %H:%M:%S.%f')
                passwords_ref.append(password_ref)

        local_user_ref = identity_model.LocalUser()
        local_user_ref.name = payload.get('local_user').get('name')
        local_user_ref.user_id = payload.get('local_user').get('user_id')
        local_user_ref.domain_id = payload.get('local_user').get('domain_id')
        local_user_ref.failed_auth_count = payload.get('local_user')\
            .get('failed_auth_count')
        local_user_ref.failed_auth_at = payload.get('local_user')\
            .get('failed_auth_at')
        local_user_ref.passwords = passwords_ref

        user_ref = identity_model.User()
        user_ref.id = payload.get('id')
        user_ref.extra = payload.get('extra')
        user_ref._enabled = payload.get('_enabled')
        user_ref.default_project_id = payload.get('default_project_id')
        user_ref.created_at = payload.get('created_at')
        user_ref.last_active_at = payload.get('last_active_at')
        user_ref.domain_id = payload.get('domain_id')
        user_ref.local_user = local_user_ref

        session.add(user_ref)
        return user_ref


@require_admin_context
def user_update(context, user_id, payload):
    with write_session() as session:
        # Retrieve user's details first
        user_ref = user_get(context, user_id)

        # Update user's details
        new_user_id = user_id
        if payload.get('id') is not None:
            user_ref.id = payload.get('id')
            new_user_id = user_ref.id
        if payload.get('extra') is not None:
            user_ref.extra = payload.get('extra')
        if payload.get('_enabled') is not None:
            user_ref._enabled = payload.get('_enabled')
        if payload.get('default_project_id') is not None:
            user_ref.default_project_id = payload.get('default_project_id')
        if payload.get('created_at') is not None:
            user_ref.created_at = payload.get('created_at')
        if payload.get('last_active_at') is not None:
            user_ref.last_active_at = payload.get('last_active_at')
        if payload.get('domain_id') is not None:
            user_ref.domain_id = payload.get('domain_id')

        local_user_ref = user_ref.local_user
        if payload.get('local_user').get('name') is not None:
            local_user_ref.name = payload.get('local_user').get('name')
        if payload.get('local_user').get('user_id') is not None:
            local_user_ref.user_id = payload.get('local_user').get('user_id')
        if payload.get('local_user').get('domain_id') is not None:
            local_user_ref.domain_id = payload.get('local_user')\
                .get('domain_id')
        if payload.get('local_user').get('failed_auth_count') is not None:
            local_user_ref.failed_auth_count = payload.get('local_user')\
                .get('failed_auth_count')
        if payload.get('local_user').get('failed_auth_at') is not None:
            local_user_ref.failed_auth_at = payload.get('local_user')\
                .get('failed_auth_at')

        passwords = payload.get('local_user').get('passwords')
        passwords_ref = []
        if passwords is not None:
            for password in passwords:
                password_ref = identity_model.Password()
                password_ref.password = password['password']
                if password['_expires_at'] is not None:
                    password_ref._expires_at = datetime.strptime(
                        password['_expires_at'], '%Y-%m-%d %H:%M:%S.%f')
                password_ref.self_service = password['self_service']
                password_ref.password_hash = password['password_hash']
                password_ref.created_at_int = datetime.strptime(
                    password['created_at_int'], '%Y-%m-%d %H:%M:%S.%f')
                if password['expires_at_int'] is not None:
                    password_ref.expires_at_int = datetime.strptime(
                        password['expires_at_int'], '%Y-%m-%d %H:%M:%S.%f')
                password_ref._created_at = datetime.strptime(
                    password['_created_at'], '%Y-%m-%d %H:%M:%S.%f')
                passwords_ref.append(password_ref)

        if passwords_ref:
            local_user_ref.passwords = passwords_ref

        user_ref.save(session)

        # Need to update the actor_id in assignment table
        # if the user id is updated
        if user_id != new_user_id:
            assignments = assignment_get(context, actor_id=user_id,
                                         first=False)
            for assignment in assignments:
                assignment.actor_id = new_user_id
                assignment.save(session)

        return user_ref


##########################

# identity projects

###################

@require_context
def project_get_all(context):
    return model_query(context, project_model.Project). \
        all()


@require_context
def project_get(context, project_id):
    result = model_query(context, project_model.Project). \
        filter_by(id=project_id). \
        first()

    if not result:
        raise exception.ProjectNotFound(project_id=project_id)

    return result


@require_admin_context
def project_create(context, payload):
    with write_session() as session:
        project_ref = project_model.Project()

        project_ref.id = payload.get('id')
        project_ref.domain_id = payload.get('domain_id')
        project_ref.name = payload.get('name')
        project_ref.extra = payload.get('extra')
        project_ref.description = payload.get('description')
        project_ref.enabled = payload.get('enabled')
        project_ref.parent_id = payload.get('parent_id')
        project_ref.is_domain = payload.get('is_domain')

        session.add(project_ref)
        return project_ref


@require_admin_context
def project_update(context, project_id, payload):
    with write_session() as session:
        # Retrieve project's details first
        project_ref = project_get(context, project_id)

        # Update project's details
        new_project_id = project_id
        if payload.get('id') is not None:
            project_ref.id = payload.get('id')
            new_project_id = project_ref.id
        if payload.get('name') is not None:
            project_ref.name = payload.get('name')
        if payload.get('extra') is not None:
            project_ref.extra = payload.get('extra')
        if payload.get('description') is not None:
            project_ref.description = payload.get('description')
        if payload.get('enabled') is not None:
            project_ref.enabled = payload.get('enabled')
        if payload.get('domain_id') is not None:
            project_ref.domain_id = payload.get('domain_id')
        if payload.get('parent_id') is not None:
            project_ref.parent_id = payload.get('parent_id')
        if payload.get('is_domain') is not None:
            project_ref.is_domain = payload.get('is_domain')
        project_ref.save(session)

        # Need to update the target_id in assignment table
        # if the project id is updated
        if project_id != new_project_id:
            assignments = assignment_get(context, target_id=project_id,
                                         first=False)
            for assignment in assignments:
                assignment.target_id = new_project_id
                assignment.save(session)

        return project_ref


###################

# identity roles

###################

@require_context
def role_get_all(context):
    return model_query(context, role_model.RoleTable). \
        all()


@require_context
def role_get(context, role_id):
    result = model_query(context, role_model.RoleTable). \
        filter_by(id=role_id). \
        first()

    if not result:
        raise exception.RoleNotFound(role_id=role_id)

    return result


@require_admin_context
def role_create(context, payload):
    with write_session() as session:
        role_ref = role_model.RoleTable()

        role_ref.id = payload.get('id')
        role_ref.domain_id = payload.get('domain_id')
        role_ref.name = payload.get('name')
        role_ref.extra = payload.get('extra')

        session.add(role_ref)
        return role_ref


@require_admin_context
def role_update(context, role_id, payload):
    with write_session() as session:
        # Retrieve role's details first
        role_ref = role_get(context, role_id)

        # Update role's details
        new_role_id = role_id
        if payload.get('id') is not None:
            role_ref.id = payload.get('id')
            new_role_id = role_ref.id
        if payload.get('name') is not None:
            role_ref.name = payload.get('name')
        if payload.get('extra') is not None:
            role_ref.extra = payload.get('extra')
        if payload.get('domain_id') is not None:
            role_ref.domain_id = payload.get('domain_id')
        role_ref.save(session)

        # Need to update the role_id in assignment table
        # if the role id is updated
        if role_id != new_role_id:
            assignments = assignment_get(context, role_id=role_id,
                                         first=False)
            for assignment in assignments:
                assignment.role_id = new_role_id
                assignment.save(session)

        return role_ref


###################

# identity assignment

###################

@require_context
def assignment_get_all(context):
    return model_query(context, assignment_model.RoleAssignment). \
        all()


@require_context
def assignment_get(context, type=None, actor_id=None, target_id=None,
                   role_id=None, inherited=None, first=True):
    # Query all records
    options = [type, actor_id, target_id, role_id, inherited]
    if all(option is None for option in options):
        if first:
            result = model_query(context, assignment_model.RoleAssignment). \
                first()
            if not result:
                raise exception.ProjectRoleAssignmentNotFound()
        else:
            result = model_query(context, assignment_model.RoleAssignment). \
                all()
        return result

    # Query with filer
    condition = {}
    if type:
        condition.update({'type': type})
    if target_id:
        condition.update({'target_id': target_id})
    if actor_id:
        condition.update({'actor_id': actor_id})
    if role_id:
        condition.update({'role_id': role_id})
    if inherited:
        condition.update({'inherited': inherited})

    if first:
        result = model_query(context, assignment_model.RoleAssignment). \
            filter_by(**condition). \
            first()
        if not result:
            raise exception.ProjectRoleAssignmentNotFound()
    else:
        result = model_query(context, assignment_model.RoleAssignment). \
            filter_by(**condition). \
            all()
    return result


@require_admin_context
def assignment_create(context, payload):
    with write_session() as session:
        assignment_ref = assignment_model.RoleAssignment()

        assignment_ref.type = payload.get('type')
        assignment_ref.actor_id = payload.get('actor_id')
        assignment_ref.target_id = payload.get('target_id')
        assignment_ref.role_id = payload.get('role_id')
        assignment_ref.inherited = payload.get('inherited')

        session.add(assignment_ref)
        return assignment_ref


@require_admin_context
def assignment_update(context, actor_id, payload):
    with write_session() as session:
        # Retrieve the role assignment's details first
        assignment_ref = assignment_get(context, actor_id)

        # Update role assignment's details
        if payload.get('type') is not None:
            assignment_ref.type = payload.get('type')
        if payload.get('actor_id') is not None:
            assignment_ref.actor_id = payload.get('actor_id')
        if payload.get('target_id') is not None:
            assignment_ref.target_id = payload.get('target_id')
        if payload.get('role_id') is not None:
            assignment_ref.role_id = payload.get('role_id')
        if payload.get('inherited') is not None:
            assignment_ref.inherited = payload.get('inherited')

        assignment_ref.save(session)
        return assignment_ref


##################################

# identity token revocation events

##################################

@require_context
def revoke_event_get_all(context):
    return model_query(context, revoke_event_model.RevocationEvent). \
        all()


@require_context
def revoke_event_get(context, id=None, project_id=None, user_id=None,
                     role_id=None, audit_id=None, issued_before=None):
    # Query with filer
    condition = {}
    if id:
        condition.update({'id': id})
    if project_id:
        condition.update({'project_id': project_id})
    if user_id:
        condition.update({'user_id': user_id})
    if role_id:
        condition.update({'role_id': role_id})
    if audit_id:
        condition.update({'audit_id': audit_id})
    if issued_before:
        condition.update({'issued_before': issued_before})

    result = model_query(context, revoke_event_model.RevocationEvent). \
        filter_by(**condition). \
        first()
    if not result:
        raise exception.RevokeEventNotFound()

    return result


@require_admin_context
def revoke_event_create(context, payload):
    with write_session() as session:
        revoke_event_ref = revoke_event_model.RevocationEvent()

        revoke_event_ref.domain_id = payload.get('domain_id')
        revoke_event_ref.project_id = payload.get('project_id')
        revoke_event_ref.user_id = payload.get('user_id')
        revoke_event_ref.role_id = payload.get('role_id')
        revoke_event_ref.trust_id = payload.get('trust_id')
        revoke_event_ref.consumer_id = payload.get('consumer_id')
        revoke_event_ref.access_token_id = payload.get('access_token_id')
        revoke_event_ref.issued_before = payload.get('issued_before')
        revoke_event_ref.expires_at = payload.get('expires_at')
        revoke_event_ref.revoked_at = payload.get('revoked_at')
        revoke_event_ref.audit_id = payload.get('audit_id')
        revoke_event_ref.audit_chain_id = payload.get('audit_chain_id')

        session.add(revoke_event_ref)
        return revoke_event_ref


@require_admin_context
def revoke_event_delete(context, id=None, user_id=None, audit_id=None,
                        issued_before=None):
    with write_session() as session:
        revoke_event_ref = revoke_event_get(context, id=id, user_id=user_id,
                                            audit_id=audit_id,
                                            issued_before=issued_before)
        session.delete(revoke_event_ref)
