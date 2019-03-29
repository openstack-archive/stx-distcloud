# Copyright 2015 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright (c) 2017-2019 Wind River Systems, Inc.
#
# The right to copy, distribute, modify, or otherwise make use
# of this software may be licensed only pursuant to the terms
# of an applicable Wind River license agreement.
#

import itertools
import six.moves

# import six

from netaddr import AddrFormatError
from netaddr import IPAddress
from netaddr import IPNetwork

from dcmanager.common import consts
from dcmanager.common import exceptions
from dcmanager.db import api as db_api
from dcmanager.drivers.openstack import vim

from controllerconfig.common.exceptions import ValidateFail


def get_import_path(cls):
    return cls.__module__ + "." + cls.__name__


# Returns a iterator of tuples containing batch_size number of objects in each
def get_batch_projects(batch_size, project_list, fillvalue=None):
    args = [iter(project_list)] * batch_size
    return six.moves.zip_longest(fillvalue=fillvalue, *args)


# to do validate the quota limits
def validate_quota_limits(payload):
    for resource in payload:
        # Check valid resource name
        if resource not in itertools.chain(consts.CINDER_QUOTA_FIELDS,
                                           consts.NOVA_QUOTA_FIELDS,
                                           consts.NEUTRON_QUOTA_FIELDS):
            raise exceptions.InvalidInputError
        # Check valid quota limit value in case for put/post
        if isinstance(payload, dict) and (not isinstance(
                payload[resource], int) or payload[resource] <= 0):
            raise exceptions.InvalidInputError


def get_sw_update_opts(context,
                       for_sw_update=False, subcloud_id=None):
        """Get sw update options for a subcloud

        :param context: request context object.
        :param for_sw_update: return the default options if subcloud options
                              are empty. Useful for retrieving sw update
                              options on application of patch strategy.
        :param subcloud_id: id of subcloud.

        """

        if subcloud_id is None:
            # Requesting defaults. Return constants if no entry in db.
            sw_update_opts_ref = db_api.sw_update_opts_default_get(context)
            if not sw_update_opts_ref:
                sw_update_opts_dict = vim.SW_UPDATE_OPTS_CONST_DEFAULT
                return sw_update_opts_dict
        else:
            # requesting subcloud options
            sw_update_opts_ref = db_api.sw_update_opts_get(context,
                                                           subcloud_id)
            if sw_update_opts_ref:
                subcloud_name = db_api.subcloud_get(context, subcloud_id).name
                return db_api.sw_update_opts_w_name_db_model_to_dict(
                    sw_update_opts_ref, subcloud_name)
            elif for_sw_update:
                sw_update_opts_ref = db_api.sw_update_opts_default_get(context)
                if not sw_update_opts_ref:
                    sw_update_opts_dict = vim.SW_UPDATE_OPTS_CONST_DEFAULT
                    return sw_update_opts_dict
            else:
                raise exceptions.SubcloudPatchOptsNotFound(
                    subcloud_id=subcloud_id)

        return db_api.sw_update_opts_w_name_db_model_to_dict(
            sw_update_opts_ref, consts.SW_UPDATE_DEFAULT_TITLE)


def ip_version_to_string(ip_version):
    """Determine whether a nameserver address is valid."""
    if ip_version == 4:
        return "IPv4"
    elif ip_version == 6:
        return "IPv6"
    else:
        return "IP"


def validate_network_str(network_str, minimum_size,
                         existing_networks=None, multicast=False):
    """Determine whether a network is valid."""
    try:
        network = IPNetwork(network_str)
        if network.ip != network.network:
            raise ValidateFail("Invalid network address")
        elif network.size < minimum_size:
            raise ValidateFail("Subnet too small - must have at least %d "
                               "addresses" % minimum_size)
        elif network.version == 6 and network.prefixlen < 64:
            raise ValidateFail("IPv6 minimum prefix length is 64")
        elif existing_networks:
            if any(network.ip in subnet for subnet in existing_networks):
                raise ValidateFail("Subnet overlaps with another "
                                   "configured subnet")
        elif multicast and not network.is_multicast():
            raise ValidateFail("Invalid subnet - must be multicast")
        return network
    except AddrFormatError:
        raise ValidateFail(
            "Invalid subnet - not a valid IP subnet")


def validate_address_str(ip_address_str, network):
    """Determine whether an address is valid."""
    try:
        ip_address = IPAddress(ip_address_str)
        if ip_address.version != network.version:
            msg = ("Invalid IP version - must match network version " +
                   ip_version_to_string(network.version))
            raise ValidateFail(msg)
        elif ip_address == network:
            raise ValidateFail("Cannot use network address")
        elif ip_address == network.broadcast:
            raise ValidateFail("Cannot use broadcast address")
        elif ip_address not in network:
            raise ValidateFail(
                "Address must be in subnet %s" % str(network))
        return ip_address
    except AddrFormatError:
        raise ValidateFail(
            "Invalid address - not a valid IP address")
