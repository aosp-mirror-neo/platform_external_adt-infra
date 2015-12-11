"""Test the emulator boot time"""

import unittest
import os
import platform
import time
import psutil
import csv
import shutil

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
        kill_proc = psutil.Popen(["adb", "emu", "kill"])
        # check emulator process is terminated

        if not self.term_check(timeout=5):
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
            psutil.Popen(["adb", "kill-server"])
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
        self.boot_check(avd_config)

def get_port():
    if not hasattr(get_port, '_port'):
        get_port._port = 5552
    get_port._port += 2
    return str(get_port._port)

def create_test_case_from_file():
    """ Create test case based on test configuration file. """

    def valid_case(avd_config):
        if emu_args.filter_dict is not None:
            for key, value in emu_args.filter_dict.iteritems():
                if getattr(avd_config, key) != value:
                    return False
        return True

    def create_test_case(avd_config, op):
        if op == "S" or op == "" or not valid_case(avd_config):
            return

        func = lambda self: self.run_boot_test(avd_config)
        if op == "X":
            func = unittest.expectedFailure(func)
        # TODO: handle flakey tests
        elif op == "F":
            func = func
        qemu_str = "_qemu2" if avd_config.ranchu == "yes" else ""
        setattr(BootTestCase, "test_boot_%s%s" % (str(avd_config), qemu_str), func)

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
                    device = row[3]
                    if row[4] != "":
                        ram = row[4]
                    else:
                        ram = "512" if device == "" else "1536"
                    if row[5] != "":
                        gpu = row[5]
                    else:
                        gpu = "yes" if api > "15" else "no"
                    # For 32 bit machine, ram should be less than 768MB
                    if not platform.machine().endswith('64'):
                        ram = str(min([int(ram), 768]))
                    if api < "22" and row[6] == "yes":
                        raise ConfigError()
                    tot_image = row[6] if row[6] == "yes" else "no"
                    avd_config = AVDConfig(api, tag, abi, device, ram, gpu, tot_image, ranchu="no", port=get_port())
                    create_test_case(avd_config, op)
                    # for unreleased images, test with qemu2 in addition
                    if tot_image == "yes":
                        avd_config = AVDConfig(api, tag, abi, device, ram, gpu, tot_image, ranchu="yes", port=get_port())
                        create_test_case(avd_config, op)

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
