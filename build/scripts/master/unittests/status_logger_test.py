#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import json
import os
import tempfile
import shutil
import unittest

import test_env  # pylint: disable=W0611,W0403

from master import status_logger


### Mock buildbot objects.

class Builder(object):
  name = 'coconuts'


class Properties(object):
  def getProperty(self, _name):
    return 'whatever'


class Build(object):
  def getNumber(self):
    return 5

  def getBuilder(self):
    return Builder()

  def getSlavename(self):
    return 'cool-m1'

  def getProperty(self, _name):
    return 1427929423.0

  def getProperties(self):
    return Properties()

  def getTimes(self):
    return 5000, 6000


class Step(object):
  step_number = 8
  def getName(self):
    return 'reticulating_splines'

  def getTimes(self):
    return 5100, 5500


@contextlib.contextmanager
def _make_logger(file_content=None):
  """Create a status_logger and delete any temp files when done."""
  tempdir = tempfile.mkdtemp(prefix='status-logger')

  filename = 'logstatus'
  if file_content is None:
    filename = 'does_not_exist'
  else:
    with open(os.path.join(tempdir, filename), 'w') as f:
      if not file_content:
        f.write('\n')
      else:
        f.write(json.dumps(file_content))

  logger = status_logger.StatusEventLogger(
    configfile=filename, basedir=tempdir, event_logging_dir=tempdir)
  logger._create_logger()
  logger._create_event_logger()
  logger._create_ts_mon_logger()
  yield logger

  if os.path.exists(tempdir):
    shutil.rmtree(tempdir)


### Main test class.

class StatusLoggerTest(unittest.TestCase):
  def testNoFile(self):
    with _make_logger() as logger:
      self.assertTrue(logger)

  def testNormalInitialization(self):
    with _make_logger('') as logger:
      self.assertTrue(logger.active)
      self.assertTrue(logger._logging)

  def testDisableLogger(self):
    with _make_logger({'file_logging': False}) as logger:
      self.assertTrue(logger.active)
      self.assertFalse(logger._logging)

  def testConfigureEndpoints(self):
    config_dict = {
        'logfile': '/tmp/bummer',
        'logging_ignore_basedir': True,
    }
    with _make_logger(config_dict) as logger:
      self.assertTrue(logger.active)
      self.assertTrue(logger._logging)
      self.assertTrue(logger._event_logging_dir)
      self.assertEqual(logger.logfile, '/tmp/bummer')

  def testStartBuild(self):
    config_dict = {
        'file_logging': True,
        'event_logging': True,
    }
    with _make_logger(config_dict) as logger:
      logger.buildStarted('coconuts', Build())
      self.assertTrue(os.path.exists(logger.logfile))
      self.assertTrue(os.path.isdir(logger._event_logging_dir))
      self.assertTrue(os.path.exists(logger._event_logfile))
      # Ensure we added valid json
      with open(logger._event_logfile, 'r') as f:
        content = f.read()
        self.assertTrue(content)
        json.loads(content)

  def testStartStep(self):
    config_dict = {
        'file_logging': True,
        'event_logging': True,
    }
    with _make_logger(config_dict) as logger:
      logger.stepStarted(Build(), Step())
      self.assertTrue(os.path.exists(logger.logfile))
      self.assertTrue(os.path.isdir(logger._event_logging_dir))
      self.assertTrue(os.path.exists(logger._event_logfile))
      # Ensure we added valid json
      with open(logger._event_logfile, 'r') as f:
        content = f.read()
        self.assertTrue(content)
        json.loads(content)

  def testStopBuild(self):
    config_dict = {
        'file_logging': True,
        'event_logging': True,
    }
    with _make_logger(config_dict) as logger:
      logger.buildFinished('coconuts', Build(), 0)
      self.assertTrue(os.path.exists(logger.logfile))
      self.assertTrue(os.path.isdir(logger._event_logging_dir))
      self.assertTrue(os.path.exists(logger._event_logfile))
      # Ensure we added valid json
      with open(logger._event_logfile, 'r') as f:
        content = f.read()
        self.assertTrue(content)
        json.loads(content)

  def testStopStep(self):
    config_dict = {
        'file_logging': True,
        'event_logging': True,
    }
    with _make_logger(config_dict) as logger:
      logger.stepFinished(Build(), Step(), [0])
      self.assertTrue(os.path.exists(logger.logfile))
      self.assertTrue(os.path.isdir(logger._event_logging_dir))
      self.assertTrue(os.path.exists(logger._event_logfile))
      # Ensure we added valid json
      with open(logger._event_logfile, 'r') as f:
        content = f.read()
        self.assertTrue(content)
        json.loads(content)


if __name__ == '__main__':
  unittest.main()
