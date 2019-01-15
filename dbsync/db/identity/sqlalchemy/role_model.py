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

# NOTE(henry-nash): From the manager and above perspective, the domain_id
# attribute of a role is nullable.  However, to ensure uniqueness in
# multi-process configurations, it is better to still use a sql uniqueness
# constraint. Since the support for a nullable component of a uniqueness
# constraint across different sql databases is mixed, we instead store a
# special value to represent null, as defined in NULL_DOMAIN_ID below.
NULL_DOMAIN_ID = '<<null>>'


class RoleTable(sql.ModelBase, sql.ModelDictMixinWithExtras):

    __tablename__ = 'role'
    attributes = ['id', 'name', 'domain_id']
    id = sql.Column(sql.String(64), primary_key=True)
    name = sql.Column(sql.String(255), nullable=False)
    domain_id = sql.Column(sql.String(64), nullable=False,
                           server_default=NULL_DOMAIN_ID)
    extra = sql.Column(sql.JsonBlob())
    __table_args__ = (sql.UniqueConstraint('name', 'domain_id'),)
