#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function

import os
import subprocess
import test_env  # pylint: disable=W0611
import time
import unittest
from common import find_depot_tools  # pylint: disable=W0611
from tools import slavedisk
from testing_support import auto_stub

COMMUNICATE = None
FILES = None
STATS = None
OUTPUT = None

class MockStatbuf(object):
  def __init__(self, ctime, mode=040000):
    self.st_ctime = ctime
    self.st_mode = mode

def MockCommunicate(fullness):
  return ["x x x x Use%%\ny y y y %d" % fullness]

class MockDf():
  def communicate(self):
    return COMMUNICATE

def MockPrint(s=""):
  global OUTPUT
  OUTPUT += s
  OUTPUT += "\n"

def MockStat(f):
  return STATS[f]

class SlaveDiskTest(auto_stub.TestCase):
  def setUp(self):
    global OUTPUT
    OUTPUT = ""

    # If you try to mock os.stat(), the testing framework blows up.
    # So don't try to uncomment the following line:
    # self.mock(os, 'stat', self.MockStat)

    self.mock(os, 'chdir', self.MockChdir)
    self.mock(os, 'listdir', self.MockListdir)
    self.mock(os.path, 'exists', self.MockExists)
    self.mock(subprocess, 'Popen', self.MockPopen)
    self.mock(time, 'time', self.MockTime)
    super(SlaveDiskTest, self).setUp()

  def MockExists(self, f):
    return True

  def MockChdir(self, d):
    pass

  def MockListdir(self, d):
    return FILES

  def MockTime(self):
    return 86400 * 30

  def MockPopen(self, *a, **kw):
    return MockDf()

  def tearDown(self):
    super(SlaveDiskTest, self).tearDown()

  def test_full(self):
    """Test what happens when the disk is full."""
    global COMMUNICATE
    global FILES
    global STATS
    COMMUNICATE = MockCommunicate(100)
    FILES = ['foo']
    STATS = dict(foo=MockStatbuf(0))
    rv = slavedisk.main(stat=MockStat, print=MockPrint)

    self.assertEqual(rv, 0)
    self.assertIn("rm -rf /b/build/slave/foo # 30 days old", OUTPUT)

  def test_not_full(self):
    """Test what happens when the disk is NOT full."""
    global COMMUNICATE
    global FILES
    global STATS
    COMMUNICATE = MockCommunicate(50)
    FILES = ['foo']
    STATS = dict(foo=MockStatbuf(0))
    rv = slavedisk.main(stat=MockStat, print=MockPrint)

    self.assertEqual(rv, 0)
    self.assertNotIn("rm -rf /b/build/slave/foo # 30 days old", OUTPUT)

  def test_filematching(self):
    """Test the code that matches build directories."""
    global COMMUNICATE
    global FILES
    global STATS
    COMMUNICATE = MockCommunicate(100)
    FILES = ['invalid@name', 'not_a_dir', 'too_young']
    STATS = dict(not_a_dir=MockStatbuf(0, 0),
                 too_young=MockStatbuf(86400 * 30 - 1))
    rv = slavedisk.main(stat=MockStat, print=MockPrint)

    # None of the three files should be eligible for deletion;
    # the first has a bad name, the second isn't a directory,
    # and the third is too young.
    self.assertIn("nothing to delete", OUTPUT)
    self.assertEqual(rv, 1)


if __name__ == '__main__':
  unittest.TestCase.maxDiff = None
  unittest.main()
