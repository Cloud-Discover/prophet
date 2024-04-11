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

"""Base collector class for different resources collection

Inherit this class and implement collect method in sub class.

"""

import json
import logging
import os

REGION_PRICES = "regions"

REGION_NAME = "region"


class BaseCloudCollector(object):
    """Base class for cloud collector

    This may extends more base class for different resources in future.

    """

    def __init__(self, cloud, ak, sk, output_path, *args, **kwargs):
        self.cloud = cloud
        self.ak = ak
        self.sk = sk
        self.output_path = output_path

    @property
    def base_path(self):
        """Base path to save collection results, by os type"""
        os_path = os.path.join(self.output_path, self.cloud)

        if not os.path.exists(os_path):
            logging.info("Create os path %s" % os_path)
            os.makedirs(os_path)

        return os_path

    def collect(self):
        """Implement in each sub class, main method to collect"""
        raise NotImplementedError

    def collection_file(self, save_path, name):
        filename = "%s.json" % name
        return os.path.join(save_path, filename)

    def save_to_json(self, save_path, values):
        """Save collection prices to json file"""
        logging.info("Saving prices to json %s..." % save_path)

        json_datas = json.dumps(values, ensure_ascii=False)

        with open(save_path, "w") as jsonfile:
            logging.debug("Save values %s: " % json_datas)
            jsonfile.write(json_datas)

        logging.info("Saved prices to json %s" % save_path)

    def save(self, save_path, values):
        """Save collection prices to file"""
        logging.info("Saving prices to json %s..." % save_path)
        regions_path = os.path.join(save_path, REGION_PRICES)
        os.makedirs(regions_path)
        if values.get("regions"):
            self.save_to_json(self.collection_file(save_path, REGION_NAME),
                              values["regions"])

        if values.get("prices"):
            for region_id in values["prices"]:
                self.save_to_json(
                    self.collection_file(regions_path, region_id),
                    values["prices"][region_id])

        logging.info("Saved prices to json %s" % save_path)
