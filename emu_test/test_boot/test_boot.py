"""Test the emulator boot time"""

import unittest
import os
import time
import psutil
import csv
import shutil
from subprocess import Popen, PIPE

from utils.emu_error import *
from utils.emu_argparser import emu_args
from utils.emu_testcase import EmuBaseTestCase, AVDConfig

class BootTestCase(EmuBaseTestCase):
    def __init__(self, *args, **kwargs):
        super(BootTestCase, self).__init__(*args, **kwargs)
        self.avd_config = None

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
        self.m_logger.info("Remove AVD inside of tear down")
        # avd should be found $HOME/.android/avd/
        avd_dir = os.path.join(os.path.expanduser('~'), '.android', 'avd')
        try:
            os.remove(os.path.join(avd_dir, '%s.ini' % self.avd_config.name()))
            shutil.rmtree(os.path.join(avd_dir, '%s.avd' % self.avd_config.name()), ignore_errors=True)
        except:
            pass

    def boot_check(self, avd):
        boot_time = self.launch_emu_and_wait(avd)
        self.m_logger.info('AVD %s, boot time: %s, expected time: %s', avd, boot_time, emu_args.expected_boot_time)
        self.assertLessEqual(boot_time, emu_args.expected_boot_time)

    def run_boot_test(self, avd_config):
        self.avd_config = avd_config
        self.assertEqual(self.create_avd(avd_config), 0)
        self.boot_check(str(avd_config))

def create_test_case_from_file():

    def create_test_case(avd_config):
        return lambda self: self.run_boot_test(avd_config)

    with open(emu_args.config_file, "rb") as file:
        reader = csv.reader(file)
        for row in reader:
            #skip the first line
            if reader.line_num == 1:
                continue
            if reader.line_num == 2:
                builder_idx = row.index(emu_args.builder_name)
            else:
                if(row[0].strip() != ""):
                    api = row[0].split("API", 1)[1].strip()
                if(row[1].strip() != ""):
                    tag = row[1].strip()
                if(row[2].strip() != ""):
                    abi = row[2].strip()

                # P - config should be passing
                # X - config is expected to fail
                # S and everything else - Skip this config
                op = row[builder_idx].strip().upper()
                if op in ["P", "X", "F"]:
                    avd_config = AVDConfig(api, tag, abi, row[3], row[4], row[5])
                    if op == "X":
                        setattr(BootTestCase, "test_boot_%s" % str(avd_config),
                                unittest.expectedFailure(create_test_case(avd_config)))
                    else:
                        setattr(BootTestCase, "test_boot_%s" % str(avd_config), create_test_case(avd_config))

def create_test_case_for_avds():
    avd_list = emu_args.avd_list
    for avd in avd_list:
        def fn(i):
            return lambda self: self.boot_check(i)
        setattr(BootTestCase, "test_boot_%s" % avd, fn(avd))

if emu_args.config_file is None:
    create_test_case_for_avds()
else:
    create_test_case_from_file()

if __name__ == '__main__':
    os.environ["SHELL"] = "/bin/bash"
    emu_argparser.emu_args = emu_argparser.get_parser().parse_args()
    print emu_argparser.emu_args
    sys.argv[1:] = emu_args.unittest_args
    unittest.main()
