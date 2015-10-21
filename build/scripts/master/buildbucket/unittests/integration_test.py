#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Buildbucket integration unit tests"""

import contextlib
import datetime
import httplib
import json
import logging
import sys
import threading
import time
import traceback
import unittest

import test_env  # pylint: disable=W0611

from buildbot.status import builder as build_results
from master.buildbucket import common, integration
from master.unittests.deferred_resource_test import run_deferred
from mock import Mock, call, ANY
from twisted.internet import defer, reactor
import apiclient


BUCKET = 'chromium'
BUILDSET = 'patch/rietveld/codereview.chromium.org/1/2'
BUILDSET_TAG = 'buildset:%s' % BUILDSET
LEASE_KEY = 42


def fake_buildbot(one_slave=False):
  buildbot = Mock()

  # Slaves
  buildbot.get_connected_slaves.return_value = [buildbot.slave]
  if not one_slave:
    buildbot.get_connected_slaves.return_value.append(buildbot.slave2)

  # Builders
  builders = {
      'Debug': Mock(),
      'Release': Mock(),
  }
  buildbot.get_builders.return_value = builders

  # Build requests.
  build_requests = []
  buildbot.get_incomplete_build_requests.return_value = build_requests
  def add_build_request(*_, **__):
    req = Mock()
    build_requests.append(req)
    return req
  buildbot.add_build_request.side_effect = add_build_request

  return buildbot


def fake_buildbucket():
  service = Mock()
  def lease(id, body):  # pylint: disable=W0622
    return {
        'build': {
            'lease_key': LEASE_KEY,
            'lease_expiration_ts': body['lease_expiration_ts'],
        }
    }
  service.api.lease.side_effect = lease
  service.api.heartbeat_batch.side_effect = lambda *_, **__: defer.succeed({})

  return service


