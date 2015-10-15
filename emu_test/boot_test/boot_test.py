"""Test the emulator boot time"""

import unittest
import os, sys
import logging
import time
import telnetlib
import psutil
from subprocess import Popen, PIPE

from utils.emu_error import *
from utils.emu_argparser import emu_args

class BootTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(BootTestCase, self).__init__(*args, **kwargs)
        self.start_proc = None
    def setUp(self):
        logging.info('Running - %s', self._testMethodName)
    def tearDown(self):
        logging.debug('First try - quit emulator by adb emu kill')
        kill_proc = Popen(["adb", "emu", "kill"], stdout=PIPE, stderr=PIPE)
        kill_proc.wait()
        # check emulator process is terminated
        
        def nx_term_check():
            logging.debug('term_check called') 
            for count in range(10):
                logging.debug('Waiting for emulator terminate - %d', count) 
                time.sleep(1)
                if self.start_proc.poll() is not None:
                    logging.debug('self.start_proc.poll() returned - %d', self.start_proc.poll()) 
                    return True
            return False
        """
            if not self.term_check():
            logging.debug('Second try - quit emulator by telnet')
            # unable to quit emulator by 'emu kill', try kill from telnet
            tn = telnetlib.Telnet("localhost","5554")
            tn.write("kill\n")
            if not self.term_check():
                logging.debug('Third try - quit emulator by popen.terminate')
                self.start_proc.terminate()
                self.term_check()
		"""
        if not self.term_check():
            logging.debug('Second try - quit emulator by psutil')
            for x in psutil.process_iter():
                proc = psutil.Process(x.pid) 
                if "emulator" in proc.name():
                    proc.kill()
            logging.debug("term_check after psutil.kill - %s", self.term_check()) 
    def term_check(self):
        for count in range(10):
            term = True
            for proc in psutil.process_iter():
                if "emulator" in proc.name() and proc.status() is psutil.STATUS_RUNNING:
                    logging.debug("Found - %s, pid - %d, status - %s", proc.name(), proc.pid, proc.status())
                    time.sleep(1)
                    term = False
        return term
    def launch_emu(self, avd):
        exec_path = "emulator"
        logging.info('Launching AVD %s, cmd: %s -avd %s', avd, exec_path, avd)
        self.start_proc = Popen([exec_path, "-avd", avd], stdout=PIPE, stderr=PIPE)
        time.sleep(5)
        if self.start_proc.poll() is not None and self.start_proc.poll() is not 0:
            logging.error(self.start_proc.communicate()[1])
            raise LaunchError(avd)
    def boot_check(self, avd):
        start_time = time.time()
        self.launch_emu(avd)
        completed = "0"
        for count in range(emu_args.timeout_in_seconds):
            process = Popen(["adb", "shell", "getprop", "sys.boot_completed"], stdout=PIPE, stderr=PIPE)
            (output, err) = process.communicate()
            exit_code = process.wait()
            logging.debug('%d - AVD %s, %s %s', count, avd, output, err)
            if exit_code is 0:
                completed = output.strip()
            if completed is "1":
                break;
            time.sleep(1)
        if completed is not "1":
            logging.error('AVD %s didn\'t boot up within %s seconds', avd, emu_args.timeout_in_seconds)
            raise TimeoutError(avd, emu_args.timeout_in_seconds)
        boot_time = time.time() - start_time
        logging.info('AVD %s, boot time is %s', avd, boot_time)
        self.assertLessEqual(boot_time, emu_args.expected_boot_time)

def create_test_case_for_avds():
    if emu_args.avd_list is not None:
        avd_list = emu_args.avd_list
    else:
        # avd is searched in the order of $ANDROID_AVD_HOME,$ANDROID_SDK_HOME/.android/avd and $HOME/.android/avd
        android_exec = "android.bat" if os.name == "nt" else "android"
        avd_list_proc = Popen([android_exec, "list", "avd", "-c"], stdout=PIPE, stderr=PIPE)
        (output, err) = avd_list_proc.communicate()
        logging.debug(output)
        logging.debug(err)
        avd_list = [x.strip() for x in output.splitlines()]
    logging.info("Run test for %d AVDs - %s", len(avd_list), avd_list)
    for avd in avd_list:
        def fn(i):
            return lambda self: self.boot_check(i)
        setattr(BootTestCase, "test_boot_%s" % avd, fn(avd))
create_test_case_for_avds()
if __name__ == '__main__':
    os.environ["SHELL"] = "/bin/bash"
    emu_argparser.emu_args = emu_argparser.get_parser().parse_args()
    logging.basicConfig(level=getattr(logging, emu_argparser.emu_args.loglevel.upper()), format='%(asctime)s - %(levelname)s - %(message)s')
    print emu_argparser.emu_args
    sys.argv[1:] = emu_args.unittest_args
    unittest.main()
