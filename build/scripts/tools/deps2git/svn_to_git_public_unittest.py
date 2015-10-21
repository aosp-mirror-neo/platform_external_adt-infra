#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import svn_to_git_public


class SvnUrlToGitUrlTest(unittest.TestCase):
  def testWebRtcUrls(self):
    expected = {
      'deps/third_party/foo': 'external/webrtc/deps/third_party/foo',
      'trunk': 'external/webrtc',
      'trunk/bar': 'external/webrtc/trunk/bar',
    }
    svn_base_url = 'https://webrtc.googlecode.com/svn'

    path = 'just/some/path'
    for k, v in expected.iteritems():
      res = svn_to_git_public.SvnUrlToGitUrl(path, '%s/%s' % (svn_base_url, k))
      self.assertEqual(res[0], path)
      self.assertEqual(res[1], '%s%s.git' % (svn_to_git_public.GIT_HOST, v))

if __name__ == '__main__':
  unittest.main()
