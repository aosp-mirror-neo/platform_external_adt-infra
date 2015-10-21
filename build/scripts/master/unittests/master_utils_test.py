#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Source file for master_utils testcases."""


import unittest

import test_env  # pylint: disable=W0611,W0403

from buildbot.process.properties import Properties
from master import master_utils


class MasterUtilsTest(unittest.TestCase):

  def testPartition(self):
    partitions = master_utils.Partition([(1, 'a'),
                                         (2, 'b'),
                                         (3, 'c'),
                                         ], 2)
    self.assertEquals([['a', 'b'], ['c']], partitions)


class MockBuilder(object):
  def __init__(self, name):
    self.name = name

class MockSlave(object):
  def __init__(self, name, properties):
    self.properties = Properties()
    self.properties.update(properties, "BuildSlave")
    self.properties.setProperty("slavename", name, "BuildSlave")

class MockSlaveBuilder(object):
  def __init__(self, name, properties):
    self.name = name
    self.slave = MockSlave(name, properties)

class PreferredBuilderNextSlaveFuncTest(unittest.TestCase):
  def testNextSlave(self):
    builder1 = MockBuilder('builder1')
    builder2 = MockBuilder('builder2')
    builder3 = MockBuilder('builder3')

    slaves = [
        MockSlaveBuilder('slave1', {'preferred_builder': 'builder1'}),
        MockSlaveBuilder('slave2', {'preferred_builder': 'builder2'}),
        MockSlaveBuilder('slave3', {'preferred_builder': 'builder3'}),
    ]

    f = master_utils.PreferredBuilderNextSlaveFunc()
    self.assertEqual('slave1', f(builder1, slaves).name)
    self.assertEqual('slave2', f(builder2, slaves).name)
    self.assertEqual('slave3', f(builder3, slaves).name)

    # Remove slave 3.
    del slaves[2]

    # When there is no slave that matches preferred_builder,
    # any slave builder might be chosen.
    self.assertTrue(f(builder3, slaves).name in ['slave1', 'slave2'])

  def testNextSlaveEmpty(self):
    builder = MockBuilder('builder')
    slaves = []

    f = master_utils.PreferredBuilderNextSlaveFunc()

    self.assertIsNone(f(builder, slaves))


if __name__ == '__main__':
  unittest.main()
