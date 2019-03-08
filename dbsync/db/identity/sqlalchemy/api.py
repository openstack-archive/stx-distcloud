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

from sqlalchemy import Table, MetaData
from sqlalchemy.sql import select

from dbsync.common import exceptions as exception
from dbsync.common.i18n import _

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


def get_connection():
    return get_engine().connect()


def row2dict(table, row):
    d = {}
    for c in table.columns:
        c_value = getattr(row, c.name)
        d[c.name] = c_value

    return d


def index2column(r_table, index_name):
    column = None
    for c in r_table.columns:
        if c.name == index_name:
            column = c
            break

    return column


def query(connection, table, index_name=None, index_value=None):
    meta = MetaData()
    engine = get_engine()
    r_table = Table(table, meta, autoload=True, autoload_with=engine)

    if index_name and index_value:
        c = index2column(r_table, index_name)
        stmt = select([r_table]).where(c == index_value)
    else:
        stmt = select([r_table])

    records = []
    result = connection.execute(stmt)
    for row in result:
        # convert the row into a dictionary
        d = row2dict(r_table, row)
        records.append(d)

    return records


def insert(connection, table, data):
    meta = MetaData()
    engine = get_engine()
    r_table = Table(table, meta, autoload=True, autoload_with=engine)
    stmt = r_table.insert()

    connection.execute(stmt, data)


def delete(connection, table, index_name, index_value):
    meta = MetaData()
    engine = get_engine()
    r_table = Table(table, meta, autoload=True, autoload_with=engine)

    c = index2column(r_table, index_name)
    stmt = r_table.delete().where(c == index_value)
    connection.execute(stmt)


def update(connection, table, index_name, index_value, data):
    meta = MetaData()
    engine = get_engine()
    r_table = Table(table, meta, autoload=True, autoload_with=engine)

    c = index2column(r_table, index_name)
    stmt = r_table.update().where(c == index_value).values(data)
    connection.execute(stmt)


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


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


###################

# identity users

###################

@require_context
def user_get_all(context):
    result = []

    conn = get_connection()
    with conn.begin():
        # user table
        users = query(conn, 'user')
        # local_user table
        local_users = query(conn, 'local_user')
        # password table
        passwords = query(conn, 'password')

    for local_user in local_users:
        user = {'user': user for user in users if user['id']
                == local_user['user_id']}
        user_passwords = {'password': [password for password in passwords
                                       if password['local_user_id'] ==
                                       local_user['id']]}
        user_consolidated = dict({'local_user': local_user}.items() +
                                 user.items() + user_passwords.items())
        result.append(user_consolidated)

    return result


@require_context
def user_get(context, user_id):
    result = {}

    conn = get_connection()
    with conn.begin():
        # user table
        users = query(conn, 'user', 'id', user_id)
        if not users:
            raise exception.UserNotFound(user_id=user_id)
        result['user'] = users[0]
        # local_user table
        local_users = query(conn, 'local_user', 'user_id', user_id)
        if not local_users:
            raise exception.UserNotFound(user_id=user_id)
        result['local_user'] = local_users[0]
        # password table
        result['password'] = []
        if result['local_user']:
            result['password'] = query(conn, 'password',
                                       'local_user_id',
                                       result['local_user'].get('id'))

    return result


@require_admin_context
def user_create(context, payload):
    users = [payload['user']]
    local_users = [payload['local_user']]
    passwords = payload['password']

    conn = get_connection()
    with conn.begin():
        insert(conn, 'user', users)

        # ignore auto generated id
        for local_user in local_users:
            local_user.pop('id', None)
        insert(conn, 'local_user', local_users)

        inserted_local_users = query(conn, 'local_user', 'user_id',
                                     payload['local_user']['user_id'])

        if not inserted_local_users:
            raise exception.UserNotFound(user_id=payload['local_user']
                                         ['user_id'])

        for password in passwords:
            # ignore auto generated id
            password.pop('id', None)
            password['local_user_id'] = inserted_local_users[0]['id']

        insert(conn, 'password', passwords)

    return user_get(context, payload['user']['id'])


@require_admin_context
def user_update(context, user_id, payload):
    conn = get_connection()
    with conn.begin():
        # user table
        table = 'user'
        new_user_id = user_id
        if table in payload:
            user = payload[table]
            update(conn, table, 'id', user_id, user)
            new_user_id = user.get('id')
        # local_user table
        table = 'local_user'
        if table in payload:
            local_user = payload[table]
            # ignore auto generated id
            local_user.pop('id', None)
            update(conn, table, 'user_id', user_id, local_user)
            updated_local_users = query(conn, table, 'user_id',
                                        new_user_id)

            if not updated_local_users:
                raise exception.UserNotFound(user_id=payload[table]['user_id'])
            # password table
            table = 'password'
            if table in payload:
                delete(conn, table, 'local_user_id',
                       updated_local_users[0]['id'])
                passwords = payload[table]
                for password in passwords:
                    # ignore auto generated ids
                    password.pop('id', None)
                    password['local_user_id'] = \
                        updated_local_users[0]['id']
                    insert(conn, table, password)
        # Need to update the actor_id in assignment table
        # if the user id is updated
        if user_id != new_user_id:
            table = 'assignment'
            assignment = {'actor_id': new_user_id}
            update(conn, table, 'actor_id', user_id, assignment)

    return user_get(context, new_user_id)


