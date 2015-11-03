"""Derived class of unittest.TestCase which has contains console and file handler

   This class is intented to be a base class of specific test case classes
"""

import os
import unittest
import logging
import time
import psutil
from emu_argparser import emu_args
from subprocess import PIPE

class LoggedTestCase(unittest.TestCase):
    # Two logger are provided for each class
    # m_logger, used for script message, that are indicating the status of script
    # simple_logger, used for message from external process, keep their original format
    m_logger = None
    simple_logger = None

    def __init__(self, *args, **kwargs):
        super(LoggedTestCase, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        print
        print "=================== Start of", cls.__name__, "==================="
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        simple_formatter = logging.Formatter('%(message)s')

        file_name = '%s_%s.log' % (cls.__name__, time.strftime("%Y%m%d-%H%M%S"))

        cls.m_logger = cls.setupLogger(cls.__name__, file_name, log_formatter)
        cls.simple_logger = cls.setupLogger(cls.__name__+'_simple', file_name, simple_formatter)

    @classmethod
    def setupLogger(cls, logger_name, file_name, formatter):

        file_handler = logging.FileHandler(os.path.join(emu_args.session_dir, file_name))
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.setLevel(getattr(logging, emu_args.loglevel.upper()))

        return logger

    @classmethod
    def tearDownClass(cls):
        print "=================== End of", cls.__name__, "==================="
        # clear up log handlers
        cls.m_logger.handlers = []

class EmuBaseTestCase(LoggedTestCase):
    """Base class for Emulator TestCase class

    Provide common base functions that will be used in derived emu test classes
    """
    def __init__(self, *args, **kwargs):
        super(EmuBaseTestCase, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        super(EmuBaseTestCase, cls).setUpClass()

    def setUp(self):
        self.m_logger.info('Running - %s', self._testMethodName)

    def term_check(self, timeout):
        """Check if emulator process has terminated, return True if terminated else False"""
        for x in range(timeout):
            term = True
            for proc in psutil.process_iter():
                if "emulator" in proc.name() or "qemu-system" in proc.name():
                    self.m_logger.debug("Found - %s, pid - %d, status - %s", proc.name(), proc.pid, proc.status())
                    if proc.status() is psutil.STATUS_RUNNING:
                        time.sleep(1)
                        term = False
            if term:
                break
        return term

    def launch_emu(self, avd):
        """Launch given avd and return immediately"""
        exec_path = emu_args.emulator_exec
        self.m_logger.info('Launching AVD %s, cmd: %s -avd %s', avd, exec_path, avd)
        start_proc = psutil.Popen([exec_path, "-avd", avd], stdout=PIPE, stderr=PIPE)
        time.sleep(5)
        if start_proc.poll() is not None and start_proc.poll() is not 0:
            m_logger.error(start_proc.communicate()[1])
            raise LaunchError(avd)

    def launch_emu_and_wait(self, avd):
        """Launch given avd and wait for boot completion, return boot time"""
        start_time = time.time()
        self.launch_emu(avd)
        completed = "0"
        for count in range(emu_args.timeout_in_seconds):
            process = psutil.Popen(["adb", "shell", "getprop", "sys.boot_completed"], stdout=PIPE, stderr=PIPE)
            (output, err) = process.communicate()
            exit_code = process.wait()
            self.m_logger.debug('%d - AVD %s, %s %s', count, avd, output, err)
            if exit_code is 0:
                completed = output.strip()
            if completed is "1":
                break;
            time.sleep(1)
        if completed is not "1":
            self.m_logger.error('AVD %s didn\'t boot up within %s seconds', avd, emu_args.timeout_in_seconds)
            raise TimeoutError(avd, emu_args.timeout_in_seconds)
        boot_time = time.time() - start_time
        self.m_logger.info('AVD %s, boot time is %s', avd, boot_time)
        return boot_time
