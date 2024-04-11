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

from prophet.cloud_price.cloud.huawei_intl import *
from huaweicloudsdkbss.v2 import BssClient


HUAWEI_CN_RESOURCES = os.path.dirname(os.path.abspath(__file__)) + \
                         '/huawei_cn_resources.json'


def get_huawei_cn_resources():
    with open(HUAWEI_CN_RESOURCES, 'r') as f:
        return json.loads(f.read())


class HuaweiCnCollector(HuaweiCollector):

    def __init__(self, *args, **kwargs):
        super(HuaweiCnCollector, self).__init__(*args, **kwargs)
        self.huawei_resources = get_huawei_cn_resources()

    def _get_product_rate(self, ak, sk, project_id, body,
                          product_type="OnDemand"):
        rate_list = []
        if not body:
            return rate_list
        credentials = GlobalCredentials(ak, sk)
        client = BssClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(self._to_specify_region(
                "bss", self.huawei_resources["DEFAULT_REGION_ID"])) \
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
