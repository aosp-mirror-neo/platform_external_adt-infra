# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe for emulator boot tests."""

from recipe_engine.types import freeze
import os
import platform

DEPS = [
    'path',
    'properties',
    'python',
    'raw_io',
    'step',
]

MASTER_USER = 'user'
MASTER_IP = '172.27.213.40'

def RunSteps(api):
  buildername = api.properties['buildername']
  image_file_path = api.properties['image']
  image_filename = image_file_path[(image_file_path.rfind('/') + 1):]

  download_path = api.path['slave_build'].join('')
  remote_path = '%s@%s:%s' % (MASTER_USER, MASTER_IP, image_file_path)

  local_zipfile = download_path.join(image_filename)
  emulator_path = download_path.join('tools', 'emulator')

  env_path = ['%(PATH)s']

  # find android sdk root directory
  home_dir = os.path.expanduser('~')
  host = platform.system()
  if host == "Darwin":
    android_sdk_home = os.path.join(home_dir, 'Android/android-sdk-macosx')
  elif host == "Linux":
    android_sdk_home = os.path.join(home_dir, 'Android/android-sdk-linux')
  # On windows, we need cygwin and GnuWin for commands like, rm, scp, unzip
  elif host == "Windows":
    if 'x86' in os.environ['PROGRAMFILES']:
      android_sdk_home = 'C:\\Program Files (x86)\\Android\\android-sdk'
      gnu_path = 'C:\\Program Files (x86)\\GnuWin32\\bin'
      cygwin_path = 'C:\\cygwin64\\bin'
    else:
      android_sdk_home = 'C:\\Program Files\\Android\\android-sdk'
      gnu_path = 'C:\\Program Files\\GnuWin32\\bin'
      cygwin_path = 'C:\\cygwin\\bin'
    env_path = [gnu_path, cygwin_path] + env_path
  else:
    raise

  android_tools_dir = os.path.join(android_sdk_home, 'tools')
  android_platform_dir = os.path.join(android_sdk_home, 'platform-tools')
  env_path += [android_tools_dir, android_platform_dir]
  env = {'PATH': api.path.pathsep.join(env_path),
         'ANDROID_SDK_ROOT': android_sdk_home}

  # Find emulator script based on current location
  # Current directory should be [project root]/build/scripts/slave/recipes/[recipeName]/
  # Emulator scripts are located [project root]/emu_test
  build_dir = api.path['build']
  script_root = api.path.join(build_dir, os.pardir, 'emu_test')
  dotest_path = api.path.join(script_root, 'dotest.py')

  api.step('Clean slave build directory',
           ['find', '.', '-delete'],
           env=env)
  api.step('Download Image',
           ['scp', remote_path,
           '.'],
           env=env)
  api.step('Unzip Image File',
           ['unzip', local_zipfile],
           env=env)
  with api.step.defer_results():
    deferred_step_result = api.python('Run Emulator Boot Test', dotest_path,
                                      ['-l', 'INFO', '-exec', emulator_path,
                                       '-p', 'test_boot.*', '-c',
                                       api.path.join(script_root, 'config',
                                                     'boot_cfg.csv'), '-n',
                                       buildername],
                                      env=env, stderr=api.raw_io.output('err'))
    if not deferred_step_result.is_ok:
      stderr_output = deferred_step_result.get_error().result.stderr
      print stderr_output
      lines = ['%s: %s' % (line[0:line.index(':')], line[line.rfind('.')+1:])
               for line in stderr_output.split('\n')
               if line.startswith('FAIL:') or line.startswith('TIMEOUT:')]
      for line in lines:
        api.step.active_result.presentation.logs[line] = ''
    else:
      print deferred_step_result.get_result().stderr

    deferred_step_result = api.python('Run Emulator CTS Test', dotest_path,
                                      ['-l', 'INFO', '-exec', emulator_path,
                                       '-p', 'test_cts.*', '-c',
                                       api.path.join(script_root, 'config',
                                                     'cts_cfg.csv'),
                                       '-n', buildername],
                                      env=env, stderr=api.raw_io.output('err'))
    if not deferred_step_result.is_ok:
      stderr_output = deferred_step_result.get_error().result.stderr
      print stderr_output
      lines = [line for line in stderr_output.split('\n')
               if line.startswith('FAIL:') or line.startswith('TIMEOUT:')]
      for line in lines:
        api.step.active_result.presentation.logs[line] = ''
    else:
      print deferred_step_result.get_result().stderr


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
