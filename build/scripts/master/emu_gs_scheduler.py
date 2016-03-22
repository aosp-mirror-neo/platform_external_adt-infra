# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This SingleBranchScheduler download necessary emulator package and include it in build properties

"""

import os, sys
import gcs_oauth2_boto_plugin
import StringIO
from boto import boto
from twisted.python import log
from twisted.internet import defer, utils
from buildbot.schedulers.timed import Periodic
from buildbot.schedulers.basic import SingleBranchScheduler

google_storage = 'gs'

class EmulatorSingleBranchScheduler(SingleBranchScheduler):
  """Augmented 'SingleBranchScheduler' that adds emu_image properties"""

  # Overrides 'SingleBranchScheduler.addBuildsetForChanges'
  @defer.inlineCallbacks
  def addBuildsetForChanges(self, *args, **kwargs):
    project = None
    try:
      with open('project.cache', 'r') as rfile:
        project = rfile.readlines()
    except:
      log.msg("%s: Error reading project.cache" % self.name)
    for x in ['windows', 'linux', 'mac']:
      if x in self.name:
        if project is not None and 'emu-2.0-release' in project:
          emu_cache_file = 'emulator_2.0_%s_poller.cache' % x
        else:
          emu_cache_file = 'emulator_%s_poller.cache' % x

    def readRev(cache_file):
      rev, file_list = 'None', ''
      try:
        with open(cache_file, 'r') as f:
          content = f.read().splitlines()
          rev = content[0]
          file_list = ','.join(content[1:])
      except:
        log.msg("%s: Error - %s file not available" % (self.name, cache_file))
      return rev, file_list

    emu_revision, emu_file = readRev(emu_cache_file)
    if emu_revision == 'None':
      log.msg("%s: Error - emu cache file %s not available, cancel build" % (self.name, emu_cache_file))
      return
    lmp_mr1_revision, lmp_mr1_file = readRev('sys_image_lmp_mr1_poller.cache')
    mnc_revision, mnc_file = readRev('sys_image_mnc_poller.cache')

    if 'dev' in self.name:
      nyc_poller = 'sys_image_nyc_dev_poller.cache'
    else:
      nyc_poller = 'sys_image_nyc_release_poller.cache'

    nyc_revision, nyc_file = readRev(nyc_poller)
    lmp_revision, lmp_file = readRev('sys_image_lmp_poller.cache')
    klp_revision, klp_file = readRev('sys_image_klp_poller.cache')

    self.properties.setProperty('mnc_revision', mnc_revision, 'Scheduler')
    self.properties.setProperty('mnc_system_image', mnc_file, 'Scheduler')
    self.properties.setProperty('lmp_mr1_revision', lmp_mr1_revision, 'Scheduler')
    self.properties.setProperty('lmp_mr1_system_image', lmp_mr1_file, 'Scheduler')
    self.properties.setProperty('nyc_revision', nyc_revision, 'Scheduler')
    self.properties.setProperty('nyc_system_image', nyc_file, 'Scheduler')
    self.properties.setProperty('klp_revision', klp_revision, 'Scheduler')
    self.properties.setProperty('klp_system_image', klp_file, 'Scheduler')
    self.properties.setProperty('lmp_revision', lmp_revision, 'Scheduler')
    self.properties.setProperty('lmp_system_image', lmp_file, 'Scheduler')
    self.properties.setProperty('emu_revision', emu_revision, 'Scheduler')
    self.properties.setProperty('emulator_image', emu_file, 'Scheduler')
    self.properties.setProperty('got_revision', '%s-%s-%s-%s-%s' % (emu_revision, mnc_revision, lmp_mr1_revision, nyc_revision, lmp_revision), 'Scheduler')
    self.properties.setProperty('logs_dir', os.path.join(os.getcwd(), 'slave_logs', ''), 'Scheduler')
    if 'emu-2.0-release' in project:
        self.properties.setProperty('emu_branch', 'emu-2.0-release', 'Scheduler')
    else:
        self.properties.setProperty('emu_branch', 'emu-master-dev', 'Scheduler')

    rv = yield SingleBranchScheduler.addBuildsetForChanges(
        self,
        *args,
        **kwargs)
    defer.returnValue(rv)
