# Copyright 2012 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
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

import datetime

import sqlalchemy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import orm
from sqlalchemy.orm import collections

from keystone.common import sql
from keystone.identity.backends import resource_options as iro


class User(sql.ModelBase, sql.ModelDictMixinWithExtras):
    __tablename__ = 'user'
    attributes = ['id', 'name', 'domain_id', 'password', 'enabled',
                  'default_project_id', 'password_expires_at']
    readonly_attributes = ['id', 'password_expires_at', 'password']
    resource_options_registry = iro.USER_OPTIONS_REGISTRY
    id = sql.Column(sql.String(64), primary_key=True)
    domain_id = sql.Column(sql.String(64), nullable=False)
    _enabled = sql.Column('enabled', sql.Boolean)
    extra = sql.Column(sql.JsonBlob())
    default_project_id = sql.Column(sql.String(64), index=True)
    _resource_option_mapper = orm.relationship(
        'UserOption',
        single_parent=True,
        cascade='all,delete,delete-orphan',
        lazy='subquery',
        backref='user',
        collection_class=collections.attribute_mapped_collection('option_id'))
    local_user = orm.relationship('LocalUser', uselist=False,
                                  single_parent=True, lazy='subquery',
                                  cascade='all,delete-orphan', backref='user')
    federated_users = orm.relationship('FederatedUser',
                                       uselist=False,
                                       single_parent=True,
                                       lazy='subquery',
                                       cascade='all,delete-orphan',
                                       backref='user')
    nonlocal_user = orm.relationship('NonLocalUser',
                                     uselist=False,
                                     single_parent=True,
                                     lazy='subquery',
                                     cascade='all,delete-orphan',
                                     backref='user')
    created_at = sql.Column(sql.DateTime, nullable=True)
    last_active_at = sql.Column(sql.Date, nullable=True)
    # unique constraint needed here to support composite fk constraints
    __table_args__ = (sql.UniqueConstraint('id', 'domain_id'), {})


class LocalUser(sql.ModelBase, sql.ModelDictMixin):
    __tablename__ = 'local_user'
    attributes = ['id', 'user_id', 'domain_id', 'name']
    id = sql.Column(sql.Integer, primary_key=True)
    user_id = sql.Column(sql.String(64))
    domain_id = sql.Column(sql.String(64), nullable=False)
    name = sql.Column(sql.String(255), nullable=False)
    passwords = orm.relationship('Password',
                                 single_parent=True,
                                 cascade='all,delete-orphan',
                                 lazy='subquery',
                                 backref='local_user',
                                 order_by='Password.created_at_int')
    failed_auth_count = sql.Column(sql.Integer, nullable=True)
    failed_auth_at = sql.Column(sql.DateTime, nullable=True)
    __table_args__ = (
        sql.UniqueConstraint('user_id'),
        sql.UniqueConstraint('domain_id', 'name'),
        sqlalchemy.ForeignKeyConstraint(['user_id', 'domain_id'],
                                        ['user.id', 'user.domain_id'],
                                        onupdate='CASCADE', ondelete='CASCADE')
    )


class Password(sql.ModelBase, sql.ModelDictMixin):
    __tablename__ = 'password'
    attributes = ['id', 'local_user_id', 'password', 'password_hash',
                  'created_at', 'expires_at']
    id = sql.Column(sql.Integer, primary_key=True)
    local_user_id = sql.Column(sql.Integer, sql.ForeignKey('local_user.id',
                               ondelete='CASCADE'))
    # TODO(notmorgan): in the Q release the "password" field can be dropped as
    # long as data migration exists to move the hashes over to the
    # password_hash column if no value is in the password_hash column.
    password = sql.Column(sql.String(128), nullable=True)
    password_hash = sql.Column(sql.String(255), nullable=True)

    # TODO(lbragstad): Once Rocky opens for development, the _created_at and
    # _expires_at attributes/columns can be removed from the schema. The
    # migration ensures all passwords are converted from datetime objects to
    # big integers. The old datetime columns and their corresponding attributes
    # in the model are no longer required.
    # created_at default set here to safe guard in case it gets missed
    _created_at = sql.Column('created_at', sql.DateTime, nullable=False,
                             default=datetime.datetime.utcnow)
    _expires_at = sql.Column('expires_at', sql.DateTime, nullable=True)
    # set the default to 0, a 0 indicates it is unset.
    created_at_int = sql.Column(sql.DateTimeInt(), nullable=False,
                                default=datetime.datetime.utcnow)
    expires_at_int = sql.Column(sql.DateTimeInt(), nullable=True)
    self_service = sql.Column(sql.Boolean, default=False, nullable=False,
                              server_default='0')

    @hybrid_property
    def created_at(self):
        return self.created_at_int or self._created_at

    @created_at.setter
    def created_at(self, value):
        self._created_at = value
        self.created_at_int = value

    @hybrid_property
    def expires_at(self):
        return self.expires_at_int or self._expires_at

    @expires_at.setter
    def expires_at(self, value):
        self._expires_at = value
        self.expires_at_int = value


