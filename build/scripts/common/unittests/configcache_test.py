#!/usr/bin/env python2.7
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test suite for common.configcache."""

import test_env
import unittest

import os
from common import configcache


class _TestFetcher(object):
  def __init__(self):
    self.return_data = None
    self.return_version = None
    self.call_args = None

  def __call__(self, name, version):
    self.call_args = (name, version)
    return self.return_data, self.return_version


class ConfigCacheTestCase(unittest.TestCase):
  def setUp(self):
    self.fetcher = _TestFetcher()
    self.cache = configcache.CacheManager(
        'test',
        cache_dir='cache',
        fetcher=self.fetcher)

    # Mock '_WriteFile'.
    self.mock_fs = {}
    def _MockWriteFile(path, data):
      return self._writeFile(path, data)
    def _MockReadFile(path):
      return self._readFile(path)
    self.cache._WriteFile = _MockWriteFile
    self.cache._ReadFile = _MockReadFile

  def _writeFile(self, path, data):
    self.mock_fs[path] = data

  def _readFile(self, path):
    data = self.mock_fs.get(path)
    if data is None:
      raise IOError("No file exists at: %s" % (path,))
    return data

  def assertWroteFile(self, data, *path):
    try:
      file_data = self._readFile(os.path.join(*path))
    except IOError:
      self.fail("File '%s' was not written." % (path,))
    self.assertEqual(data, file_data)

  def testFetchAndCache(self):
    self.fetcher.return_data = 'bar'
    self.fetcher.return_version = 'v1'
    data, version = self.cache.FetchAndCache('foo', 'v1')

    self.assertEqual(self.fetcher.call_args, ('foo', 'v1'))
    self.assertEqual(data, 'bar')
    self.assertEqual(version, 'v1')
    self.assertWroteFile('bar', 'cache', 'test', 'foo.data')
    self.assertWroteFile('v1', 'cache', 'test', 'foo.version')

  def testFetchReturnsWrongVersionRaisesValueError(self):
    self.fetcher.return_data = 'bar'
    self.fetcher.return_version = 'v2'
    self.assertRaises(ValueError, self.cache.FetchAndCache, 'foo', 'v1')

  def testGetArtifactVersion(self):
    self.fetcher.return_data = 'bar'
    self.fetcher.return_version = 'v1'
    self.cache.FetchAndCache('foo', 'v1')
    self.assertEqual(self.cache.GetArtifactVersion('foo'), 'v1')

  def testGetArtifactData(self):
    self.fetcher.return_data = 'bar'
    self.fetcher.return_version = 'v1'
    self.cache.FetchAndCache('foo')
    self.assertEqual(self.cache.Get('foo'), 'bar')

  def testGetMissingArtifactData(self):
    self.assertEqual(self.cache.Get('foo'), None)

  def testGetArtifactWrongVersion(self):
    self.fetcher.return_data = 'bar'
    self.fetcher.return_version = 'v1'
    self.cache.FetchAndCache('foo', 'v1')
    self.assertEqual(self.cache.Get('foo', version='v2'), None)

  def testUpdateArtifactVersio(self):
    self.fetcher.return_data = 'bar'
    self.fetcher.return_version = 'v1'
    self.cache.FetchAndCache('foo', 'v1')
    self.assertEqual(self.cache.GetArtifactVersion('foo'), 'v1')

    self.fetcher.return_version = 'v2'
    self.cache.FetchAndCache('foo', 'v2')
    self.assertEqual(self.cache.GetArtifactVersion('foo'), 'v2')


if __name__ == '__main__':
  unittest.main()
