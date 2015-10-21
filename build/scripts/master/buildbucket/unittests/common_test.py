#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for common module"""

import unittest

import test_env  # pylint: disable=W0611

from master.buildbucket import common


class CommonUnitTest(unittest.TestCase):
  def test_parse_info_property_succeed(self):
    value, expected = {'build': {'foo': 'bar'}}, {'build': {'foo': 'bar'}}
    self.assertDictEqual(common.parse_info_property(value), expected)

    value, expected = {'build': '{"foo": "bar"}'}, {'build': {'foo': 'bar'}}
    self.assertDictEqual(common.parse_info_property(value), expected)

    value, expected = '{"build": {"foo": "bar"}}', {'build': {'foo': 'bar'}}
    self.assertDictEqual(common.parse_info_property(value), expected)

  def test_parse_info_property_fail(self):
    value = 'invalid json'
    self.assertRaises(ValueError, lambda: common.parse_info_property(value))

    value = {'build': "invalid json"}
    self.assertRaises(ValueError, lambda: common.parse_info_property(value))

    value = '42'  # not a dict
    self.assertRaises(ValueError, lambda: common.parse_info_property(value))


if __name__ == '__main__':
  unittest.main()
