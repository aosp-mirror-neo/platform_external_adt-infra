#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import subprocess
import sys
import tempfile


GCLIENT_CONFIG = """solutions = [
  {
    "name"      : "master.DEPS",
    "url"       : "https://chrome-internal.googlesource.com/chrome/tools/build/master.DEPS.git",
    "deps_file" : ".DEPS.git",
    "managed"   : True,
  },
]"""


def check_call(cmd, cwd=None):
  print 'Running %s%s' % (cmd, ' in %s' % cwd if cwd else '')
  subprocess.check_call(cmd, cwd=cwd)


def check_output(cmd, cwd=None):
  print 'Running %s%s' % (cmd, ' in %s' % cwd if cwd else '')
  return subprocess.check_output(cmd, cwd=cwd)


def main():
  home_dir = os.path.realpath(os.path.expanduser('~'))
  buildbot_dir = os.path.join(home_dir, 'buildbot')

  # Sanity check that buildbot directory is correctly found.
  assert os.path.isdir(buildbot_dir)

  tmpdir = tempfile.mkdtemp(dir=os.path.realpath(buildbot_dir),
                            prefix='master_svn_to_git')
  try:
    # Create new temp Git checkout.
    with open(os.path.join(tmpdir, '.gclient'), 'w') as gclient_file:
      gclient_file.write(GCLIENT_CONFIG)

    # Sync both repos (SVN first since mirroring happens from SVN to Git).
    check_call(['gclient', 'sync'], cwd=buildbot_dir)
    check_call(['gclient', 'sync'], cwd=tmpdir)

    # Find repositories handled by gclient.
    revinfo = check_output(['gclient', 'revinfo'], cwd=tmpdir)
    repos = {}
    for line in revinfo.splitlines():
      relpath, repospec = line.split(':', 1)
      repos[relpath.strip()] = repospec.strip()

    # Sanity checks.
    for relpath in sorted(repos):
      # Only process directories that have .svn dir in them.
      if not os.path.isdir(os.path.join(buildbot_dir, relpath, '.svn')):
        print '%s subdir does not have .svn directory' % relpath
        del repos[relpath]
        continue
      # Make sure Git directory exists.
      assert os.path.isdir(os.path.join(tmpdir, relpath, '.git'))
      # Make sure there are no local modifications.
      assert check_output(
          ['svn', 'diff'], cwd=os.path.join(buildbot_dir, relpath)) == ''

    # Move SVN .gclient away so that no one can run gclient sync while
    # conversion is in progress.
    print 'Moving .gclient to .gclient.svn in %s' % buildbot_dir
    shutil.move(os.path.join(buildbot_dir, '.gclient'),
                os.path.join(buildbot_dir, '.gclient.svn'))

    # Rename all .svn directories into .svn.backup.
    svn_dirs = []
    count = 0
    print 'Searching for .svn folders'
    for root, dirs, _files in os.walk(buildbot_dir):
      count += 1
      if count % 1000 == 0:
        print 'Processed %d directories' % count
      if '.svn' in dirs:
        svn_dirs.append(os.path.join(root, '.svn'))
        dirs.remove('.svn')
    for rel_svn_dir in svn_dirs:
      svn_dir = os.path.join(buildbot_dir, rel_svn_dir)
      print 'Moving %s to %s.backup' % (svn_dir, svn_dir)
      shutil.move(svn_dir, '%s.backup' % svn_dir)


    # Move Git directories from temp dir to the checkout.
    for relpath, repospec in sorted(repos.iteritems()):
      src_git = os.path.join(tmpdir, relpath, '.git')
      dest_git = os.path.join(buildbot_dir, relpath, '.git')
      print 'Moving %s to %s' % (src_git, dest_git)
      shutil.move(src_git, dest_git)
  finally:
    shutil.rmtree(tmpdir)

  # Update .gclient file to reference Git DEPS.
  with open(os.path.join(buildbot_dir, '.gclient'), 'w') as gclient_file:
    gclient_file.write(GCLIENT_CONFIG)

  # Reset changes to known troublesome files (CRLF/LF changes).
  crlf_fix_files = [
      'third_party/buildbot_8_4p1/contrib/windows/buildbot.bat',
      'third_party/buildbot_slave_8_4/contrib/windows/buildslave.bat',
      'third_party/sqlalchemy_migrate_0_7_1/migrate/tests/fixture/warnings.py']
  for file_path in crlf_fix_files:
    check_call(['git', 'checkout', file_path],
               cwd=os.path.join(buildbot_dir, 'build'))

  # Run gclient sync again.
  check_call(['gclient', 'sync'], cwd=buildbot_dir)


if __name__ == '__main__':
  sys.exit(main())
