# Copyright (c) 2016 Ericsson AB.

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

RPC_API_VERSION = "1.0"

TOPIC_DC_DBSYNC = "dbsync"

PATCH_VAULT_DIR = "/opt/patch-vault"

# Well known region names
SYSTEM_CONTROLLER_NAME = "SystemController"
DEFAULT_REGION_NAME = "RegionOne"

# Subcloud management state
MANAGEMENT_UNMANAGED = "unmanaged"
MANAGEMENT_MANAGED = "managed"

# Subcloud availability status
AVAILABILITY_OFFLINE = "offline"
AVAILABILITY_ONLINE = "online"

# Subcloud sync status
SYNC_STATUS_UNKNOWN = "unknown"
SYNC_STATUS_IN_SYNC = "in-sync"
SYNC_STATUS_OUT_OF_SYNC = "out-of-sync"

# Subcloud endpoint related database fields
ENDPOINT_SYNC_STATUS = "endpoint_sync_status"
SYNC_STATUS = "sync_status"
ENDPOINT_TYPE = "endpoint_type"

# Service group status
SERVICE_GROUP_STATUS_ACTIVE = "active"

# Availability fail count
AVAIL_FAIL_COUNT_TO_ALARM = 2
AVAIL_FAIL_COUNT_MAX = 9999

# Software update type
SW_UPDATE_TYPE_PATCH = "patch"
SW_UPDATE_TYPE_UPGRADE = "upgrade"

# Software update states
SW_UPDATE_STATE_INITIAL = "initial"
SW_UPDATE_STATE_APPLYING = "applying"
SW_UPDATE_STATE_ABORT_REQUESTED = "abort requested"
SW_UPDATE_STATE_ABORTING = "aborting"
SW_UPDATE_STATE_COMPLETE = "complete"
SW_UPDATE_STATE_ABORTED = "aborted"
SW_UPDATE_STATE_FAILED = "failed"
SW_UPDATE_STATE_DELETING = "deleting"
SW_UPDATE_STATE_DELETED = "deleted"

# Software update actions
SW_UPDATE_ACTION_APPLY = "apply"
SW_UPDATE_ACTION_ABORT = "abort"

# Subcloud apply types
SUBCLOUD_APPLY_TYPE_PARALLEL = "parallel"
SUBCLOUD_APPLY_TYPE_SERIAL = "serial"

# Strategy step states
STRATEGY_STATE_INITIAL = "initial"
STRATEGY_STATE_UPDATING_PATCHES = "updating patches"
STRATEGY_STATE_CREATING_STRATEGY = "creating strategy"
STRATEGY_STATE_APPLYING_STRATEGY = "applying strategy"
STRATEGY_STATE_FINISHING = "finishing"
STRATEGY_STATE_COMPLETE = "complete"
STRATEGY_STATE_ABORTED = "aborted"
STRATEGY_STATE_FAILED = "failed"

SW_UPDATE_DEFAULT_TITLE = "all clouds default"
