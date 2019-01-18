# Copyright 2012-13 OpenStack Foundation
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

from keystone.common import sql
from keystone import exception


class AssignmentType(object):
    USER_PROJECT = 'UserProject'
    GROUP_PROJECT = 'GroupProject'
    USER_DOMAIN = 'UserDomain'
    GROUP_DOMAIN = 'GroupDomain'

    @classmethod
    def calculate_type(cls, user_id, group_id, project_id, domain_id):
        if user_id:
            if project_id:
                return cls.USER_PROJECT
            if domain_id:
                return cls.USER_DOMAIN
        if group_id:
            if project_id:
                return cls.GROUP_PROJECT
            if domain_id:
                return cls.GROUP_DOMAIN
        # Invalid parameters combination
        raise exception.AssignmentTypeCalculationError(**locals())


class RoleAssignment(sql.ModelBase, sql.ModelDictMixin):
    __tablename__ = 'assignment'
    attributes = ['type', 'actor_id', 'target_id', 'role_id', 'inherited']
    # NOTE(henry-nash): Postgres requires a name to be defined for an Enum
    type = sql.Column(
        sql.Enum(AssignmentType.USER_PROJECT, AssignmentType.GROUP_PROJECT,
                 AssignmentType.USER_DOMAIN, AssignmentType.GROUP_DOMAIN,
                 name='type'),
        nullable=False)
    actor_id = sql.Column(sql.String(64), nullable=False)
    target_id = sql.Column(sql.String(64), nullable=False)
    role_id = sql.Column(sql.String(64), nullable=False)
    inherited = sql.Column(sql.Boolean, default=False, nullable=False)
    __table_args__ = (
        sql.PrimaryKeyConstraint('type', 'actor_id', 'target_id', 'role_id',
                                 'inherited'),
        sql.Index('ix_actor_id', 'actor_id'),
    )

    def to_dict(self):
        """Override parent method with a simpler implementation.

        RoleAssignment doesn't have non-indexed 'extra' attributes, so the
        parent implementation is not applicable.
        """
        return dict(self.items())
