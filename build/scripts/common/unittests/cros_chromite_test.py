#!/usr/bin/env python2.7
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test suite for common.cros_chromite."""

import test_env

import base64
import json
import unittest

from common import cros_chromite


class MockConfigCache(object):
  def __init__(self, data):
    self.data = data

  def Get(self, name, version=None):
    return self.data.get((name, version))


class ChromiteConfigTestCase(unittest.TestCase):


  CHROMITE_CONFIG = {
    '_default': {
      'foo': 'bar',
      'key': 'value',
      'hw_tests': [
        'default0',
        'default1',
      ],
    },
    '_templates': {
      'no-hwtest-pre-cq': {
        'hw_tests': [
        ],
      },
    },
    'test': {
      'foo': 'baz',
    },
    'no-hwtest-pre-cq': {
      '_template': 'no-hwtest-pre-cq',
      'name': 'no-hwtest-pre-cq',
    },
    'parent': {
      'name': 'parent',
      'child_configs': [
        {
          'name': 'alice',
          'vm_tests': [
            'test',
          ],
          'hw_tests': [
            'test',
          ],
          'unittests': True,
        },
        {'name': 'bob'}
      ],
    },
    'parent-template': {
      'name': 'parent-template',
      'hw_tests': [],
      'child_configs': [
        {
          '_template': 'no-hwtest-pre-cq',
          'name': 'joe',
        }
      ],
    },
    'baremetal-pre-cq': {
      'vm_tests': [
        'test',
      ],
      'hw_tests': [
        'test',
      ],
      'unittests': True,
    },
    'pre-cq-group': {},
    'master-thing': {
      'master': True,
    },
  }

  def setUp(self):
    self.config = cros_chromite.ChromiteConfig.FromConfigDict(
        self.CHROMITE_CONFIG)
    self.test = self.config['test']
    self.no_hwtest_pre_cq = self.config['no-hwtest-pre-cq']
    self.parent = self.config['parent']
    self.parent_template = self.config['parent-template']
    self.baremetal = self.config['baremetal-pre-cq']

  def testChildren(self):
    self.assertEqual(len(self.test.children), 0)
    self.assertEqual(len(self.parent.children), 2)
    self.assertEqual(self.parent.children[0]['name'], 'alice')
    self.assertEqual(self.parent.children[1]['name'], 'bob')

  def testDefaultFallthrough_UsesLocalWhenAvailable(self):
    self.assertEqual(self.test['foo'], 'baz')

  def testDefaultFallthrough_UsesDefaultWhenMissing(self):
    self.assertEqual(self.test['key'], 'value')

  def testDefaultFallthrough_ParentUsesDefaults(self):
    self.assertEqual(self.parent['hw_tests'], ['default0', 'default1'])

  def testHasTests(self):
    self.assertFalse(self.test.HasVmTests())
    self.assertTrue(self.test.HasHwTests())
    self.assertFalse(self.no_hwtest_pre_cq.HasHwTests())
    self.assertFalse(self.test.HasUnitTests())

    self.assertTrue(self.baremetal.HasVmTests())
    self.assertTrue(self.baremetal.HasHwTests())
    self.assertTrue(self.baremetal.HasUnitTests())

  def testHasTests_DetectsInChildren(self):
    self.assertTrue(self.parent.HasVmTests())
    self.assertTrue(self.parent.HasHwTests())
    self.assertFalse(self.parent_template.HasHwTests())
    self.assertTrue(self.baremetal.HasUnitTests())

  def testPreCqDetection(self):
    self.assertFalse(self.test.IsPreCqBuilder())

    self.assertTrue(self.baremetal.IsPreCqBuilder())
    self.assertFalse(self.baremetal.IsGeneralPreCqBuilder())

    pre_cq_group = self.config['pre-cq-group']
    self.assertTrue(pre_cq_group.IsPreCqBuilder())
    self.assertTrue(pre_cq_group.IsGeneralPreCqBuilder())

  def testIsMaster(self):
    self.assertTrue(self.config['master-thing'].is_master)

  def testCategorize(self):
    # Type-based: name, build_type => base, suffix, category
    expectations = (
    )
    # Name-based: name => base, suffix, category
    expectations = (
      # (With Board Type)
      ('pre-cq-launcher', 'priest', 'pre-cq-launcher', None, 'PRE_CQ_LAUNCHER'),
      # The canary board type should override the name-based inferences,
      # marking this board as a canary.
      ('odd-name-paladin', 'canary', 'odd-name-paladin', None, 'CANARY'),

      ('my-board-asan', None, 'my-board', 'asan', 'ASAN'),
      ('my-board-pre-cq', None, 'my-board', 'pre-cq', 'PRE_CQ'),
      ('my-board-chrome-pfq', None, 'my-board', 'chrome-pfq', 'PFQ'),
      ('my-board-chromium-pfq', None, 'my-board', 'chromium-pfq', 'PFQ'),
      ('my-board-paladin', None, 'my-board', 'paladin', 'PALADIN'),
      ('my-board-release', None, 'my-board', 'release', 'CANARY'),
      ('my-board-release-group', None, 'my-board', 'release-group', 'CANARY'),
      ('my-board-firmware', None, 'my-board', 'firmware', 'FIRMWARE'),
      ('my-board-incremental', None, 'my-board', 'incremental', 'INCREMENTAL'),
      ('my-board-factory', None, 'my-board', 'factory', 'FACTORY'),
      ('my-board-project-sdk', None, 'my-board-project', 'sdk', 'SDK'),
      ('my-board-toolchain-major', None,
          'my-board', 'toolchain-major', 'TOOLCHAIN'),
      ('my-board-toolchain-minor', None,
          'my-board', 'toolchain-minor', 'TOOLCHAIN'),
    )

    for name, build_type, exp_base, exp_suffix, exp_cat_attr in expectations:
      exp_category = getattr(cros_chromite.ChromiteTarget, exp_cat_attr)
      base, suffix, category = cros_chromite.ChromiteTarget.Categorize(
          name,
          build_type=build_type)
      self.assertEqual(
          (base, suffix, category), (exp_base, exp_suffix, exp_category))


class ChromitePinManagerTestCase(unittest.TestCase):

  def testGetPinnedBranch_PinnedBranchReturnsPinnedValue(self):
    pm = cros_chromite.ChromitePinManager(pinned={'a': 'b'}, require=True)
    self.assertEqual(pm.GetPinnedBranch('a'), 'b')

  def testGetPinnedBranch_UnpinnedBranchReturnsBranch(self):
    pm = cros_chromite.ChromitePinManager(pinned={'a': 'b'}, require=False)
    self.assertEqual(pm.GetPinnedBranch('foo'), 'foo')

  def testGetPinnedBranch_UnpinnedBranchReturnsErrorWithRequiredPinning(self):
    pm = cros_chromite.ChromitePinManager(pinned={'a': 'b'}, require=True)
    self.assertRaises(cros_chromite.ChromiteError,
        pm.GetPinnedBranch, 'foo')


class ChromiteConfigManagerTestCase(unittest.TestCase):

  def setUp(self):
    self.cache = MockConfigCache({
      ('test', 'v1'): '{}',
      ('test', 'v_invalid'): '{NOT JSON}',
    })

  def testGetConfig_ValidSucceeds(self):
    manager = cros_chromite.ChromiteConfigManager(self.cache,
        cros_chromite.ChromitePinManager({'test': 'v1'}))
    self.assertTrue(isinstance(manager.GetConfig('test'),
        cros_chromite.ChromiteConfig))

  def testGetConfig_InvalidJsonRaises(self):
    manager = cros_chromite.ChromiteConfigManager(self.cache,
        cros_chromite.ChromitePinManager({'test': 'v_invalid'}))
    self.assertRaises(cros_chromite.ChromiteError, manager.GetConfig, 'test')

  def testGetConfig_MissingRaises(self):
    manager = cros_chromite.ChromiteConfigManager(self.cache)
    self.assertRaises(cros_chromite.ChromiteError, manager.GetConfig, 'foo')


class ChromiteFetcherTestCase(unittest.TestCase):

  def setUp(self):
    self.fetcher = cros_chromite.ChromiteFetcher(
        cros_chromite.ChromitePinManager({'test': 'v1'})
    )

  @staticmethod
  def _configUrlForBranch(branch):
    return '%s/+/%s/%s?format=text' % (
        cros_chromite.ChromiteFetcher.CHROMITE_GITILES_BASE,
        branch,
        cros_chromite.ChromiteFetcher.CHROMITE_CONFIG_PATH,
    )

  def testFetch_Valid(self):
    fetched_urls = []
    def _MockGetText(url):
      fetched_urls.append(url)
      return base64.b64encode('content')
    self.fetcher._GetText = _MockGetText

    data = self.fetcher('test', None)
    self.assertEqual(data, ('content', 'v1'))
    self.assertEqual(fetched_urls, [self._configUrlForBranch('v1')])

  def testFetch_NotBase64(self):
    def _MockGetText(_url):
      return 'Not Valid Base64'
    self.fetcher._GetText = _MockGetText
    self.assertRaises(cros_chromite.GitilesError, self.fetcher, 'test', None)


if __name__ == '__main__':
  unittest.main()
