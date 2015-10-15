#!/usr/bin/env python

"""
A simple testing framework for emulator using python's unit testing framework.

Type:

./dotest.py -h

for available options.
"""

import sys
import os
import unittest
import logging
import re

from utils import emu_argparser
from utils import emu_unittest

# Provides a regular expression for matching fail message
TIMEOUT_REGEX = re.compile(r"(^\d+)([smhd])?$")
#AssertionError: 37.59494113922119 not less than or equal to 30
def printResult(emuResult):
    print
    print "Test Summary"
    print ("Run %d tests (%d fail, %d pass)" % 
           (emuResult.testsRun, len(emuResult.failures)+len(emuResult.errors), len(emuResult.passes)))
    if len(emuResult.errors) > 0 or len(emuResult.failures) > 0:
        for x in emuResult.errors:
            if x[1].splitlines()[-1] == "TimeoutError":
                print "TIMEOUT: ", x[0].id()
            else: 
                print "FAIL: ", x[0].id()
        for x in emuResult.failures:
            print "FAIL: ", x[0].id()
    if len(emuResult.passes) > 0:
        print '------------------------------------------------------'
    for x in emuResult.passes:
        print "PASS: ", x.id()
    print
    print "Test successful - ", emuResult.wasSuccessful()

# Run the test case
if __name__ == '__main__':

    os.environ["SHELL"] = "/bin/bash"
    emu_argparser.emu_args = emu_argparser.get_parser().parse_args()
    logging.basicConfig(level=getattr(logging, emu_argparser.emu_args.loglevel.upper()), format='%(asctime)s - %(levelname)s - %(message)s')

    print emu_argparser.emu_args

    from boot_test.boot_test import BootTestCase

    emuSuite = unittest.TestLoader().loadTestsFromTestCase(BootTestCase)
    emuRunner = emu_unittest.EmuTextTestRunner()
    emuResult = emuRunner.run(emuSuite)
    printResult(emuResult)

    sys.exit(not emuResult.wasSuccessful())
