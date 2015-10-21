# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Launches emulator CTS tests."""

from recipe_engine.types import freeze

DEPS = [
    'bot_update',
    'gclient',
    'path',
    'properties',
    'python',
    'step',
    'zip',
]

MASTER_USER = 'user'
MASTER_IP = '172.27.213.40'

def RunSteps(api):
  api.gclient.set_config('chromium')
  # api.bot_update.ensure_checkout(force=True)

  buildername = api.properties['buildername']
  image_file_path = api.properties['image']
  image_filename = image_file_path[(image_file_path.rfind('/') + 1):]

  download_path = api.path['slave_build'].join('')
  remote_path = '%s@%s:%s' % (MASTER_USER, MASTER_IP, image_file_path)

  api.step('Clean slave build directory', ['rm', '-rf', download_path.join('tools')])
  #api.step('Clean slave build directory', ['rm', '-rf', download_path.join('*')])
  api.step('Download Image', ['scp', remote_path, download_path])
  local_zipfile = download_path.join(image_filename)
  api.step('Unzip Image File', ['unzip', local_zipfile])

  dotest_path = '/home/adt_build/Buildbot/emu_scripts/dotest.py'
  emulator_path = download_path.join('tools', 'emulator')
  android_path = '/home/adt_build/Android/android-sdk-linux/tools/'
  android_platform_path = '/home/adt_build/Android/android-sdk-linux/platform-tools/'
  env = {'PATH': api.path.pathsep.join([android_path, android_platform_path, '%(PATH)s'])}
  api.python('Run Emulator Tests', dotest_path,
             ['-l', 'INFO', '-exec', emulator_path], env=env)


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties(
      mastername='client.adt',
      buildername='Win 7 64-bit HD 4400',
      image='/usr/local/google/code/adt_buildbot_repo/external/adt-infra/build/masters/'
            'master.client.adt/images/emu_gspoller_windows/sdk-repo-windows-tools-2344972.zip',
    )
  )