class IntegratorTest(unittest.TestCase):
  ssid = 1
  buckets = [BUCKET]
  integrator = None
  buildbot = None
  buildbucket = None
  buildbucket_change = {
      'id': '1',
      'author': {'email': 'johndoe@chromium.org'},
      'message': 'hello world',
      'revision': 'deadbeef',
      'branch': 'master',
      'create_ts': 1419984000000000,  # 2014-11-31
      'project': 'chromium',
      'repoUrl': 'http://chromium.googlesource.com/chromium/src'
  }
  buildbucket_build_rel = {
      'id': '1',
      'bucket': BUCKET,
      'tags': [BUILDSET_TAG],
      'parameters_json': json.dumps({
            'builder_name': 'Release',
            'changes': [buildbucket_change],
      }),
  }
  buildbucket_build_dbg = {
      'id': '2',
      'bucket': BUCKET,
      'tags': [BUILDSET_TAG],
      'parameters_json': json.dumps({
            'builder_name': 'Debug',
            'changes': [buildbucket_change],
      }),
  }

  def setUp(self):
    super(IntegratorTest, self).setUp()
    self.changes = Mock()
    self.changes.get_source_stamp.return_value = self.ssid

  @contextlib.contextmanager
  def create_integrator(self, buildbot=None, max_lease_count=None,
                        build_params_hook=None):
    self.buildbucket = fake_buildbucket()
    self.buildbot = buildbot or fake_buildbot()
    self.integrator = integration.BuildBucketIntegrator(
        self.buckets, max_lease_count=max_lease_count,
        build_params_hook=build_params_hook,
        heartbeat_interval=datetime.timedelta(microseconds=1))
    def log(msg, level=logging.INFO):
      logging.log(level, msg)
    self.integrator.log = log
    self.integrator.start(
        self.buildbot, self.buildbucket,
        change_store_factory=lambda bb: self.changes)
    try:
      yield
    finally:
      self.integrator.stop()

  def test_no_builds(self):
    with self.create_integrator():
      self.buildbucket.api.peek.return_value = {'builds': []}
      run_deferred(self.integrator.poll_builds())
      self.assertFalse(self.buildbot.add_build_request.called)
      self.assertTrue(self.buildbucket.api.peek.called)
      self.assertFalse(self.buildbucket.api.lease.called)

  def test_error_in_peek_response(self):
    with self.create_integrator():
      self.buildbucket.api.peek.return_value = {
          'error': {
              'reason': 'PROBLEM',
              'message': 'Something is bad',
          }
      }
      run_deferred(self.integrator.poll_builds())
      self.assertFalse(self.buildbucket.api.lease.called)

  def test_build_was_not_leased(self):
    with self.create_integrator(), self.mock_build_peek():
      self.buildbucket.api.lease.return_value = {
          'error': {
              'reason': 'CANNOT_LEASE_BUILD',
              'message': 'Sorry',
          }
      }
      self.buildbucket.api.lease.side_effect = None
      run_deferred(self.integrator.poll_builds())
      self.assertFalse(self.buildbot.add_build_request.called)

  @contextlib.contextmanager
  def mock_build_peek(self, lease=True):
    """Mocks buildbucket.peek API call."""
    self.buildbucket.api.peek.return_value = {
        'builds': [self.buildbucket_build_rel, self.buildbucket_build_dbg],
    }
    yield
    self.assertTrue(
        self.buildbucket.api.peek.called, 'build.peek was not called')

  def assert_added_build_request(
      self, build_id, builder_name, ssid, properties=None, buildset=None):
    properties = (properties or {}).copy()
    properties['buildbucket'] = ANY
    properties = {
        k: (v, 'buildbucket') for k, v in properties.iteritems()
    }

    self.integrator.buildbot.add_build_request.assert_any_call(
        ssid=ssid,
        reason=common.CHANGE_REASON,
        builder_name=builder_name,
        properties_with_source=properties,
        external_idstring=build_id,
    )

  def assert_buildbucket_lease_was_called(self, build_id):
    for _, kwargs in self.buildbucket.api.lease.call_args_list:
      if kwargs['id'] == build_id:
        return
    self.fail('Build %s was not leased' % build_id)

  def assert_leased(self, build_id):
    self.assertTrue(build_id in self.integrator._leases)
    self.assertTrue(self.integrator._leases[build_id]['key'] == LEASE_KEY)
    self.assert_buildbucket_lease_was_called(build_id)

  def test_minimalistic_build(self):
    with self.create_integrator():
      self.buildbucket.api.peek.return_value = {
          'builds': [{
              'id': '1',
              'bucket': BUCKET,
              'parameters_json': json.dumps({
                    'builder_name': 'Release',
              }),
          }],
      }

      run_deferred(self.integrator.poll_builds())

      self.assert_leased('1')
      self.assert_added_build_request('1', 'Release', self.ssid)

  def test_invalid_build_def(self):
    with self.create_integrator():
      self.buildbucket.api.peek.return_value = {
          'builds': [{
              'id': '1',
          }],
      }

      run_deferred(self.integrator.poll_builds())

      self.assert_buildbucket_lease_was_called('1')
      self.buildbucket.api.fail.assert_called_once_with(
          id='1',
          body={
              'lease_key': LEASE_KEY,
              'failure_reason': 'INVALID_BUILD_DEFINITION',
              'result_details_json': json.dumps({
                  'error': {
                      'message': (
                          'Build parameters (parameters_json) are not set'),
                  }
              }, sort_keys=True)
          })
      self.assertFalse(self.buildbot.add_build_request.called)

  def test_build_with_properties(self):
    with self.create_integrator():
      self.buildbucket.api.peek.return_value = {
          'builds': [{
              'id': '1',
              'bucket': BUCKET,
              'parameters_json': json.dumps({
                    'builder_name': 'Release',
                    'properties': {
                        'a': 'b',
                    }
              }),
          }],
      }

      run_deferred(self.integrator.poll_builds())

      self.assert_leased('1')
      self.assert_added_build_request(
          '1', 'Release', self.ssid, properties={'a': 'b'})

  def test_build_with_properties_hook(self):
    def hook(params, build):
      build['bucket'] = 'INVALID'
      params['builder_name'] = 'Debug'
      params['properties']['foo'] = 'bar'

    build = {
        'id': '1',
        'bucket': BUCKET,
        'parameters_json': json.dumps({
              'builder_name': 'Release',
              'properties': {
                  'a': 'b',
              }
        }),
    }

    with self.create_integrator(build_params_hook=hook):
      self.buildbucket.api.peek.return_value = {
          'builds': [build],
      }

      run_deferred(self.integrator.poll_builds())

      self.assert_leased('1')
      self.assert_added_build_request(
          '1', 'Debug', self.ssid, properties={'a': 'b', 'foo': 'bar'})

    # Modifications to 'build' in the hook should not be persisted.
    self.assertEqual(build['bucket'], BUCKET)

  def test_build_with_hook_fails_if_valueerror(self):
    def hook(params, build):
      raise ValueError("Test Failure.")

    with self.create_integrator(build_params_hook=hook):
      self.buildbucket.api.peek.return_value = {
          'builds': [{
              'id': '1',
              'bucket': BUCKET,
              'parameters_json': json.dumps({
                  'builder_name': 'Release',
              }),
          }],
      }

      run_deferred(self.integrator.poll_builds())

      self.buildbucket.api.fail.assert_called_once_with(
          id='1',
          body={
              'lease_key': LEASE_KEY,
              'failure_reason': 'INVALID_BUILD_DEFINITION',
              'result_details_json': json.dumps({
                  'error': {
                      'message': 'Test Failure.',
                  },
              }),
          }
      )

  def test_all_scheduled(self):
    with self.create_integrator():
      with self.mock_build_peek():
        run_deferred(self.integrator.poll_builds())

      self.assert_leased(self.buildbucket_build_rel['id'])
      self.assert_leased(self.buildbucket_build_dbg['id'])

      # Assert added two buildsets.
      self.assertEqual(self.buildbot.add_build_request.call_count, 2)
      self.assert_added_build_request(
          self.buildbucket_build_rel['id'], 'Release', self.ssid,
          buildset=BUILDSET)
      self.assert_added_build_request(
          self.buildbucket_build_dbg['id'], 'Debug', self.ssid,
          buildset=BUILDSET)

  def test_polling_with_cursor(self):
    with self.create_integrator():
      peek_response1 = {
          'builds': [self.buildbucket_build_rel],
          'next_cursor': '123',

      }
      peek_response2 = {
          'builds': [self.buildbucket_build_dbg],
      }
      self.buildbucket.api.peek.side_effect = [peek_response1, peek_response2]

      run_deferred(self.integrator.poll_builds())

      self.assertEqual(self.buildbucket.api.peek.call_count, 2)
      _, last_peek_call_kwargs = self.buildbucket.api.peek.call_args
      self.assertEqual(
          last_peek_call_kwargs['start_cursor'],
          peek_response1['next_cursor'])

      self.assert_leased(self.buildbucket_build_rel['id'])
      self.assert_leased(self.buildbucket_build_dbg['id'])

      # Assert added two buildsets.
      self.assertEqual(self.buildbot.add_build_request.call_count, 2)
      self.assert_added_build_request(
          self.buildbucket_build_rel['id'], 'Release', self.ssid,
          buildset=BUILDSET)
      self.assert_added_build_request(
          self.buildbucket_build_dbg['id'], 'Debug', self.ssid,
          buildset=BUILDSET)

  def test_honor_max_lease_count(self):
    with self.create_integrator():
      self.buildbucket.api.peek.return_value = {
          'builds': [
              self.buildbucket_build_rel,
              self.buildbucket_build_dbg,
              self.buildbucket_build_dbg
          ],
      }
      run_deferred(self.integrator.poll_builds())
      # Assert only two builds were leased.
      self.assertEqual(self.buildbucket.api.lease.call_count, 2)

  def test_max_one_lease(self):
    bb = fake_buildbot(one_slave=True)
    with self.create_integrator(bb, max_lease_count=1):
      with self.mock_build_peek():
        run_deferred(self.integrator.poll_builds())
      # Assert only one build was leased and scheduled.
      self.assertEqual(bb.add_build_request.call_count, 1)
      self.assertEqual(self.buildbucket.api.lease.call_count, 1)

  def test_build_not_scheduled_if_builder_name_is_wrong(self):
    with self.create_integrator():
      bb = self.integrator.buildbot
      bb.add_build_request.return_value = (1, 1)

      # No Debug builder.
      del bb.get_builders.return_value['Debug']

      with self.mock_build_peek():
        run_deferred(self.integrator.poll_builds())

      # Assert added one buildset of two.
      self.assertEqual(bb.add_build_request.call_count, 1)

  def test_nothing_is_scheduled_if_builders_do_not_have_connected_slaves(self):
    with self.create_integrator():
      self.buildbot.get_connected_slaves.return_value = []

      run_deferred(self.integrator.poll_builds())

      self.assertFalse(self.buildbucket.api.peek.called)
      self.assertFalse(self.buildbot.add_build_request.called)

  def mock_existing_build(self, put_build_to_lease=True):
    build = Mock()
    build.id = '123321'
    build.getNumber.return_value = 42
    build.isFinished.return_value = False
    info = json.dumps({
       'build': {
            'id': build.id,
            'lease_key': LEASE_KEY,
        },
    })
    build.properties.getProperty.return_value = info
    properties = {
        'a': ('b', 'ValueSource')
    }
    as_dict_result = properties.copy()
    as_dict_result[common.INFO_PROPERTY] = (info, 'buildbucket')
    build.getProperties.return_value.asDict.return_value = as_dict_result
    build.expected_result_details_json = json.dumps({'properties': {'a': 'b'}})

    self.integrator._leases = self.integrator._leases or {}
    self.integrator._leases[build.id] = {
        'key': LEASE_KEY,
        'build_request': Mock(),
        'build': build if put_build_to_lease else None,
    }

    return build

  def test_heartbeats(self):
    def test():
      NUM_BUILDS = 200  # More than batch size.

      self.integrator._leases = {
        str(i): {
          'key': LEASE_KEY,
          'build_request': Mock(),
        } for i in xrange(NUM_BUILDS)
      }

      test_finished = defer.Deferred()

      def assert_heartbeat_sent():
        try:
          updated_builds = set()
          for _, kwargs in self.buildbucket.api.heartbeat_batch.call_args_list:
            for hb in kwargs['body']['heartbeats']:
              updated_builds.add(int(hb['build_id']))
          self.assertEqual(updated_builds, set(xrange(NUM_BUILDS)))
        finally:
          test_finished.callback(None)  # Finish test.

      reactor.callLater(0.001, assert_heartbeat_sent)
      return test_finished

    with self.create_integrator():
      run_deferred(test())

  @contextlib.contextmanager
  def mock_heartbeat_lease_expired(self, build_id):
    response = {
      'results': [{
          'build_id': build_id,
          'error': {
              'reason': 'LEASE_EXPIRED',
          },
      }],
    }
    self.buildbucket.api.heartbeat_batch.side_effect = (
        lambda *_, **__: defer.succeed(response))
    yield
    self.assertTrue(self.buildbucket.api.heartbeat_batch.called)

  def test_lease_for_build_expired(self):
    with self.create_integrator():
      build = self.mock_existing_build()
      with self.mock_heartbeat_lease_expired(build.id):
        run_deferred(self.integrator.send_heartbeats())
      self.assertTrue(self.buildbot.stop_build.called)

  def test_lease_for_build_request_expired(self):
    with self.create_integrator():
      build_request = Mock()
      self.integrator._leases = {
          '1': {
            'key': LEASE_KEY,
            'build_request': build_request,
          },
      }

      with self.mock_heartbeat_lease_expired('1'):
        run_deferred(self.integrator.send_heartbeats())

      self.assertTrue(build_request.cancel.called)

  def test_clean_completed_build_requests(self):
    with self.create_integrator():
      def make_build_request(complete):
        result = Mock()
        result.is_failed.return_value = complete
        return result
      self.integrator._leases = {
          '1': {
              'lease_key': LEASE_KEY,
              'build_request': make_build_request(True),
          },
          '2': {
              'lease_key': LEASE_KEY,
              'build_request': make_build_request(False),
          },
          '3': {
              'lease_key': LEASE_KEY,
              'build_request': make_build_request(True),
              'build': Mock(),
          },
      }

      run_deferred(self.integrator.clean_completed_build_requests())

      self.assertEqual(1, self.buildbucket.api.cancel.call_count)
      self.buildbucket.api.cancel.assert_called_once_with(id='1')

  def test_build_started(self):
    with self.create_integrator():
      build = self.mock_existing_build(put_build_to_lease=False)
      self.buildbucket.api.start.return_value = {}
      self.integrator.on_build_started(build)

      self.buildbucket.api.start.assert_called_once_with(
          id=build.id,
          body={
              'lease_key': LEASE_KEY,
              'url': self.buildbot.get_build_url.return_value,
          })

  def test_build_started_error_response(self):
    with self.create_integrator():
      build = self.mock_existing_build(put_build_to_lease=False)
      self.buildbucket.api.start.return_value = {
          'error': {
              'reason': 'BAD',
              'message': 'Something is bad',
          },
      }
      self.integrator.on_build_started(build)
      self.assertTrue(self.buildbot.stop_build.called)

  def test_build_succeeded(self):
    with self.create_integrator():
      build = self.mock_existing_build()
      self.buildbucket.api.succeed.return_value = {}

      run_deferred(self.integrator.on_build_finished(build, 'SUCCESS'))

      self.assertFalse(build.id in self.integrator._leases)
      self.buildbucket.api.succeed.assert_called_once_with(
          id=build.id,
          body={
              'lease_key': LEASE_KEY,
              'result_details_json': build.expected_result_details_json,
          }
      )

  def test_build_failed(self):
    with self.create_integrator():
      build = self.mock_existing_build()
      self.buildbucket.api.fail.return_value = {}

      run_deferred(self.integrator.on_build_finished(build, 'FAILURE'))

      self.assertFalse(build.id in self.integrator._leases)
      self.buildbucket.api.fail.assert_called_once_with(
          id=build.id,
          body={
              'lease_key': LEASE_KEY,
              'failure_reason': 'BUILD_FAILURE',
              'result_details_json': build.expected_result_details_json,
          }
      )

  def test_build_retried(self):
    with self.create_integrator():
      build = self.mock_existing_build()

      # A build is marked during master stop.
      self.integrator.stop()
      run_deferred(self.integrator.on_build_finished(build, 'RETRY'))
      # Do not delete lease for RETRY builds.
      self.assertTrue(build.id in self.integrator._leases)
      self.assertFalse(self.buildbucket.api.fail.called)

  def test_build_skipped(self):
    with self.create_integrator():
      build = self.mock_existing_build()
      run_deferred(self.integrator.on_build_finished(build, 'SKIPPED'))
      self.assertFalse(build.id in self.integrator._leases)
      self.assertFalse(self.buildbucket.api.fail.called)


if __name__ == '__main__':
  logging.basicConfig(
      level=(logging.DEBUG if '-v' in sys.argv else logging.FATAL))
  if '-v' in sys.argv:
    unittest.TestCase.maxDiff = None
  unittest.main()
