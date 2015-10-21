# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This PollingChangeSource polls a Google Storage URL for change revisions.

Each change is submitted to change master which triggers build steps.

Notice that the gsutil configuration (.boto file) must be setup in either the
default location (home dir) or by using the environment variables
AWS_CREDENTIAL_FILE and BOTO_CONFIG.

Example:
To poll a change in Chromium build snapshots, use -
from master import gsurl_poller
changeurl = 'gs://chromium-browser-snapshots/Linux/LAST_CHANGE'
poller = gsurl_poller.GSURLPoller(changeurl=changeurl, pollInterval=10800)
c['change_source'] = [poller]
"""

import os, sys
import gcs_oauth2_boto_plugin
import StringIO
from boto import boto
from twisted.python import log
from twisted.internet import defer, utils
from buildbot.schedulers.timed import Periodic

google_storage = 'gs'


class GSPeriodic(Periodic):
    def __init__(self, gs_bucket, gs_path, name_identifier, **kwargs):
        Periodic.__init__(self, **kwargs)
        self.last_change = None
        self.cachepath = self.name + '.cache'
        self.gs_bucket = gs_bucket 
        self.gs_path = gs_path
        self.name_identifier = name_identifier 
        if os.path.exists(self.cachepath):
            try:
                f = open(self.cachepath, "r")
                self.last_change = f.read().strip()
                log.msg("%s: Setting last_change to %s" % (self.name, self.last_change))
                f.close()
                # try writing it, too
                f = open(self.cachepath, "w")
                f.write(str(self.last_change))
                f.close()
            except:
                self.cachepath = None
                log.msg("%s: Cache file corrupt or unwriteable; skipping and not using" % self.name)
                log.err()

    def downloadImage(self, src_path, dst_path):
        log.msg("%s: downloadImage: from %s to %s" % (self.name, src_path, dst_path))
        src_uri = boto.storage_uri(self.gs_bucket + '/' + src_path, 'gs')
        object_contents = StringIO.StringIO()
        src_uri.get_key().get_file(object_contents)
        dst_uri = boto.storage_uri(dst_path, 'file')
        object_contents.seek(0)
        dst_uri.new_key().set_contents_from_file(object_contents)
        object_contents.close() 

    # return the latest complete build
    def findLatestBuild(self):
        bucket = boto.storage_uri(self.gs_bucket, 'gs').get_bucket()
        maxtime = None
        build_version = None
        last_modified_file = None
        for obj in bucket.list(self.gs_path):
            if (maxtime is None or maxtime < obj.last_modified) and (self.name_identifier in obj.name):
                maxtime = obj.last_modified
                last_modified_file = obj.name
        log.msg("findlatestbuild: %s %s" % (last_modified_file, maxtime))
        return last_modified_file
       
    def startBuild(self):
        last_modified_file = self.findLatestBuild()
        if last_modified_file is not None:
            # file path: "builds/[builder_name]/[build_version]/[random_hash]/[binary].zip"
            new_change = last_modified_file.split('/')[2]
            if new_change != self.last_change:
                dst_path = os.path.join(os.getcwd(), 'images', self.name, os.path.basename(last_modified_file))
                self.downloadImage(last_modified_file, dst_path)
                log.msg("%s: Last change set from %s to %s; start build." %
                       (self.name, self.last_change, new_change))
                self.last_change = new_change 
                if self.cachepath:
                    f = open(self.cachepath, "w")
                    f.write(str(self.last_change))
                    f.close()
                self.properties.setProperty('got_revision', new_change, 'Scheduler')
                self.properties.setProperty('git_branch', self.branch, 'Scheduler')
                self.properties.setProperty('image', dst_path, 'Scheduler')
                return Periodic.startBuild(self)
        log.msg("%s: Didn't find newer release; last build: %s; skipping build." % (self.name, self.last_change))
        return defer.succeed(None)

