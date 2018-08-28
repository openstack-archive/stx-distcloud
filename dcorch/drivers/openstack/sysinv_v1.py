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

import hashlib
import os
import tsconfig.tsconfig as tsc

from cgtsclient import client as cgts_client
from cgtsclient.exc import HTTPConflict
from cgtsclient.exc import HTTPNotFound
from cgtsclient.v1.icommunity import CREATION_ATTRIBUTES \
    as SNMP_COMMUNITY_CREATION_ATTRIBUTES
from cgtsclient.v1.itrapdest import CREATION_ATTRIBUTES \
    as SNMP_TRAPDEST_CREATION_ATTRIBUTES
from oslo_log import log
from sysinv.common import constants as sysinv_constants

from dcorch.common import consts
from dcorch.common import exceptions
from dcorch.drivers import base

LOG = log.getLogger(__name__)

API_VERSION = '1'


def make_sysinv_patch(update_dict):
    patch = []
    for k, v in update_dict.iteritems():
        key = k
        if not k.startswith('/'):
            key = '/' + key

        p = {'path': key, 'value': v, 'op': 'replace'}
        patch.append(dict(p))

    LOG.debug("make_sysinv_patch patch={}".format(patch))

    return patch


class SysinvClient(base.DriverBase):
    """Sysinv V1 driver."""

    # TODO(John): This could go into cgtsclient/v1/remotelogging.py
    REMOTELOGGING_PATCH_ATTRS = ['ip_address', 'enabled', 'transport', 'port',
                                 'action']

    def __init__(self, region_name, session):
        self._expired = False
        self.api_version = API_VERSION
        self.region_name = region_name
        self.session = session

        self.client = self.update_client(
            self.api_version, self.region_name, self.session)

    def update_client(self, api_version, region_name, session):
        try:
            endpoint = self.session.get_endpoint(
                service_type=consts.ENDPOINT_TYPE_PLATFORM,
                interface=consts.KS_ENDPOINT_INTERNAL,
                region_name=region_name)
            token = session.get_token()
            client = cgts_client.Client(
                api_version,
                endpoint=endpoint,
                token=token)
        except exceptions.ServiceUnavailable:
            raise

        self._expired = False

        return client

    def get_dns(self):
        """Get the dns nameservers for this region

           :return: dns
        """
        idnss = self.client.idns.list()
        if not idnss:
            LOG.info("dns is None for region: %s" % self.region_name)
            return None
        idns = idnss[0]

        LOG.debug("get_dns uuid=%s nameservers=%s" %
                  (idns.uuid, idns.nameservers))

        return idns

    def update_dns(self, nameservers):
        """Update the dns nameservers for this region

           :param: nameservers  csv string
           :return: Nothing
        """
        try:
            idns = self.get_dns()
            if not idns:
                LOG.warn("idns not found %s" % self.region_name)
                return idns

            if idns.nameservers != nameservers:
                if nameservers == "":
                    nameservers = "NC"
                patch = make_sysinv_patch({'nameservers': nameservers,
                                           'action': 'apply'})
                LOG.info("region={} dns update uuid={} patch={}".format(
                         self.region_name, idns.uuid, patch))
                idns = self.client.idns.update(idns.uuid, patch)
            else:
                LOG.info("update_dns no changes, skip dns region={} "
                         "update uuid={} nameservers={}".format(
                             self.region_name, idns.uuid, nameservers))
        except Exception as e:
            LOG.error("update_dns exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return idns

    def get_ntp(self):
        """Get the ntp configuration for this region

           :return: ntp
        """
        intps = self.client.intp.list()
        if not intps:
            LOG.info("ntp is None for region: %s" % self.region_name)
            return None
        intp = intps[0]

        LOG.debug("get_ntp uuid=%s enabled=%s ntpservers=%s" %
                  (intp.uuid, intp.enabled, intp.ntpservers))

        return intp

    @staticmethod
    def _same_ntpservers(i1, i2):
        same_ntpservers = True
        if i1 != i2:
            if not i1 and not i2:
                # To catch equivalent ntpservers None vs ""
                same_ntpservers = True
            else:
                same_ntpservers = False
        return same_ntpservers

    def update_ntp(self, enabled, ntpservers):
        """Update the ntpservers for this region

           :param: enabled     string
           :param: ntpservers  csv string
           :return: Nothing
        """
        try:
            intp = self.get_ntp()
            if not intp:
                LOG.warn("intp not found %s" % self.region_name)
                return intp
            if ntpservers == "NC":
                ntpservers = ""
            if intp.enabled != (enabled == "True") or \
               not self._same_ntpservers(intp.ntpservers, ntpservers):
                if ntpservers == "":
                    ntpservers = "NC"
                patch = make_sysinv_patch({'enabled': enabled,
                                           'ntpservers': ntpservers,
                                           'action': 'apply'})
                LOG.info("region={} ntp update uuid={} patch={}".format(
                         self.region_name, intp.uuid, patch))
                intp = self.client.intp.update(intp.uuid, patch)
            else:
                LOG.info("update_ntp no changes, skip ntp region={} "
                         "update uuid={} enabled={} ntpservers={}".format(
                             self.region_name, intp.uuid, enabled, ntpservers))
        except Exception as e:
            LOG.error("update_ntp exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return intp

    def get_ptp(self):
        """Get the ptp configuration for this region

           :return: ptp
        """
        ptps = self.client.ptp.list()
        if not ptps:
            LOG.info("ptp is None for region: %s" % self.region_name)
            return None
        ptp = ptps[0]

        LOG.debug("get_ptp uuid=%s enabled=%s mode=%s "
                  "transport=%s mechanism=%s" %
                  (ptp.uuid, ptp.enabled, ptp.mode,
                   ptp.transport, ptp.mechanism))

        return ptp

    def update_ptp(self, enabled, mode, transport, mechanism):
        """Update the ptp configuration for this region

           :param: enabled
           :param: mode
           :param: transport
           :param: mechanism
           :return: Nothing
        """
        try:
            ptp = self.get_ptp()
            if not ptp:
                LOG.warn("ptp not found %s" % self.region_name)
                return ptp

            if ptp.enabled != (enabled == "True") or \
               ptp.mode != mode or \
               ptp.transport != transport or \
               ptp.mechanism != mechanism:
                patch = make_sysinv_patch({'enabled': enabled},
                                          {'mode': mode},
                                          {'transport': transport},
                                          {'mechanism': mechanism})
                LOG.info("region={} ptp update uuid={} patch={}".format(
                         self.region_name, ptp.uuid, patch))
                ptp = self.client.ptp.update(ptp.uuid, patch)
            else:
                LOG.info("update_ptp no changes, skip ptp region={} "
                         "update uuid={} enabled={} mode={} "
                         "transport={} mechanism={}".format(
                             self.region_name, ptp.uuid,
                             enabled, mode, transport, mechanism))
        except Exception as e:
            LOG.error("update_ptp exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return ptp

    def snmp_trapdest_list(self):
        """Get the trapdest list for this region

           :return: itrapdests list of itrapdest
        """
        itrapdests = self.client.itrapdest.list()
        return itrapdests

    def snmp_trapdest_create(self, trapdest_dict):
        """Add the trapdest for this region

           :param: trapdest_payload dictionary
           :return: itrapdest
        """

        # Example trapdest_dict:
        #     {"ip_address": "10.10.10.12", "community": "cgcs"}
        itrapdest = None
        trapdest_create_dict = {}
        for k, v in trapdest_dict.iteritems():
            if k in SNMP_TRAPDEST_CREATION_ATTRIBUTES:
                trapdest_create_dict[str(k)] = v

        LOG.info("snmp_trapdest_create driver region={}"
                 "trapdest_create_dict={}".format(
                     self.region_name, trapdest_create_dict))
        try:
            itrapdest = self.client.itrapdest.create(**trapdest_create_dict)
        except HTTPConflict:
            LOG.info("snmp_trapdest_create exists region={}"
                     "trapdest_dict={}".format(
                         self.region_name, trapdest_dict))
            # Retrieve the existing itrapdest
            trapdests = self.snmp_trapdest_list()
            for trapdest in trapdests:
                if trapdest.ip_address == trapdest_dict.get('ip_address'):
                    LOG.info("snmp_trapdest_create found existing {}"
                             "for region: {}".format(
                                 trapdest, self.region_name))
                    itrapdest = trapdest
                    break
        except Exception as e:
            LOG.error("snmp_trapdest_create exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return itrapdest

    def snmp_trapdest_delete(self, trapdest_ip_address):
        """Delete the trapdest for this region

           :param: trapdest_ip_address
        """
        try:
            LOG.info("snmp_trapdest_delete region {} ip_address: {}".format(
                     self.region_name, trapdest_ip_address))
            self.client.itrapdest.delete(trapdest_ip_address)
        except HTTPNotFound:
            LOG.info("snmp_trapdest_delete NotFound %s for region: {}".format(
                     trapdest_ip_address, self.region_name))
            raise exceptions.TrapDestNotFound(region_name=self.region_name,
                                              ip_address=trapdest_ip_address)
        except Exception as e:
            LOG.error("snmp_trapdest_delete exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

    def snmp_community_list(self):
        """Get the community list for this region

           :return: icommunitys list of icommunity
        """
        icommunitys = self.client.icommunity.list()
        return icommunitys

    def snmp_community_create(self, community_dict):
        """Add the community for this region

           :param: community_payload dictionary
           :return: icommunity
        """

        # Example community_dict: {"community": "cgcs"}
        icommunity = None
        community_create_dict = {}
        for k, v in community_dict.iteritems():
            if k in SNMP_COMMUNITY_CREATION_ATTRIBUTES:
                community_create_dict[str(k)] = v

        LOG.info("snmp_community_create driver region={}"
                 "community_create_dict={}".format(
                     self.region_name, community_create_dict))
        try:
            icommunity = self.client.icommunity.create(**community_create_dict)
        except HTTPConflict:
            LOG.info("snmp_community_create exists region={}"
                     "community_dict={}".format(
                         self.region_name, community_dict))
            # Retrieve the existing icommunity
            communitys = self.snmp_community_list()
            for community in communitys:
                if community.community == community_dict.get('community'):
                    LOG.info("snmp_community_create found existing {}"
                             "for region: {}".format(
                                 community, self.region_name))
                    icommunity = community
                    break
        except Exception as e:
            LOG.error("snmp_community_create exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return icommunity

    def snmp_community_delete(self, community):
        """Delete the community for this region

           :param: community
        """
        try:
            LOG.info("snmp_community_delete region {} community: {}".format(
                     self.region_name, community))
            self.client.icommunity.delete(community)
        except HTTPNotFound:
            LOG.info("snmp_community_delete NotFound %s for region: {}".format(
                     community, self.region_name))
            raise exceptions.CommunityNotFound(region_name=self.region_name,
                                               community=community)
        except Exception as e:
            LOG.error("snmp_community_delete exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

    def get_remotelogging(self):
        """Get the remotelogging for this region

           :return: remotelogging
        """
        try:
            remoteloggings = self.client.remotelogging.list()
            remotelogging = remoteloggings[0]
        except Exception as e:
            LOG.error("get_remotelogging exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        if not remotelogging:
            LOG.info("remotelogging is None for region: %s" % self.region_name)

        else:
            LOG.debug("get_remotelogging uuid=%s ip_address=%s" %
                      (remotelogging.uuid, remotelogging.ip_address))

        return remotelogging

    def create_remote_logging_patch_from_dict(self, values):
        patch = {}
        action_found = False
        for k, v in values.iteritems():
            if k in self.REMOTELOGGING_PATCH_ATTRS:
                if k == 'action':
                    action_found = True
                elif k == 'enabled' and not isinstance(v, basestring):
                    # api requires a string for enabled
                    if not v:
                        patch[k] = 'false'
                    else:
                        patch[k] = 'true'
                elif k == 'ip_address' and not v:
                    # api requires a non None/empty value
                    continue
                else:
                    patch[k] = v

        if not action_found:
            patch['action'] = 'apply'

        patch = make_sysinv_patch(patch)
        LOG.debug("create_remote_logging_patch_from_dict=%s" % patch)
        return patch

    @staticmethod
    def ip_address_in_patch(patch):
        for p in patch:
            if p['path'] == '/ip_address':
                if p['value']:
                    return True
        LOG.info("No valid ip_address_in_patch: %s" % patch)
        return False

    def update_remotelogging(self, values):
        """Update the remotelogging values for this region

           :param: values  dictionary or payload
           :return: remotelogging
        """
        try:
            remotelogging = self.get_remotelogging()
            if not remotelogging:
                LOG.warn("remotelogging not found %s" % self.region_name)
                return remotelogging

            if isinstance(values, dict):
                patch = self.create_remote_logging_patch_from_dict(values)
            else:
                patch = values

            if (not self.ip_address_in_patch(patch) and
               not remotelogging.ip_address):
                # This region does not have an ip_address set yet
                LOG.info("region={} remotelogging ip_address not set "
                         "uuid={} patch={}. Skip patch operation.".format(
                             self.region_name, remotelogging.uuid, patch))
                return remotelogging

            LOG.info("region={} remotelogging update uuid={} patch={}".format(
                     self.region_name, remotelogging.uuid, patch))
            remotelogging = self.client.remotelogging.update(
                remotelogging.uuid, patch)
        except Exception as e:
            LOG.error("update_remotelogging exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return remotelogging

    def get_firewallrules(self):
        """Get the firewallrules for this region

           :return: firewallrules
        """
        try:
            firewallruless = self.client.firewallrules.list()
            firewallrules = firewallruless[0]
        except Exception as e:
            LOG.error("get_firewallrules region={} "
                      "exception={}".format(self.region_name, e))
            raise exceptions.SyncRequestFailedRetry()

        if not firewallrules:
            LOG.info("firewallrules is None for region: {}".format(
                self.region_name))

        else:
            LOG.info("get_firewallrules uuid=%s firewall_sig=%s" %
                     (firewallrules.uuid, firewallrules.firewall_sig))

        return firewallrules

    def _validate_firewallrules(self, firewall_sig, firewallrules):
        firewallrules_sig = hashlib.md5(firewallrules).hexdigest()

        if firewallrules_sig == firewall_sig:
            return True

        LOG.info("_validate_firewallrules region={} sig={} mismatch "
                 "reference firewall_sig={}".format(
                     self.region_name, firewallrules_sig, firewall_sig))
        return False

    def update_firewallrules(self,
                             firewall_sig,
                             firewallrules=None):
        """Update the firewallrules for this region

           :param: firewall_sig
           :param: firewallrules
           :return: ifirewallrules
        """

        if not firewallrules:
            # firewallrules not provided, obtain from SystemController
            firewall_rules_file = os.path.join(
                tsc.CONFIG_PATH,
                sysinv_constants.FIREWALL_RULES_FILE)

            with open(firewall_rules_file, 'r') as content_file:
                firewallrules = content_file.read()

            LOG.info("update_firewallrules from shared file={}".format(
                firewallrules))

        if not self._validate_firewallrules(firewall_sig, firewallrules):
            raise exceptions.SyncRequestFailedRetry()

        try:
            ifirewallrules = self.client.firewallrules.import_firewall_rules(
                firewallrules)
            LOG.info("region={} firewallrules uuid={} firewall_sig={}".format(
                self.region_name, ifirewallrules.get('uuid'), firewall_sig))
        except Exception as e:
            LOG.error("update_firewallrules exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return ifirewallrules

    def get_certificates(self):
        """Get the certificates for this region

           :return: certificates
        """

        try:
            certificates = self.client.certificate.list()
        except Exception as e:
            LOG.error("get_certificates region={} "
                      "exception={}".format(self.region_name, e))
            raise exceptions.SyncRequestFailedRetry()

        if not certificates:
            LOG.info("No certificates in region: {}".format(
                self.region_name))

        return certificates

    def _validate_certificate(self, signature, certificate):
        # JKUNG need to look at the crypto public serial id
        certificate_sig = hashlib.md5(certificate).hexdigest()

        if certificate_sig == signature:
            return True

        LOG.info("_validate_certificate region={} sig={} mismatch "
                 "reference signature={}".format(
                     self.region_name, certificate_sig, signature))
        return False

    def update_certificate(self,
                           signature,
                           certificate=None,
                           data=None):
        """Update the certificate for this region

           :param: signature of the public certificate
           :param: certificate
           :param: data
           :return: icertificate
        """

        LOG.info("update_certificate signature {} data {}".format(
            signature, data))
        if not certificate:
            tpmconfigs = self.client.tpmconfig.list()
            if tpmconfigs:
                LOG.info("region={} no certificates available, "
                         "tpm configured".format(self.region_name))
                return

            if data:
                data['passphrase'] = None
                mode = data.get('mode', sysinv_constants.CERT_MODE_SSL)
                if mode == sysinv_constants.CERT_MODE_SSL_CA:
                    certificate_files = [sysinv_constants.SSL_CERT_CA_FILE]
                elif mode == sysinv_constants.CERT_MODE_SSL:
                    certificate_files = [sysinv_constants.SSL_PEM_FILE]
                elif mode == sysinv_constants.CERT_MODE_MURANO_CA:
                    certificate_files = [sysinv_constants.MURANO_CERT_CA_FILE]
                elif mode == sysinv_constants.CERT_MODE_MURANO:
                    certificate_files = [sysinv_constants.MURANO_CERT_KEY_FILE,
                                         sysinv_constants.MURANO_CERT_FILE]
                else:
                    LOG.warn("update_certificate mode {} not supported".format(
                        mode))
                    return
            elif signature and signature.startswith(
                    sysinv_constants.CERT_MODE_SSL_CA):
                data['mode'] = sysinv_constants.CERT_MODE_SSL_CA
                certificate_files = [sysinv_constants.SSL_CERT_CA_FILE]
            elif signature and signature.startswith(
                    sysinv_constants.CERT_MODE_SSL):
                data['mode'] = sysinv_constants.CERT_MODE_SSL
                certificate_files = [sysinv_constants.SSL_PEM_FILE]
            elif signature and signature.startswith(
                    sysinv_constants.CERT_MODE_MURANO_CA):
                data['mode'] = sysinv_constants.CERT_MODE_MURANO_CA
                certificate_files = [sysinv_constants.MURANO_CERT_CA_FILE]
            elif signature and signature.startswith(
                    sysinv_constants.CERT_MODE_MURANO + '_'):
                data['mode'] = sysinv_constants.CERT_MODE_MURANO
                certificate_files = [sysinv_constants.MURANO_CERT_KEY_FILE,
                                     sysinv_constants.MURANO_CERT_FILE]
            else:
                LOG.warn("update_certificate signature {} "
                         "not supported".format(signature))
                return

            certificate = ""
            for certificate_file in certificate_files:
                with open(certificate_file, 'r') as content_file:
                    certificate += content_file.read()

            LOG.info("update_certificate from shared file {} {}".format(
                signature, certificate_files))

        if (signature and
                (signature.startswith(sysinv_constants.CERT_MODE_SSL) or
                    (signature.startswith(sysinv_constants.CERT_MODE_TPM)))):
            # ensure https is enabled
            isystem = self.client.isystem.list()[0]
            https_enabled = isystem.capabilities.get('https_enabled', False)
            if not https_enabled:
                isystem = self.client.isystem.update(
                    isystem.uuid,
                    [{"path": "/https_enabled",
                      "value": "true",
                      "op": "replace"}])
                LOG.info("region={} enabled https system={}".format(
                         self.region_name, isystem.uuid))

        try:
            icertificate = self.client.certificate.certificate_install(
                certificate, data)
            LOG.info("update_certificate region={} signature={}".format(
                self.region_name,
                signature))
        except Exception as e:
            LOG.error("update_certificate exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return icertificate

    def get_user(self):
        """Get the user password info for this region

           :return: iuser
        """
        iusers = self.client.iuser.list()
        if not iusers:
            LOG.info("user is None for region: %s" % self.region_name)
            return None
        iuser = iusers[0]

        LOG.debug("get_user uuid=%s passwd_hash=%s" %
                  (iuser.uuid, iuser.passwd_hash))

        return iuser

    def update_user(self, passwd_hash, root_sig, passwd_expiry_days):
        """Update the user passwd for this region

           :param: passwd_hash
           :return: iuser
        """
        try:
            iuser = self.get_user()
            if not iuser:
                LOG.warn("iuser not found %s" % self.region_name)
                return iuser

            if (iuser.passwd_hash != passwd_hash or
               iuser.passwd_expiry_days != passwd_expiry_days):
                patch = make_sysinv_patch(
                    {'passwd_hash': passwd_hash,
                     'passwd_expiry_days': passwd_expiry_days,
                     'root_sig': root_sig,
                     'action': 'apply',
                     })
                LOG.info("region={} user update uuid={} patch={}".format(
                         self.region_name, iuser.uuid, patch))
                iuser = self.client.iuser.update(iuser.uuid, patch)
            else:
                LOG.info("update_user no changes, skip user region={} "
                         "update uuid={} passwd_hash={}".format(
                             self.region_name, iuser.uuid, passwd_hash))
        except Exception as e:
            LOG.error("update_user exception={}".format(e))
            raise exceptions.SyncRequestFailedRetry()

        return iuser
