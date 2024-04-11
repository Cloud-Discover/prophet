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

"""Batch job for running mix host type collection"""

import glob
import logging
import os
import shutil
import time

import numpy as np
import pandas as pd
from stevedore import driver

# Driver namespace
PRICE_COLLECTOR_NAMESPACE = "price_collector"

# Region Resource Collection
PRICE_REGIONS_RESOURCE = "regions"


class PriceCollector(object):

    def __init__(self, cloud, ak, sk, output_path, *args, **kwargs):
        self.cloud = cloud
        self.ak = ak
        self.sk = sk
        self.output_path = output_path

        # Generate compressed pacakge name
        self._zip_package_name = None

    @property
    def collection_path(self):
        """Base path to save all files"""
        return os.path.join(self.output_path, self.cloud)

    @property
    def collection_report_path(self):
        """Path to save collection result"""
        return os.path.join(self.collection_path, PRICE_REGIONS_RESOURCE)

    @property
    def zip_package_name(self):
        """Compressed pacakge path for final collections"""
        if not self._zip_package_name:
            timestamp = time.strftime(
                    "%Y%m%d%H%M%S", time.localtime(time.time()))
            self._zip_package_name = "%s_%s" % (
                    self.cloud, timestamp)

        return self._zip_package_name

    def collect_prices(self):
        """Collect Cloud resource unit price"""

        # Validation and prepare
        self._prepare()

        logging.info("Collecting %s resource unit price, "
                     "ak: %s, sk: %s" % (self.cloud, self.ak, self.sk))

        try:
            # Run collect method from each driver
            driver_manager = driver.DriverManager(
                    namespace=PRICE_COLLECTOR_NAMESPACE,
                    name=self.cloud.upper(),
                    invoke_on_load=False)

            c = driver_manager.driver(
                    cloud=self.cloud,
                    ak=self.ak,
                    sk=self.sk,
                    output_path=self.collection_path)
            c.collect()

            logging.info("Collect %s prices success" % self.cloud)
        except Exception as e:
            logging.error("Cloud %s collect prices failed !" % self.cloud)
            logging.exception(e)

    def package(self):
        """Create compressed pacakge for prices collection"""
        logging.info("Copying log file into collection info path...")

        log_files = "%s/*.log" % self.output_path

        for f in glob.glob(log_files):
            logging.info("Copying %s to %s..." % (
                f, self.collection_path))
            shutil.copy(f, self.collection_path)

        logging.info("Compressed pacakge in %s, "
                     "filename is %s.zip..." % (
                         self.output_path, self.zip_package_name))
        os.chdir(self.output_path)
        shutil.make_archive(self.zip_package_name, "zip",
                            self.collection_path)

    def _prepare(self):

        # Create output path if not exists
        if not os.path.exists(self.output_path):
            logging.info("Creating output path %s...")
            os.makedirs(self.output_path)
            logging.info("Created output path %s success")

        # Clean host collection base path if force check, otherwise
        # elder collection path will be kept
        if os.path.exists(self.collection_path):
            logging.info("Deleting existing prices "
                         "collection path %s..." % self.collection_path)
            shutil.rmtree(self.collection_path)
            logging.info("Delete existing prices collection "
                         "path %s Succesfully" % self.collection_path)

        if not os.path.exists(self.collection_path):
            logging.info("Creating collection path %s..." %
                         self.collection_path)
            os.makedirs(self.collection_path)
