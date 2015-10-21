#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ExceptionNofifier unittests."""

import unittest

import test_env  # pylint: disable=W0611,W0403

from buildbot.status import results
from master import exception_notifier


class BuildMock(object):
  # Silence Method could be a function: pylint: disable=R0201
  def getBuilder(self):
    return None


class ExceptionNotifierTest(unittest.TestCase):
  def test_mode_failing(self):
    notifier = exception_notifier.ExceptionNotifier(
        fromaddr='buildbot@test',
        mode='failing',
    )
    self.assertTrue(notifier)
    self.assertTrue(notifier.isMailNeeded(BuildMock(), results.EXCEPTION))
    self.assertTrue(notifier.isMailNeeded(BuildMock(), results.FAILURE))
    self.assertFalse(notifier.isMailNeeded(BuildMock(), results.SUCCESS))


if __name__ == '__main__':
  unittest.main()
