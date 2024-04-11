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

"""Starter script for prophet-cli"""

import argparse
import logging
import os
import sys

from prophet.cloud_price.collector import PriceCollector
from prophet.scanner.network import NetworkController
from prophet.collector.collector import HostCollector
from prophet.report.host_report import HostReporter
from prophet.utils import init_logging

VER = "v0.1.0"

# Default log name
LOG_FILE = "prophet.log"

# Default scan report name
SCAN_REPORT_NAME = "scan_results.csv"

# Default package name
HOST_PACKAGE_NAME = "hosts_collection"

# Default report name
REPORT_NAME = "analysis_report.csv"


def scan_network(args):
    host = args.host
    output_path = args.output_path
    arg = args.arg
    if not os.path.exists(output_path):
        logging.info("Cannot found %s directory in system, "
                     "create it." % output_path)
        os.makedirs(output_path)
    network = NetworkController(host, arg, output_path)
    network.generate_report()


def collect_hosts(args):
    host_file = args.host_file
    output_path = args.output_path
    force_check = args.force_check
    package_name = args.package_name

    host_collector = HostCollector(host_file, output_path,
                                   force_check, package_name)
    host_collector.collect_hosts()
    host_collector.package()


def analysis_report(args):
    host_report = HostReporter(args.package_file,
                               args.output_path,
                               args.clean,
                               args.report_name)
    host_report.analysis()


def collect_prices(args):
    cloud = args.cloud
    ak = args.ak
    sk = args.sk
    output_path = args.output_path

    price_collector = PriceCollector(cloud, ak, sk, output_path)
    price_collector.collect_prices()
    price_collector.package()


def parse_sys_args(argv):
    """Parses commaond-line arguments"""
    parser = argparse.ArgumentParser(
        description="Resource collect and report tool prophet")
    parser.add_argument("-d", "--debug", action="store_true",
            dest="debug", default=False,
            help="Enable debug message.")
    parser.add_argument("-v", "--verbose", action="store_true",
            dest="verbose", default=True,
            help="Show message in standard output.")

    subparsers = parser.add_subparsers(title='Avaliable commands')

    # Network Scan Arguments
    parser_scan_network = subparsers.add_parser("scan")
    parser_scan_network.add_argument("--host", dest="host", required=True,
            help="Input host, example: 192.168.10.0/24, 192.168.10.1-2")
    parser_scan_network.add_argument("--arg", dest="arg",
            required=False, default="-O -sS",
            help="Arguments for nmap, for more detailed, "
                            "please check nmap document")
    parser_scan_network.add_argument("--output-path", dest="output_path",
            required=True, help="Generate initial host report path")
    parser_scan_network.add_argument("--report-name", dest="report_name",
            required=False, default=SCAN_REPORT_NAME,
            help="Scan report csv name, "
                 "Default name is %s" % SCAN_REPORT_NAME)
    parser_scan_network.set_defaults(func=scan_network)

    # Collect Arguments
    parser_collect = subparsers.add_parser("collect")
    parser_collect.add_argument("--host-file", dest="host_file",
            required=True, help="Host file which generated "
                                "by network scan")
    parser_collect.add_argument("--output-path", dest="output_path",
            required=True, help="Output path for batch collection")
    parser_collect.add_argument("-f", "--force-check",
            action="store_true", dest="force_check", default=False,
            help="Force check all hosts")
    parser_collect.add_argument("--package-name", dest="package_name",
            required=False, default=HOST_PACKAGE_NAME,
            help="Prefix name for host collection package, "
                 "Default name is %s" % HOST_PACKAGE_NAME)
    parser_collect.set_defaults(func=collect_hosts)

    # Analysis Arguments
    parser_report = subparsers.add_parser("report")
    parser_report.add_argument("--package-file",
            dest="package_file", required=True,
            help="Investigate package file which is "
                 "genreated by prophet-collect")
    parser_report.add_argument("--output-path", dest="output_path",
            required=True, help="Generate report path")
    parser_report.add_argument("--report-name", dest="report_name",
            required=False, default=REPORT_NAME, help="Generate report name")
    parser_report.add_argument("--clean", action="store_true",
            dest="clean", required=False, default=False,
            help="Clean temp work dir or not, by default is not")

    parser_report.set_defaults(func=analysis_report)

    # Collecting Unit Prices Of Cloud Platform Resources
    parser_price = subparsers.add_parser("price")
    parser_price.add_argument("--cloud",
            dest="cloud", required=True,
            help="Cloud platform acronyms")
    parser_price.add_argument("--ak",
            dest="ak", required=True,
            help="Cloud authentication access key id")
    parser_price.add_argument("--sk", dest="sk",
            required=True, help="Cloud authentication access key id")
    parser_price.add_argument("--output-path", dest="output_path",
            required=True, help="Generate report path")

    parser_price.set_defaults(func=collect_prices)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    else:
        return parser.parse_args(argv[1:])

def main():
    # NOTE(Ray): If there are speicial chars in vars, like Chinese
    # chars, something will be wrong if we don't set correct LANG,
    # force set LANG to en_US.utf-8 by default
    os.environ["LANG"] = "en_US.utf-8"
    args = parse_sys_args(sys.argv)
    init_logging(args.debug, args.verbose, LOG_FILE, args.output_path)
    args.func(args)

if __name__ == "__main__":
    main()