class FederatedUser(sql.ModelBase, sql.ModelDictMixin):
    __tablename__ = 'federated_user'
    attributes = ['id', 'user_id', 'idp_id', 'protocol_id', 'unique_id',
                  'display_name']
    id = sql.Column(sql.Integer, primary_key=True)
    user_id = sql.Column(sql.String(64), sql.ForeignKey('user.id',
                                                        ondelete='CASCADE'))
    idp_id = sql.Column(sql.String(64), sql.ForeignKey('identity_provider.id',
                                                       ondelete='CASCADE'))
    protocol_id = sql.Column(sql.String(64), nullable=False)
    unique_id = sql.Column(sql.String(255), nullable=False)
    display_name = sql.Column(sql.String(255), nullable=True)
    __table_args__ = (
        sql.UniqueConstraint('idp_id', 'protocol_id', 'unique_id'),
        sqlalchemy.ForeignKeyConstraint(['protocol_id', 'idp_id'],
                                        ['federation_protocol.id',
                                         'federation_protocol.idp_id'])
    )


class NonLocalUser(sql.ModelBase, sql.ModelDictMixin):
    """SQL data model for nonlocal users (LDAP and custom)."""

    __tablename__ = 'nonlocal_user'
    attributes = ['domain_id', 'name', 'user_id']
    domain_id = sql.Column(sql.String(64), primary_key=True)
    name = sql.Column(sql.String(255), primary_key=True)
    user_id = sql.Column(sql.String(64))
    __table_args__ = (
        sql.UniqueConstraint('user_id'),
        sqlalchemy.ForeignKeyConstraint(
            ['user_id', 'domain_id'], ['user.id', 'user.domain_id'],
            onupdate='CASCADE', ondelete='CASCADE'),)


class Group(sql.ModelBase, sql.ModelDictMixinWithExtras):
    __tablename__ = 'group'
    attributes = ['id', 'name', 'domain_id', 'description']
    id = sql.Column(sql.String(64), primary_key=True)
    name = sql.Column(sql.String(64), nullable=False)
    domain_id = sql.Column(sql.String(64), nullable=False)
    description = sql.Column(sql.Text())
    extra = sql.Column(sql.JsonBlob())
    # Unique constraint across two columns to create the separation
    # rather than just only 'name' being unique
    __table_args__ = (sql.UniqueConstraint('domain_id', 'name'),)


class UserGroupMembership(sql.ModelBase, sql.ModelDictMixin):
    """Group membership join table."""

    __tablename__ = 'user_group_membership'
    user_id = sql.Column(sql.String(64),
                         sql.ForeignKey('user.id'),
                         primary_key=True)
    group_id = sql.Column(sql.String(64),
                          sql.ForeignKey('group.id'),
                          primary_key=True)


class UserOption(sql.ModelBase):
    __tablename__ = 'user_option'
    user_id = sql.Column(sql.String(64), sql.ForeignKey('user.id',
                         ondelete='CASCADE'), nullable=False,
                         primary_key=True)
    option_id = sql.Column(sql.String(4), nullable=False,
                           primary_key=True)
    option_value = sql.Column(sql.JsonBlob, nullable=True)

    def __init__(self, option_id, option_value):
        self.option_id = option_id
        self.option_value = option_value


# These two models are missed in keystone identity model
class IdentityProvider(sql.ModelBase, sql.ModelDictMixin):
    __tablename__ = 'identity_provider'
    id = sql.Column(sql.String(64), primary_key=True)


class FederationProtocol(sql.ModelBase, sql.ModelDictMixin):
    __tablename__ = 'federation_protocol'
    id = sql.Column(sql.String(64), primary_key=True)
    idp_id = sql.Column(sql.String(64), sql.ForeignKey('identity_provider.id',
                                                       ondelete='CASCADE'))
