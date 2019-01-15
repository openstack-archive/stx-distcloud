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

from oslo_log import log

from keystone.common import sql


LOG = log.getLogger(__name__)


class Project(sql.ModelBase, sql.ModelDictMixinWithExtras):
    # NOTE(henry-nash): From the manager and above perspective, the domain_id
    # is nullable.  However, to ensure uniqueness in multi-process
    # configurations, it is better to still use the sql uniqueness constraint.
    # Since the support for a nullable component of a uniqueness constraint
    # across different sql databases is mixed, we instead store a special value
    # to represent null, as defined in NULL_DOMAIN_ID above.

    __tablename__ = 'project'
    attributes = ['id', 'name', 'domain_id', 'description', 'enabled',
                  'parent_id', 'is_domain']
    id = sql.Column(sql.String(64), primary_key=True)
    name = sql.Column(sql.String(64), nullable=False)
    domain_id = sql.Column(sql.String(64), sql.ForeignKey('project.id'),
                           nullable=False)
    description = sql.Column(sql.Text())
    enabled = sql.Column(sql.Boolean)
    extra = sql.Column(sql.JsonBlob())
    parent_id = sql.Column(sql.String(64), sql.ForeignKey('project.id'))
    is_domain = sql.Column(sql.Boolean, default=False, nullable=False,
                           server_default='0')
    # Unique constraint across two columns to create the separation
    # rather than just only 'name' being unique
    __table_args__ = (sql.UniqueConstraint('domain_id', 'name'),)
