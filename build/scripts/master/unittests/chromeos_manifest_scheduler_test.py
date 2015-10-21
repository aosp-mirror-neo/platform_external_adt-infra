#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Source file for chromium_step testcases."""

import re
import unittest

import test_env  # pylint: disable=W0611,W0403

import buildbot.changes.filter
from master import chromeos_manifest_scheduler


class FilterNewSpecProviderTest(unittest.TestCase):
  """Tests FilterNewSpecProvider class.

  When tested commit lines originate from the actual manifest-versions
  repository (https://chromium.googlesource.com/chromiumos/manifest-versions),
  the corresponding commit hash is noted.
  """

  def _matchesLines(self, builder, branch, *lines):
    fns = chromeos_manifest_scheduler.FilterNewSpecProvider(
        None, builder, branch)
    return fns._CheckCommitLines(*lines)

  def _assertMatches(self, builder, branch, *lines):
    self.assertTrue(self._matchesLines(builder, branch, *lines),
        "Lines didn't match builder '%s', branch '%s', but should: %s" % (
            builder, branch, lines))

  def _assertNotMatches(self, builder, branch, *lines):
    self.assertFalse(self._matchesLines(builder, branch, *lines),
        "Lines match builder '%s', branch '%s', but shouldn't: %s" % (
            builder, branch, lines))

  def testCommitMultiLineMatching(self):
    # 3a1ee22ef3b9a41652ab1051877573b70ad2b23f
    line = ('Automatic: Start lumpy-pre-flight-branch release-R42-6812.B '
            '6812.62.0-rc2')

    # Single line.
    self._assertMatches('lumpy-pre-flight-branch', 'release-R42-6812.B', line)

    # With prefix/suffix lines.
    self._assertMatches('lumpy-pre-flight-branch', 'release-R42-6812.B',
          'Prefix', '', line, 'suffix')


  def testCommitLineMatching(self):
    # 3a1ee22ef3b9a41652ab1051877573b70ad2b23f
    self._assertMatches('lumpy-pre-flight-branch', 'release-R42-6812.B',
        ('Automatic: Start lumpy-pre-flight-branch release-R42-6812.B '
         '6812.62.0-rc2'))

    # 3a1ee22ef3b9a41652ab1051877573b70ad2b23f (regex)
    self._assertMatches('lumpy-pre-flight-branch', re.compile(r'.+-6812.*\.B'),
        ('Automatic: Start lumpy-pre-flight-branch release-R42-6812.B '
         '6812.62.0-rc2'))

    # 963c69bb1a2561f3b8e1a76688ad98c55b853acd
    self._assertMatches('master-chromium-pfq', 'master',
        'Automatic: Start master-chromium-pfq master 6941.0.0-rc1')

    # 963c69bb1a2561f3b8e1a76688ad98c55b853acd
    self._assertNotMatches('lumpy-pre-flight-branch', 'master',
        'Automatic: Start master-chromium-pfq master 6941.0.0-rc1')

    # 963c69bb1a2561f3b8e1a76688ad98c55b853acd
    self._assertNotMatches('master-chromium-pfq', 'release-R42-6812.B',
        'Automatic: Start master-chromium-pfq master 6941.0.0-rc1')

    self._assertNotMatches('builder', 'branch', 'Some other lines...')


class FilterNewSpecTest(unittest.TestCase):

  def testFilterNewSpecReturnsChangeFilter(self):
    self.assertIsInstance(
        chromeos_manifest_scheduler.FilterNewSpec(None, 'builder', 'branch'),
        buildbot.changes.filter.ChangeFilter)


if __name__ == '__main__':
  unittest.main()
