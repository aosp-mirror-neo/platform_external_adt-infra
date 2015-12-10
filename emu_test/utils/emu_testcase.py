"""Derived class of unittest.TestCase which has contains console and file handler

   This class is intented to be a base class of specific test case classes
"""

import os
import sys
import unittest
import logging
import time
import psutil
import threading
from emu_error import *
from emu_argparser import emu_args
from subprocess import PIPE, STDOUT
from collections import namedtuple
from ConfigParser import ConfigParser

class AVDConfig(namedtuple('AVDConfig', 'api, tag, abi, device, ram, gpu, tot_image, ranchu, port')):
    __slots__ = ()
    def __str__(self):
        device = self.device if self.device != '' else 'defdev'
        for ch in [' ', '(', ')']:
            device = device.replace(ch, '_')
        return str("%s-%s-%s-%s-gpu_%s-api%s" % (self.tag, self.abi,
                                                 device, self.ram, self.gpu,
                                                 self.api))
    def name(self):
        return str(self)
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
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        simple_formatter = logging.Formatter('%(message)s')

        file_name = '%s_%s.log' % (cls.__name__, time.strftime("%Y%m%d-%H%M%S"))

        cls.m_logger = cls.setupLogger(cls.__name__, file_name, log_formatter)
        cls.simple_logger = cls.setupLogger(cls.__name__+'_simple', file_name, simple_formatter)

    @classmethod
    def setupLogger(cls, logger_name, file_name, formatter):

        file_handler = logging.FileHandler(os.path.join(emu_args.session_dir, file_name))
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        # Redirect message to standard out, these messages indicate test progress, they don't belong to stderr
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, emu_args.loglevel.upper()))

        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.setLevel(logging.DEBUG)

        return logger

    @classmethod
    def tearDownClass(cls):
        # clear up log handlers
        psutil.Popen(["adb", "kill-server"])
        def cleanup(logger):
            for x in list(logger.handlers):
                logger.removeHandler(x)
                x.flush()
                x.close()
        cleanup(cls.m_logger)
        cleanup(cls.simple_logger)

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
                    if proc.status() != psutil.STATUS_ZOMBIE:
                        time.sleep(1)
                        term = False
            if term:
                break
        return term

    def launch_emu(self, avd):
        """Launch given avd and return immediately"""
        exec_path = emu_args.emulator_exec
        launch_cmd = [exec_path, "-avd", str(avd), "-port", avd.port, "-verbose", "-show-kernel", "-wipe-data"]
        if avd.ranchu == "yes":
           launch_cmd += ["-ranchu"]

        def launch_in_thread():
            self.start_proc = psutil.Popen(launch_cmd, stdout=PIPE, stderr=STDOUT)
            lines_iterator = iter(self.start_proc.stdout.readline, b"")
            for line in lines_iterator:
            # FIXME: the stdout and stderr from emulator are not true, so we tell if a message is error
            # based on those key words.
                if any(x in line for x in ["ERROR", "FAIL", "error", "failed", "FATAL"]) and not line.startswith('['):
                    self.m_logger.error(line)
                else:
                    self.m_logger.debug(line)

        def find_emu_proc():
            for proc in psutil.process_iter():
                if proc.name() != "emulator.exe" and ("emulator" in proc.name() or "qemu-system" in proc.name()):
                    self.m_logger.debug("Found - %s, pid - %d, status - %s", proc.name(), proc.pid, proc.status())
                    if proc.status() != psutil.STATUS_ZOMBIE:
                        return proc
            return None

        self.m_logger.info('Launching AVD, cmd: %s', ' '.join(launch_cmd))
        t_launch = threading.Thread(target=launch_in_thread)
        t_launch.start()
        time.sleep(5)
        if find_emu_proc() is None:
            raise LaunchError(str(avd))

    def launch_emu_and_wait(self, avd):
        """Launch given avd and wait for boot completion, return boot time"""
        start_time = time.time()
        self.launch_emu(avd)
        completed = "0"
        while time.time()-start_time < emu_args.timeout_in_seconds:
            process = psutil.Popen(["adb", "-s", "emulator-%s" % avd.port, "shell", "getprop", "sys.boot_completed"], stdout=PIPE, stderr=PIPE)
            (output, err) = process.communicate()
            exit_code = process.wait()
            self.m_logger.debug('AVD %s, %s %s', avd, output, err)
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

    def update_config(self, avd_config):
        # avd should be found $HOME/.android/avd/
        dst_path = os.path.join(os.path.expanduser('~'), '.android', 'avd',
                                '%s.avd' % avd_config.name(), 'config.ini')
        if avd_config.device == "":
            self.m_logger.info("No device information, use default settings!")
            with open(dst_path, 'a') as fout:
                fout.write('hw.gpu.enabled=%s' % avd_config.gpu)
            return
        class AVDIniConverter:
            output_file = None
            def __init__(self, file_path):
                self.output_file = file_path
            def write(self, what):
                self.output_file.write(what.replace(" = ", "="))
        config = ConfigParser()
        config.optionxform = str
        file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 '..', 'config', 'avd_template.ini')
        config.read(file_path)
        def set_val(key, val):
            if val != "":
                config.set('Common', key, val)

        tag_id_to_display = {
                             'android-tv': 'Android TV',
                             'android-wear': 'Android Wear',
                             'default': 'Default',
                             'google_apis': 'Google APIs'
                            }
        abi_to_cpu_arch = {
                           'x86': 'x86',
                           'x86_64': 'x86_64',
                           'arm64-v8a': 'arm64',
                           'armeabi-v7a': 'arm',
                           'mips': 'mips',
                           'mips64': 'mips64'
                          }
        for conf in config.options(avd_config.device):
            set_val(conf, config.get(avd_config.device, conf))
        set_val('AvdId', avd_config.name())
        set_val('abi.type', avd_config.abi)
        set_val('avd.ini.displayname', avd_config.name())
        set_val('hw.cpu.arch', abi_to_cpu_arch[avd_config.abi])
        if avd_config.abi == 'armeabi-v7a':
            set_val('hw.cpu.model', 'cortex-a8')
        set_val('hw.gpu.enabled', avd_config.gpu)
        set_val('hw.ramSize', avd_config.ram)
        set_val('image.sysdir.1',
                'system-images/android-%s/%s/%s/' % (avd_config.api, avd_config.tag, avd_config.abi))
        set_val('tag.display', tag_id_to_display[avd_config.tag])
        set_val('tag.id', avd_config.tag)

        self.m_logger.info("Update device settings at %s", dst_path)
        for section in config.sections():
            if section != 'Common':
                config.remove_section(section)

        # remove space around equal sign and header
        with open(dst_path, 'w') as fout:
            config.write(AVDIniConverter(fout))
        with open(dst_path, 'r') as fin:
            data = fin.read().splitlines(True)
        with open(dst_path, 'w') as fout:
            fout.writelines(data[1:])

    def create_avd(self, avd_config):
        """Create avd if doesn't exist

           return 0 if avd exist or creation succeeded
           otherwise, return value of creation process.
        """
        avd_name = str(avd_config)

        def try_create():
            android_exec = "android.bat" if os.name == "nt" else "android"
            avd_abi = "%s/%s" % (avd_config.tag, avd_config.abi)
            if "google" in avd_config.tag:
                avd_target = "Google Inc.:Google APIs:%s" % (avd_config.api)
            else:
                avd_target = "android-%s" % (avd_config.api)
            create_cmd = [android_exec, "create", "avd", "--force",
                          "--name", avd_name, "--target", avd_target,
                          "--abi", avd_abi]
            self.m_logger.info("Create AVD, cmd: %s" % ' '.join(create_cmd))
            avd_proc = psutil.Popen(create_cmd,
                                    stdout=PIPE, stdin=PIPE, stderr=PIPE)
            output, err = avd_proc.communicate(input='\n')
            self.simple_logger.debug(output)
            self.simple_logger.debug(err)
            if 'Error' in err:
                return -1
            return avd_proc.poll()

        ret = try_create()
        if ret != 0:
            # try to download the system image
            self.update_sdk("android-%s" % avd_config.api)
            if "google" in avd_config.tag:
                self.update_sdk("addon-google_apis-google-%s" % avd_config.api)
                self.update_sdk("sys-img-%s-addon-google_apis-google-%s"
                                % (avd_config.abi, avd_config.api))
            elif "wear" in avd_config.tag:
                self.update_sdk("sys-img-%s-android-wear-%s" % (avd_config.abi, avd_config.api))
            elif "tv" in avd_config.tag:
                self.update_sdk("sys-img-%s-android-tv-%s" % (avd_config.abi, avd_config.api))
            else:
                self.update_sdk("sys-img-%s-android-%s" % (avd_config.abi, avd_config.api))
            self.m_logger.debug("try create avd again after update sdk")
            ret = try_create()

        if ret == 0:
            self.update_config(avd_config)

        return ret

    def update_sdk(self, filter):
        """Update sdk from command line with given filter"""

        android_exec = "android.bat" if os.name == "nt" else "android"
        cmd = [android_exec, "update", "sdk", "--no-ui", "--all", "--filter", filter]
        self.m_logger.debug("update sdk %s", ' '.join(cmd))
        update_proc = psutil.Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE)
        output, err = update_proc.communicate(input='y\n')
        self.simple_logger.debug(output)
        self.simple_logger.debug(err)
        self.m_logger.debug('return value of update proc: %s', update_proc.poll())
        return update_proc.poll()
