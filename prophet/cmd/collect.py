#!/usr/bin/env python
# -*- coding=utf8 -*-

# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2021 OnePro Cloud (Shanghai) Ltd.
#
# Authors: Ray <ray.sun@oneprocloud.com>
#
# Copyright (c) 2019 This file is confidential and proprietary.
# All Rights Resrved, OnePro Cloud (Shanghai) Ltd (http://www.oneprocloud.com).
# Global settings for logging, default is debug and verbose

import argparse
import logging
import os
import pandas as pd
import shutil
import sys
import time

from prophet.controller.network import NetworkController
from prophet.controller.batch_job import BatchJob

VER = "1.1.0 Beta"

# Default log name
LOG_FILE = "prophet.log"

def log_init(debug=False, verbose=False, log_path=None):
    """Set up global logs"""
    log_format = "%(asctime)s %(process)s %(levelname)s [-] %(message)s"
    log_level = logging.DEBUG if debug else logging.INFO

    # Always write log file
    log_file = os.path.join(log_path, LOG_FILE)

    logging.basicConfig(
        format=log_format,
        level=log_level,
        filename=log_file)
 
    if verbose:
        logging.getLogger().addHandler(logging.StreamHandler())

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

def batch_collection(args):
    host_file = args.host_file
    output_path = args.output_path
    force_check = args.force_check

    batch_job = BatchJob(host_file, output_path, force_check)
    batch_job.collect()
    batch_job.package()

def parse_sys_args(argv):
    """Parses commaond-line arguments"""
    parser = argparse.ArgumentParser(
        description="HyperMotion Hosts Investigation Tool")
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
    parser_scan_network.set_defaults(func=scan_network)

    # Collect Arguments
    #collect_group = parser.add_argument_group(
    #        title="Collect hosts info via host list file.")
    parser_collect = subparsers.add_parser("collect")
    parser_collect.add_argument("--host-file", dest="host_file",
            required=True, help="Host file which generated by network scan")
    parser_collect.add_argument("--output-path", dest="output_path",
            required=True, help="Output path for batch collection")
    parser_collect.add_argument("-f", "--force-check", action="store_true",
                                dest="force_check", default=False,
                                help="Force check all hosts")
    parser_collect.set_defaults(func=batch_collection)

    return parser.parse_args(argv[1:])
 
def main():
    args = parse_sys_args(sys.argv)
    log_init(args.debug, args.verbose, args.output_path)
    args.func(args)
 
if __name__ == "__main__":
    main()
