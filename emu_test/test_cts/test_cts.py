"""Test the emulator boot time"""

import os, platform
import unittest
import time
import psutil
import re
from subprocess import PIPE

from utils.emu_error import *
from utils.emu_argparser import emu_args
from utils.emu_testcase import EmuBaseTestCase

api_to_android_version = {"23": "6.0",
                          "22": "5.1",
                          "21": "5.0",
                          "19": "4.4",
                          "18": "4.3",
                          "17": "4.2",
                          "16": "4.1",
                          "15": "4.0",
                          "10": "2.3"}
class CTSTestCase(EmuBaseTestCase):
    def __init__(self, *args, **kwargs):
        super(CTSTestCase, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        super(CTSTestCase, cls).setUpClass()

    def setUp(self):
        self.m_logger.info('Running - %s', self._testMethodName)

    def tearDown(self):
        self.m_logger.debug('First try - quit emulator by adb emu kill')
        kill_proc = psutil.Popen(["adb", "emu", "kill"], stdout=PIPE, stderr=PIPE)

        # check emulator process is terminated
        if not self.term_check(timeout=10):
            self.m_logger.debug('Second try - quit emulator by psutil')
            for x in psutil.process_iter():
                proc = psutil.Process(x.pid)
                # mips 64 use qemu-system-mipsel64, others emulator-[arch]
                if "emulator" in proc.name() or "qemu-system" in proc.name():
                    proc.kill()
            result = self.term_check(timeout=10)
            self.m_logger.debug("term_check after psutil.kill - %s", result)

    def get_cts_exec(self, avd):
        home_dir = os.path.expanduser('~')
        host = platform.system()
        if host == "Darwin" or host == "Linux":
            cts_home = os.path.join(home_dir, 'Android/CTS')
        elif host == "Windows":
            cts_home = 'C:\\CTS'
        # expected avd name [arch]-[api]-[CTS]
        name_pattern = re.compile("^(.*)-(.*)-CTS$")
        res = re.match(name_pattern, avd)
        assert res is not None
        arch = res.group(1)
        api = res.group(2)
        cts_dir = "%s-%s" % (api_to_android_version[api], arch)
        return os.path.join(cts_home, cts_dir, 'android-cts', 'tools', 'cts-tradefed')

    def run_cts_plan(self, avd, plan):
        result_re = re.compile("^.*XML test result file generated at .*Passed ([0-9]+), Failed ([0-9]+), Not Executed ([0-9]+)")
        result_line = ""
        self.launch_emu_and_wait(avd)
        exec_path = self.get_cts_exec(avd)
        cts_proc = psutil.Popen([exec_path, "run", "cts", "--plan", plan, "--disable-reboot"], stdout=PIPE, stderr=PIPE)
        self.m_logger.debug("CTS process poll %s", cts_proc.poll())
        while cts_proc.poll() is None:
            line = cts_proc.stdout.readline()
            self.simple_logger.info(line)
            if re.match(result_re, line):
                result_line = line
        if result_line is not "":
            pass_count = re.match(result_re, result_line).group(1)
            fail_count = re.match(result_re, result_line).group(2)
            self.assertNotEqual(pass_count, '0')
            self.assertEqual(fail_count, '0')
        self.m_logger.debug("CTS process poll %s", cts_proc.poll())

def create_test_case_for_avds():
    avd_list = emu_args.avd_list
    for avd in avd_list:
        def fn(i, plan):
            return lambda self: self.run_cts_plan(i, plan)
        if "CTS" in avd:
            setattr(CTSTestCase, "test_cts_Short_%s" % avd, fn(avd, "Short"))

create_test_case_for_avds()
if __name__ == '__main__':
    emu_argparser.emu_args = emu_argparser.get_parser().parse_args()
    print emu_argparser.emu_args
    sys.argv[1:] = emu_args.unittest_args
    unittest.main()
