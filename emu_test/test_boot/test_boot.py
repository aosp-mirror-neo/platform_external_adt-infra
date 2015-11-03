"""Test the emulator boot time"""

import unittest
import time
import psutil
from subprocess import Popen, PIPE

from utils.emu_error import *
from utils.emu_argparser import emu_args
from utils.emu_testcase import EmuBaseTestCase

class BootTestCase(EmuBaseTestCase):
    def __init__(self, *args, **kwargs):
        super(BootTestCase, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        super(BootTestCase, cls).setUpClass()

    def tearDown(self):
        self.m_logger.debug('First try - quit emulator by adb emu kill')
        kill_proc = Popen(["adb", "emu", "kill"], stdout=PIPE, stderr=PIPE)
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

    def boot_check(self, avd):
        boot_time = self.launch_emu_and_wait(avd)
        self.m_logger.info('AVD %s, boot time: %s, expected time: %s', avd, boot_time, emu_args.expected_boot_time)
        self.assertLessEqual(boot_time, emu_args.expected_boot_time)

def create_test_case_for_avds():
    avd_list = emu_args.avd_list
    for avd in avd_list:
        def fn(i):
            return lambda self: self.boot_check(i)
        setattr(BootTestCase, "test_boot_%s" % avd, fn(avd))

create_test_case_for_avds()

if __name__ == '__main__':
    os.environ["SHELL"] = "/bin/bash"
    emu_argparser.emu_args = emu_argparser.get_parser().parse_args()
    print emu_argparser.emu_args
    sys.argv[1:] = emu_args.unittest_args
    unittest.main()
