#!/usr/bin/python

# This is a standalone script to remove files older than
# x days under specified directory
# it takes optional filter string on file names
# For example, to delete all files under /tmp directory
# with filename prefix "android" and older than 7 days, run the command:
# python remove_files 7 /tmp -p "android.*"

import os, sys, time
import re
import argparse
import logging
from logging.handlers import RotatingFileHandler
import traceback

parser = argparse.ArgumentParser(description='Download and unzip a list of files separated by comma')
parser.add_argument('age', type=int, help='delete files that are older than age days')
parser.add_argument('root_dir', help='root directory to delete files from')
parser.add_argument('-p', dest='pattern', default='.*', help='filter string used to match file name')

args = parser.parse_args()

parser_dir = os.path.dirname(os.path.realpath(__file__))

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = RotatingFileHandler(os.path.join(parser_dir, "cleanup_logs.txt"), maxBytes=1048576, backupCount=10)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

logger = logging.getLogger()
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

print "pattern", args.pattern
name_pattern = re.compile(args.pattern)

def remove_files():
    """Remove files older than age from root_dir"""
    cutoff_time = time.time() - args.age*86400

    def fn(cur_dir):
        logger.info("searching directory: %s", cur_dir)
        for x in os.listdir(cur_dir):
            xpath = os.path.join(cur_dir, x)
            if os.path.isfile(xpath):
                if name_pattern.match(x) and os.stat(xpath).st_mtime < cutoff_time:
                    logger.info("Remove %s", xpath)
                    os.remove(xpath)
            elif os.path.isdir(xpath):
                fn(xpath)
    fn(args.root_dir)

if __name__ == "__main__":
    try:
        logging.info("Start remove_old_files script ...")
        remove_files()
    except:
        logging.error(traceback.format_exc())
        exit(0)
