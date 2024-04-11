# Copyright (c) 2021 OnePro Cloud Ltd.
#
#   prophet is licensed under Mulan PubL v2.
#   You can use this software according to the terms and conditions of the Mulan PubL v2.
#   You may obtain a copy of Mulan PubL v2 at:
#
#            http://license.coscl.org.cn/MulanPubL-2.0
#
#   THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
#   EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
#   MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
#   See the Mulan PubL v2 for more details.

"""Collect resources using Huawei SDK

 Steps:

     1. AK/SK authentication
     2. Collect unit price information
     3. Save results to json file

"""

import copy
import json
import time
import re
import os
import logging
import threading
import concurrent.futures

from prophet.cloud_price.base import BaseCloudCollector

from huaweicloudsdkcore.auth.credentials import (GlobalCredentials,
                                                 BasicCredentials)
from huaweicloudsdkcore.region.region import Region
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkbssintl.v2.region.bssintl_region import BssintlRegion
from huaweicloudsdkbss.v2.region.bss_region import BssRegion
from huaweicloudsdkbssintl.v2 import (DemandProductInfo, BssintlClient,
                                      ListOnDemandResourceRatingsRequest,
                                      RateOnDemandReq,
                                      ListRateOnPeriodDetailRequest,
                                      RateOnPeriodReq, PeriodProductInfo)
from huaweicloudsdkiam.v3.region.iam_region import IamRegion
from huaweicloudsdkiam.v3 import (IamClient, KeystoneListRegionsRequest,
                                  KeystoneListAuthProjectsRequest)
from huaweicloudsdkecs.v2.region.ecs_region import EcsRegion
from huaweicloudsdkecs.v2 import (EcsClient, NovaListAvailabilityZonesRequest,
                                  ListFlavorsRequest)
from huaweicloudsdkevs.v2.region.evs_region import EvsRegion
from huaweicloudsdkevs.v2 import EvsClient, CinderListVolumeTypesRequest

HUAWEI_INTL_RESOURCES = os.path.dirname(os.path.abspath(__file__)) + \
                         '/huawei_intl_resources.json'


def get_huawei_intl_resources():
    with open(HUAWEI_INTL_RESOURCES, 'r') as f:
        return json.loads(f.read())