###################

# identity projects

###################

@require_context
def project_get_all(context):
    result = []

    conn = get_connection()
    with conn.begin():
        # project table
        projects = query(conn, 'project')

    for project in projects:
        project_consolidated = {'project': project}
        result.append(project_consolidated)

    return result


@require_context
def project_get(context, project_id):
    result = {}

    conn = get_connection()
    with conn.begin():
        # project table
        projects = query(conn, 'project', 'id', project_id)
        if not projects:
            raise exception.ProjectNotFound(project_id=project_id)
        result['project'] = projects[0]

    return result


@require_admin_context
def project_create(context, payload):
    projects = [payload['project']]

    conn = get_connection()
    with conn.begin():
        insert(conn, 'project', projects)

    return project_get(context, payload['project']['id'])


@require_admin_context
def project_update(context, project_id, payload):
    conn = get_connection()
    with conn.begin():
        # project table
        table = 'project'
        new_project_id = project_id
        if table in payload:
            project = payload[table]
            update(conn, table, 'id', project_id, project)
            new_project_id = project.get('id')

        # Need to update the target_id in assignment table
        # if the project id is updated
        if project_id != new_project_id:
            table = 'assignment'
            assignment = {'target_id': new_project_id}
            update(conn, table, 'target_id', project_id, assignment)

    return project_get(context, new_project_id)


###################

# identity roles

###################

@require_context
def role_get_all(context):
    result = []

    conn = get_connection()
    with conn.begin():
        # role table
        roles = query(conn, 'role')

    for role in roles:
        role_consolidated = {'role': role}
        result.append(role_consolidated)

    return result


@require_context
def role_get(context, role_id):
    result = {}

    conn = get_connection()
    with conn.begin():
        # role table
        roles = query(conn, 'role', 'id', role_id)
        if not roles:
            raise exception.RoleNotFound(role_id=role_id)
        result['role'] = roles[0]

    return result


@require_admin_context
def role_create(context, payload):
    roles = [payload['role']]

    conn = get_connection()
    with conn.begin():
        insert(conn, 'role', roles)

    return role_get(context, payload['role']['id'])


@require_admin_context
def role_update(context, role_id, payload):
    conn = get_connection()
    with conn.begin():
        # role table
        table = 'role'
        new_role_id = role_id
        if table in payload:
            role = payload[table]
            update(conn, table, 'id', role_id, role)
            new_role_id = role.get('id')

        # Need to update the role_id in assignment table
        # if the role id is updated
        if role_id != new_role_id:
            table = 'assignment'
            assignment = {'role_id': new_role_id}
            update(conn, table, 'role_id', role_id, assignment)

    return role_get(context, new_role_id)


##################################

# identity token revocation events

##################################

@require_context
def revoke_event_get_all(context):
    result = []

    conn = get_connection()
    with conn.begin():
        # revocation_event table
        revoke_events = query(conn, 'revocation_event')

    for revoke_event in revoke_events:
        revoke_event_consolidated = {'revocation_event': revoke_event}
        result.append(revoke_event_consolidated)

    return result


@require_context
def revoke_event_get_by_audit(context, audit_id):
    result = {}

    conn = get_connection()
    with conn.begin():
        # revocation_event table
        revoke_events = query(conn, 'revocation_event', 'audit_id',
                              audit_id)
        if not revoke_events:
            raise exception.RevokeEventNotFound()
        result['revocation_event'] = revoke_events[0]

    return result


@require_context
def revoke_event_get_by_user(context, user_id, issued_before):
    result = {}

    conn = get_connection()
    with conn.begin():
        # revocation_event table
        events = query(conn, 'revocation_event', 'user_id', user_id)
    revoke_events = [event for event in events if
                     str(event['issued_before']) == issued_before]
    if not revoke_events:
        raise exception.RevokeEventNotFound()
    result['revocation_event'] = revoke_events[0]

    return result


@require_admin_context
def revoke_event_create(context, payload):
    revoke_event = payload['revocation_event']
    # ignore auto generated id
    revoke_event.pop('id', None)

    revoke_events = [revoke_event]

    conn = get_connection()
    with conn.begin():
        insert(conn, 'revocation_event', revoke_events)

    result = {}
    if revoke_event.get('audit_id') is not None:
        result = revoke_event_get_by_audit(context,
                                           revoke_event.get('audit_id'))
    elif (revoke_event.get('user_id') is not None) and \
            (revoke_event.get('issued_before') is not None):
        result = revoke_event_get_by_user(context,
                                          revoke_event.get('user_id'),
                                          revoke_event.get('issued_before'))
    return result


@require_admin_context
def revoke_event_delete_by_audit(context, audit_id):
    conn = get_connection()
    with conn.begin():
        delete(conn, 'revocation_event', 'audit_id', audit_id)


@require_admin_context
def revoke_event_delete_by_user(context, user_id, issued_before):
    conn = get_connection()
    with conn.begin():
        result = revoke_event_get_by_user(context, user_id, issued_before)
        event_id = result['revocation_event']['id']
        delete(conn, 'revocation_event', 'id', event_id)
