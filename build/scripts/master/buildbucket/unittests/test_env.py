# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to setup the environment to run unit tests.

Imports scripts/master/unittests/test_env.py
"""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(TESTS_DIR, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(BASE_DIR, 'scripts'))

import master.unittests.test_env