class HuaweiCollector(BaseCloudCollector):
    def __init__(self, *args, **kwargs):
        super(HuaweiCollector, self).__init__(*args, **kwargs)
        self.huawei_resources = get_huawei_intl_resources()
        self.lock = threading.Lock()

    def collect(self):
        logging.info("Precheck for %s  authentication information, "
                     "ak: %s , sk: %s" % (self.cloud, self.ak, self.sk))
        self._precheck()

        logging.info("Collecting %s cloud prices info..." % self.cloud)
        price_info = self._collect_data()
        logging.debug("Collect %s cloud price returns: %s" % (self.cloud,
                                                              price_info))
        logging.info("Collected %s cloud info" % self.cloud)

        save_values = {
            "cloud": self.cloud,
            "regions": price_info.get("regions"),
            "prices": price_info.get("prices")
        }
        self.save(self.base_path, save_values)

        return [price_info]

    def _precheck(self):
        logging.info("Checking %s cloud authentication information..." %
                     self.cloud)
        try:
            self.get_regions(self.ak, self.sk)
        except exceptions.ClientRequestException as e:
            logging.exception(e)
            logging.error("%s platform authentication with AK/SK failed, "
                          "please check it." % self.cloud)
            raise e

    def _collect_data(self):
        logging.info("Collect cloud price resource unit price...")

        ret = {
            "regions": {
                "en": [],
                "zh": []
            },
            "prices": {}
        }
        projects = self.get_projects(self.ak, self.sk)
        regions = self.get_regions(self.ak, self.sk)

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for region in regions:
                ret["regions"]["en"].append({
                    "id": region["id"],
                    "name": region["locales"]["en-us"]
                })
                ret["regions"]["zh"].append({
                    "id": region["id"],
                    "name": region["locales"]["zh-cn"]
                })
                futures.append(executor.submit(
                    self._get_resource_price_task,
                    region, projects[region["id"]]))
            for future in concurrent.futures.as_completed(futures):
                ret["prices"].update(future.result())
        return ret

    def _get_resource_price_task(self, region, project_id):
        info = {
            "en": {
                "id": region["id"],
                "name": region["locales"]["en-us"]
            },
            "zh": {
                "id": region["id"],
                "name": region["locales"]["zh-cn"]
            }
        }

        # Collect on-demand pricing for instance specifications (hourly rates)
        en_flavor_univalence, zh_flavor_univalence = \
            self.flavors_price_processing(self.ak, self.sk, region, project_id)
        info["en"]["flavors"] = en_flavor_univalence
        info["zh"]["flavors"] = zh_flavor_univalence

        # Collect unit price of cloud storage (based on a 10GB/hour rate)
        en_disk_univalence, zh_disk_univalence = \
            self.disks_price_processing(self.ak, self.sk, region, project_id)
        info["en"]["disk_types"] = en_disk_univalence
        info["zh"]["disk_types"] = zh_disk_univalence

        # Collect unit price of object storage
        en_obs_univalence, zh_obs_univalence = \
            self.obs_price_processing(self.ak, self.sk, region, project_id)
        info["en"]["obs"] = en_obs_univalence
        info["zh"]["obs"] = zh_obs_univalence

        # Collect on-demand pricing for Elastic IP based on traffic volume
        # (based on a 1GB rate)
        en_eip_univalence, zh_eip_univalence = \
            self.eips_price_processing(self.ak, self.sk, region, project_id)
        info["en"]["eip"] = en_eip_univalence
        info["zh"]["eip"] = zh_eip_univalence

        return {region["id"]: info}

    def _zone_name_local(self, zone, language):
        name_local = '可用区' if language and 'zh' in language else 'AZ'
        name_local += str(
            ord(str(zone["zoneName"]).lower()[-1]) - ord('a') + 1)
        return name_local

    def _is_res_in_blacklist(self, blacklist, res_key, val):
        if blacklist and blacklist.get(res_key):
            for sign in blacklist[res_key]:
                if val.startswith(sign) or val.endswith(sign):
                    return True
        return False

    def _to_specify_region(self, server, region_id, version=''):
        endpoint = self._to_endpoint(server, region_id)
        region_class = '%sRegion' % server.replace("-", "").capitalize()
        if version:
            region_class = '%s%s' % (region_class, version.capitalize())
        region_srv = eval(region_class).value_of(
            region_id,
            static_fields={region_id: Region(id=region_id, endpoint=endpoint)})
        return region_srv

    def _to_endpoint(self, server, region_id):
        if server in ["bss-intl", "bss"]:
            endpoint = 'https://{}.myhuaweicloud.com' \
                       ''.format(server)
        else:
            endpoint = 'https://{}.{}.myhuaweicloud.com' \
                       ''.format(server, region_id)
        return self._endpoint_for_region(endpoint, region_id)

    def _endpoint_for_region(self, url, region_id):
        """Transitioning from global to regional endpoint.
        """
        if not region_id:
            return url
        if region_id not in url:
            pat = re.compile(r'^(https?://)?(\w{2,})(\.myhuaweicloud\.\w+)')
            g_domain = pat.match(url)
            if g_domain:
                region_uri = '{}.{}'.format(g_domain[2], region_id)
                url = url.replace(g_domain[2], region_uri)
        if region_id.startswith('eu-'):
            url = url.replace('myhuaweicloud.com', 'myhuaweicloud.eu')
        return url

    def get_regions(self, ak, sk):

        logging.info("Start get regions...")

        ret = []
        global_credentials = GlobalCredentials(ak, sk)

        client = IamClient.new_builder() \
            .with_credentials(global_credentials) \
            .with_region(self._to_specify_region(
                "iam", self.huawei_resources["DEFAULT_REGION_ID"])) \
            .build()

        request = KeystoneListRegionsRequest()
        response = \
            client.keystone_list_regions(request).to_json_object()["regions"]
        for region in response:
            if self._is_res_in_blacklist(
                    self.huawei_resources["BLACKLIST"],
                    "regions", region["id"]):
                continue
            ret.append({
                "id": region.get("id"),
                "locales": region.get("locales"),
            })
        logging.info("Success get regions, regions: %s" % ret)
        return ret

    def get_projects(self, ak, sk):
        logging.info("Start get projects...")

        ret = {}
        global_credentials = GlobalCredentials(ak, sk)
        client = IamClient.new_builder() \
            .with_credentials(global_credentials) \
            .with_region(self._to_specify_region(
                "iam", self.huawei_resources["DEFAULT_REGION_ID"])) \
            .build()

        request = KeystoneListAuthProjectsRequest()
        response = client.keystone_list_auth_projects(
            request).to_json_object()["projects"]
        for project in response:
            ret[project["name"]] = project["id"]
        logging.info("Success get projects, projects: %s" % ret)
        return ret

    def get_zones(self, ak, sk, region):
        logging.info("Start get zones..., region: %s" % region)
        ret = []
        credentials = BasicCredentials(ak, sk)
        client = EcsClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(self._to_specify_region("ecs", region["id"])) \
            .build()

        request = NovaListAvailabilityZonesRequest()
        response = client.nova_list_availability_zones(
            request).to_json_object()["availabilityZoneInfo"]
        for zone in response:
            if zone["zoneState"].get("available"):
                ret.append(zone)
        logging.info("Success get zones..., zones: %s" % ret)
        return ret

    def _get_price(self, client, project_id, product, product_type):
        try:
            if product_type == "OnDemand":
                request = ListOnDemandResourceRatingsRequest()
                request.body = RateOnDemandReq(
                    product_infos=[product],
                    inquiry_precision=1,
                    project_id=project_id
                )

                response = client.list_on_demand_resource_ratings(
                    request).to_json_object()["product_rating_results"]
            else:
                request = ListRateOnPeriodDetailRequest()
                request.body = RateOnPeriodReq(
                    product_infos=[product],
                    project_id=project_id
                )

                response = client.list_rate_on_period_detail(
                    request).to_json_object()[
                    "official_website_rating_result"][
                    "product_rating_results"]
            return response
        except exceptions.ClientRequestException as e:
            logging.warning(e.error_msg)
            return []

    def _get_product_rate(self, ak, sk, project_id, body,
                          product_type="OnDemand"):
        rate_list = []
        if not body:
            return rate_list
        credentials = GlobalCredentials(ak, sk)
        client = BssintlClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(self._to_specify_region(
                "bss-intl", self.huawei_resources["DEFAULT_REGION_ID"])) \
            .build()
        # Cloud platforms limit requests to 10 times per second
        with self.lock:
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=10) as executor:
                prices = []
                for index, product in enumerate(body):
                    # Waiting for request execution to complete
                    if len(prices) == 10:
                        rate_list += prices[0].result()
                        prices.pop(0)
                    prices.append(executor.submit(
                            self._get_price, client, project_id, product,
                            product_type))
                    time.sleep(0.15)
                for price in concurrent.futures.as_completed(prices):
                    rate_list += price.result()

        return rate_list

    def flavors_price_processing(self, ak, sk, region, project_id):
        logging.info("Start get flavors rating results..., "
                     "region: %s, project_id: %s" % (region, project_id))

        credentials = BasicCredentials(ak, sk)
        client = EcsClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(self._to_specify_region("ecs", region["id"])) \
            .build()

        request = ListFlavorsRequest()
        response = client.list_flavors(request).to_json_object()["flavors"]
        response.sort(key=lambda x: (int(x["vcpus"]), x["ram"]))
        flavors = []
        for flavor in response:
            if self._is_res_in_blacklist(
                    self.huawei_resources["BLACKLIST"],
                    "flavors", flavor["id"]):
                continue
            flavors.append(flavor)

        logging.info("Success get flavors list...")

        flavors_dict = {}
        on_demand_product_infos = []
        on_period_product_infos = []

        for flavor in flavors:
            if (flavor["os_extra_specs"].get("cond:operation:az") and
                "normal" in flavor["os_extra_specs"]["cond:operation:az"]) or \
                    (flavor["os_extra_specs"].get("cond:operation:status") and
                     flavor["os_extra_specs"]["cond:operation:status"] in
                     ["normal", "promotion"]):
                if flavor.get("ram") and flavor["ram"] < 1024:
                    continue
                min_rate = int(
                    flavor["os_extra_specs"].get("quota:min_rate", 0))
                max_rate = int(
                    flavor["os_extra_specs"].get("quota:max_rate", 0))
                if max_rate == -1:
                    max_rate = min_rate

                flavors_dict[flavor["id"]] = {
                    "id": flavor.get("id"),
                    "name": flavor.get("name"),
                    "vcpus": int(flavor.get("vcpus")),
                    "ram": int(flavor.get("ram") / 1024),
                    'cpu_name': flavor["os_extra_specs"].get("info:cpu:name"),
                    "max_rate": max_rate,
                    "min_rate": min_rate,
                    "max_pps": int(flavor["os_extra_specs"].get(
                        "quota:max_pps", 0)),
                    "product_rating_result": {}
                }
                on_demand_product_infos.append(
                    DemandProductInfo(
                        id=flavor["id"],
                        cloud_service_type=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_SERVICE_TYPE_CODE"],
                        resource_type=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_RESOURCE_TYPE_CODE"],
                        resource_spec="%s.linux" % flavor["id"],
                        region=region["id"],
                        usage_factor=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_USAGE_FACTOR"],
                        usage_value=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_USAGE_VALUE"],
                        usage_measure_id=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_USAGE_MEASURE_ID"],
                        subscription_num=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_SUBSCRIPTION_NUM"]
                    )
                )
                on_period_product_infos.append(
                    PeriodProductInfo(
                        id=flavor["id"],
                        cloud_service_type=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_SERVICE_TYPE_CODE"],
                        resource_type=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_RESOURCE_TYPE_CODE"],
                        resource_spec="%s.linux" % flavor["id"],
                        region=region["id"],
                        period_type=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_PERIOD_TYPE"],
                        period_num=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_PERIOD_NUM"],
                        subscription_num=self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_SUBSCRIPTION_NUM"]
                    )
                )
        on_demand_price_list = \
            self._get_product_rate(ak, sk, project_id, on_demand_product_infos,
                                   product_type="OnDemand")
        for price in on_demand_price_list:
            flavors_dict[price["id"]]["product_rating_result"].update({
                "on_demand": {
                    "id": price.get("id"),
                    "usage_value": self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_USAGE_VALUE"],
                    "usage_unit": self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_USAGE_UNIT"],
                    self.huawei_resources["CURRENCY_UNIT"]: price.get("amount")
                }
            })

        on_period_price_list = \
            self._get_product_rate(ak, sk, project_id, on_period_product_infos,
                                   product_type="OnPeriod")
        for price in on_period_price_list:
            flavors_dict[price["id"]]["product_rating_result"].update({
                "on_period": {
                    "id": price.get("id"),
                    "usage_value": self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_PERIOD_NUM"],
                    "usage_unit": self.huawei_resources[
                            "ECS_PRODUCT"]["ECS_PERIOD_MONTH_UNIT"],
                    self.huawei_resources["CURRENCY_UNIT"]: price.get(
                            "official_website_amount")
                }
            })

        logging.info("Success get flavors rating results..., "
                     "results: %s" % flavors_dict)

        en_ret = []
        zh_ret = []

        for flavor_type in \
                self.huawei_resources["FLAVOR_PERFORMANCE_TYPE"]:
            for key in flavors_dict:
                if flavors_dict[key]["product_rating_result"].get(
                        "on_demand") and \
                        flavors_dict[key]["product_rating_result"].get(
                            "on_period"):
                    if self._is_res_in_blacklist(flavor_type, "flavors", key):
                        en_flavor = copy.deepcopy(flavors_dict[key])
                        zh_flavor = copy.deepcopy(flavors_dict[key])
                        en_flavor["type"] = flavor_type["locales"]["en_US"]
                        zh_flavor["type"] = flavor_type["locales"]["zh_CN"]
                        en_ret.append(en_flavor)
                        zh_ret.append(zh_flavor)

        return en_ret, zh_ret

    def disks_price_processing(self, ak, sk, region, project_id):

        logging.info("Start get disks rating results..., "
                     "region: %s" % region)

        credentials = BasicCredentials(ak, sk)
        client = EvsClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(self._to_specify_region("evs", region["id"])) \
            .build()

        request = CinderListVolumeTypesRequest()
        response = client.cinder_list_volume_types(
            request).to_json_object()["volume_types"]

        logging.info("Success get disk types..., "
                     "disk_types: %s" % response)

        disk_types = []
        on_demand_product_infos = []
        on_period_product_infos = []
        for disk_type in response:
            # Filter out of stock types
            if disk_type["extra_specs"].get("RESKEY:availability_zones") == \
                    disk_type["extra_specs"].get(
                        "os-vendor-extended:sold_out_availability_zones"):
                continue
            if disk_type["name"] not in \
                    self.huawei_resources["DISK_TYPES"]:
                continue
            disk_types.append({
                "id": disk_type.get("id"),
                "name": disk_type.get("name"),
                "disk_type": disk_type.get("name"),
                "product_rating_result": {}
            })
            on_demand_product_infos.append(
                DemandProductInfo(
                    id=disk_type["name"],
                    cloud_service_type=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_SERVICE_TYPE_CODE"],
                    resource_type=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_RESOURCE_TYPE_CODE"],
                    resource_spec=self.huawei_resources["DISK_TYPES"][
                        disk_type["name"]]["resource_spec"],
                    region=region["id"],
                    resource_size=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_RESOURCE_SIZE"],
                    size_measure_id=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_SIZE_MEASURE_ID"],
                    usage_factor=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_USAGE_FACTOR"],
                    usage_value=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_USAGE_VALUE"],
                    usage_measure_id=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_USAGE_MEASURE_ID"],
                    subscription_num=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_SUBSCRIPTION_NUM"]
                )
            )
            on_period_product_infos.append(
                PeriodProductInfo(
                    id=disk_type["name"],
                    cloud_service_type=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_SERVICE_TYPE_CODE"],
                    resource_type=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_RESOURCE_TYPE_CODE"],
                    resource_spec=self.huawei_resources["DISK_TYPES"][
                        disk_type["name"]]["resource_spec"],
                    region=region["id"],
                    resource_size=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_RESOURCE_SIZE"],
                    size_measure_id=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_SIZE_MEASURE_ID"],
                    period_type=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_PERIOD_TYPE"],
                    period_num=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_PERIOD_NUM"],
                    subscription_num=self.huawei_resources[
                        "EBS_PRODUCT"]["EBS_SUBSCRIPTION_NUM"]
                )
            )

        on_demand_price_list = \
            self._get_product_rate(ak, sk, project_id,
                                   on_demand_product_infos,
                                   product_type="OnDemand")
        for price in on_demand_price_list:
            for disk_type in disk_types:
                if disk_type["name"] == price["id"]:
                    on_demand = {
                        "on_demand": {
                            "id": price.get("id"),
                            "resource_size": self.huawei_resources[
                                "EBS_PRODUCT"]["EBS_RESOURCE_SIZE"],
                            "resource_unit": self.huawei_resources[
                                "EBS_PRODUCT"]["EBS_RESOURCE_UNIT"],
                            self.huawei_resources["CURRENCY_UNIT"]: price.get(
                                "amount")
                        }
                    }
                    disk_type["product_rating_result"].update(on_demand)

        on_period_price_list = \
            self._get_product_rate(ak, sk, project_id,
                                   on_period_product_infos,
                                   product_type="OnPeriod")
        for price in on_period_price_list:
            for disk_type in disk_types:
                if disk_type["name"] == price["id"]:
                    on_period = {
                        "on_period": {
                            "id": price.get("id"),
                            "resource_size": self.huawei_resources[
                                "EBS_PRODUCT"]["EBS_RESOURCE_SIZE"],
                            "resource_unit": self.huawei_resources[
                                "EBS_PRODUCT"]["EBS_RESOURCE_UNIT"],
                            "usage_value": self.huawei_resources[
                                "EBS_PRODUCT"]["EBS_PERIOD_NUM"],
                            "usage_unit": self.huawei_resources[
                                "EBS_PRODUCT"]["EBS_PERIOD_MONTH_UNIT"],
                            self.huawei_resources["CURRENCY_UNIT"]: price.get(
                                "official_website_amount")
                        }
                    }
                    disk_type["product_rating_result"].update(on_period)

        logging.info("Success get disks rating results..., "
                     "results: %s" % disk_types)

        zh_ret = []
        en_ret = []
        for name in self.huawei_resources["DISK_TYPES"]:
            for disk_type in disk_types:
                if disk_type["name"] == name:
                    zh_disk_type = copy.deepcopy(disk_type)
                    zh_disk_type["display_name"] = \
                        self.huawei_resources["DISK_TYPES"][name][
                            "locales"]["zh_CN"]
                    zh_ret.append(zh_disk_type)
                    en_disk_type = copy.deepcopy(disk_type)
                    en_disk_type["display_name"] = \
                        self.huawei_resources["DISK_TYPES"][name][
                            "locales"]["en_US"]
                    en_ret.append(en_disk_type)

        return en_ret, zh_ret

    def obs_price_processing(self, ak, sk, region, project_id):
        logging.info("Start get obs rating results..., "
                     "region: %s, project_id: %s" % (region, project_id))
        obs = {
            "storage": {
                "3az": {},
                "az": {}
            },
            "public_flow": {},
            "return_flow": {}
        }

        # Collecting the unit price of multi-AZ object storage
        listProductInfosbody = [
            DemandProductInfo(
                id="1",
                cloud_service_type=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_SERVICE_TYPE_CODE"],
                resource_type=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_RESOURCE_TYPE_CODE"],
                resource_spec=self.huawei_resources["OBS_PRODUCT"][
                                "OBS_STORAGE_3AZ_RESOURCE_SPEC"],
                region=region["id"],
                usage_factor=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_STORAGE_3AZ_USAGE_FACTOR"],
                usage_value=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_VALUE"],
                usage_measure_id=self.huawei_resources["OBS_PRODUCT"][
                                "OBS_STORAGE_3AZ_USAGE_MEASURE_ID"],
                subscription_num=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_SUBSCRIPTION_NUM"]
            )
        ]
        price_list = self._get_product_rate(ak, sk, project_id,
                                            listProductInfosbody)
        if price_list:
            obs["storage"]["3az"]["product_rating_result"] = {
                "id": price_list[0].get("id"),
                "usage_value": self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_VALUE"],
                "usage_unit": self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_UNIT"],
                self.huawei_resources["CURRENCY_UNIT"]: price_list[0].get(
                                "amount")
            }

        # Collecting the unit price of single-AZ object storage
        listProductInfosbody = [
            DemandProductInfo(
                id="2",
                cloud_service_type=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_SERVICE_TYPE_CODE"],
                resource_type=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_RESOURCE_TYPE_CODE"],
                resource_spec=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_STORAGE_AZ_RESOURCE_SPEC"],
                region=region["id"],
                usage_factor=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_STORAGE_AZ_USAGE_FACTOR"],
                usage_value=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_VALUE"],
                usage_measure_id=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_STORAGE_USAGE_MEASURE_ID"],
                subscription_num=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_SUBSCRIPTION_NUM"]
            )
        ]
        price_list = self._get_product_rate(ak, sk, project_id,
                                            listProductInfosbody)
        if price_list:
            obs["storage"]["az"]["product_rating_result"] = {
                "id": price_list[0].get("id"),
                "usage_value": self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_VALUE"],
                "usage_unit": self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_UNIT"],
                self.huawei_resources["CURRENCY_UNIT"]: price_list[0].get(
                                "amount")
            }

        # Collecting the unit price for public outbound
        # traffic of object storage
        listProductInfosbody = [
            DemandProductInfo(
                id="3",
                cloud_service_type=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_SERVICE_TYPE_CODE"],
                resource_type=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_RESOURCE_TYPE_CODE"],
                resource_spec=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_STORAGE_AZ_RESOURCE_SPEC"],
                region=region["id"],
                usage_factor=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_PUBLIC_USAGE_FACTOR"],
                usage_value=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_VALUE"],
                usage_measure_id=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_MEASURE_ID"],
                subscription_num=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_SUBSCRIPTION_NUM"]
            )
        ]
        price_list = self._get_product_rate(ak, sk, project_id,
                                            listProductInfosbody)
        if price_list:
            obs["public_flow"]["product_rating_result"] = {
                "id": price_list[0].get("id"),
                "usage_value": self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_VALUE"],
                "usage_unit": self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_UNIT"],
                self.huawei_resources["CURRENCY_UNIT"]: price_list[0].get(
                                "amount")
            }

        # Collecting the unit price for origin retrieval
        # traffic of object storage
        listProductInfosbody = [
            DemandProductInfo(
                id="4",
                cloud_service_type=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_SERVICE_TYPE_CODE"],
                resource_type=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_RESOURCE_TYPE_CODE"],
                resource_spec=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_STORAGE_AZ_RESOURCE_SPEC"],
                region=region["id"],
                usage_factor=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_RETURN_USAGE_FACTOR"],
                usage_value=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_VALUE"],
                usage_measure_id=self.huawei_resources["OBS_PRODUCT"][
                                "OBS_STORAGE_3AZ_USAGE_MEASURE_ID"],
                subscription_num=self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_SUBSCRIPTION_NUM"]
            )
        ]
        price_list = self._get_product_rate(ak, sk, project_id,
                                            listProductInfosbody)
        if price_list:
            obs["return_flow"]["product_rating_result"] = {
                "id": price_list[0].get("id"),
                "usage_value": self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_VALUE"],
                "usage_unit": self.huawei_resources[
                                "OBS_PRODUCT"]["OBS_USAGE_UNIT"],
                self.huawei_resources["CURRENCY_UNIT"]: price_list[0].get(
                                "amount")
            }

        logging.info("Success get obs rating results..., "
                     "obs: %s" % obs)
        en_ret = obs
        zh_ret = obs

        return en_ret, zh_ret

    def eips_price_processing(self, ak, sk, region, project_id):

        logging.info("Start get eip rating results..., "
                     "region: %s" % region)
        en_ret = {}
        zh_ret = {}
        eip = {
            "product_rating_result": {}
        }

        # On demand billing based on data usage
        on_demand_product_infos = [
            DemandProductInfo(
                id="EIP",
                cloud_service_type=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_SERVICE_TYPE_CODE"],
                resource_type=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_RESOURCE_TYPE_CODE"],
                resource_spec=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_RESOURCE_SPEC"],
                region=region["id"],
                resource_size=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_RESOURCE_SIZE"],
                size_measure_id=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_SIZE_MEASURE_ID"],
                usage_factor=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_USAGE_FACTOR"],
                usage_value=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_USAGE_VALUE"],
                usage_measure_id=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_USAGE_MEASURE_ID"],
                subscription_num=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_SUBSCRIPTION_NUM"]
            )
        ]
        on_demand_price_list = \
            self._get_product_rate(ak, sk, project_id,
                                   on_demand_product_infos,
                                   product_type="OnDemand")
        if on_demand_price_list:
            on_demand = {
                "on_demand": {
                    "id": on_demand_price_list[0].get("id"),
                    "usage_value": self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_USAGE_VALUE"],
                    "usage_unit": self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_USAGE_UNIT"],
                    self.huawei_resources["CURRENCY_UNIT"]:
                        on_demand_price_list[0].get("amount")
                }
            }
            eip["product_rating_result"].update(on_demand)

        # On period and bandwidth
        on_period_product_infos = [
            PeriodProductInfo(
                id="EIP",
                cloud_service_type=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_SERVICE_TYPE_CODE"],
                resource_type=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_RESOURCE_TYPE_CODE"],
                resource_spec=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_PERIOD_RESOURCE_SPEC"],
                region=region["id"],
                resource_size=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_RESOURCE_SIZE"],
                size_measure_id=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_SIZE_MEASURE_ID"],
                period_type=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_PERIOD_TYPE"],
                period_num=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_PERIOD_NUM"],
                subscription_num=self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_SUBSCRIPTION_NUM"]
            )
        ]
        on_period_price_list = \
            self._get_product_rate(ak, sk, project_id,
                                   on_period_product_infos,
                                   product_type="OnPeriod")
        if on_period_price_list:
            on_period = {
                "on_period": {
                    "id": on_period_price_list[0].get("id"),
                    "usage_value": self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_PERIOD_NUM"],
                    "usage_unit": self.huawei_resources[
                                "EIP_PRODUCT"]["EIP_PERIOD_MONTH_UNIT"],
                    self.huawei_resources["CURRENCY_UNIT"]:
                        on_period_price_list[0].get("official_website_amount")
                }
            }
            eip["product_rating_result"].update(on_period)

        logging.info("Success get eip rating results..., "
                     "eip: %s" % eip)
        en_ret.update(eip)
        zh_ret.update(eip)

        return en_ret, zh_ret
