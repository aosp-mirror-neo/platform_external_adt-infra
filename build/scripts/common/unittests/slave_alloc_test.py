#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import test_env # pylint: disable=W0611

from common import slave_alloc


class SlavePoolTestCase(unittest.TestCase):

  def _assertAllocations(self, sa, **key_map):
    sa_map = {}
    for k, v in sa.GetSlaveMap().entries.iteritems():
      for key in v.keys:
        sa_map.setdefault(key, set()).add(k)

    # Sort the entries so they're ordered.
    sa_key_map = {}
    for k, v in sa_map.iteritems():
      sa_key_map[k] = tuple(sorted(v))
    self.assertEqual(key_map, sa_key_map)

  def testBasicAllocation_FixedCount(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1', 'a2', 'a3', 'a4')
    sa.Join('test', sa.Alloc('basic', count=2))
    self._assertAllocations(sa, test=('a0', 'a1'))

  def testBasicAllocation_UnlimitedCount(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1')
    sa.Join('test', sa.Alloc('basic', count=None))
    self._assertAllocations(sa, test=('a0', 'a1'))

  def testBasicAllocation_MixedCount(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1', 'a2', 'a3')
    sa.Join('test', sa.Alloc('Aunlimited', count=None))
    sa.Join('test2', sa.Alloc('Zfinite', count=2))
    self._assertAllocations(sa, test=('a2', 'a3'), test2=('a0', 'a1'))

  def testBasicAllocation_UnlimitedCountWithNoMoreSlavesRaises(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1')
    sa.Join('test', sa.Alloc('unlimited', count=None))
    sa.Join('test2', sa.Alloc('finite', count=2))
    self.assertRaises(AssertionError, sa._GetSlaveClassMap)

  def testBasicAllocation_Rotation(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1')
    sa.Join('test', sa.Alloc('basic', exclusive=False))
    sa.Join('test2', sa.Alloc('other', exclusive=False))
    sa.Join('test3', sa.Alloc('third', exclusive=False))
    self._assertAllocations(sa, test=('a0',), test2=('a1',), test3=('a0',))

  def testNonExclusiveAllocation(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1')
    sa.Join('test', sa.Alloc('basic', exclusive=False, count=2))
    sa.Join('test2', sa.Alloc('other', exclusive=False, count=2))
    self._assertAllocations(sa, test=('a0', 'a1'), test2=('a0', 'a1'))

  def testExclusiveAllocation(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1')
    sa.Join('test', sa.Alloc('basic'))
    sa.Join('test2', sa.Alloc('other'))
    self._assertAllocations(sa, test=('a0',), test2=('a1',))

  def testPoolConstrainedAllocation(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0')
    sa.AddPool('other', 't0')
    sa.AddPool('extra', 'u0')
    sa.Join('test', sa.Alloc('basic', pools=('default', 'extra'),
                                       count=2))
    self._assertAllocations(sa, test=('a0', 'u0'))

  def testMultiKeyAllocation(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0')

    basic = sa.Alloc('basic')
    sa.Join('test', basic)
    sa.Join('test2', basic)

    self._assertAllocations(sa, test=('a0',), test2=('a0',))

  def testBasicAllocation_WithState(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1')
    basic = sa.Alloc('basic')
    sa.Join('test', basic)
    sa.Join('test2', sa.Alloc('other'))
    sa.LoadStateDict({basic.name: {basic.subtype: ['a1']}})
    self._assertAllocations(sa, test=('a1',), test2=('a0',))

  def testAllocation_StateWithConfigChange(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1', 'b0', 'c0', 'c1')
    basic = sa.Alloc('basic', count=3)
    sa.Join('test', basic)

    # State has 'b1', which no longer exists in the pool.
    sa.LoadStateDict({basic.name: {basic.subtype: ['a1', 'b0', 'b1']}})
    self._assertAllocations(sa, test=('a0', 'a1', 'b0'))

  def testAllocation_StateWithClassCountChange(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('default', 'a0', 'a1', 'b0', 'b1', 'b2', 'b3')
    basic = sa.Alloc('basic', count=2)
    sa.Join('test', basic)
    sa.Join('test2', sa.Alloc('other', count=3))

    # State has 4 slaves allocated, but the class only requests two.
    sa.LoadStateDict({basic.name: {basic.subtype: ['a1', 'b1', 'b2', 'b3']}})
    self._assertAllocations(sa, test=('a1', 'b1'), test2=('a0', 'b0', 'b2'))

  def testAddPool_IterativeGrowthAugmentsPool(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('test', 'a0')
    sa.AddPool('test')
    sa.AddPool('test', 'a1')
    self.assertSetEqual(sa.GetPool('test'), set(['a0', 'a1']))

  def testAddPool_SlaveInMultiplePoolsRaisesAssertion(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('test', 'a0')
    sa.AddPool('test', 'a0') # Can add to same pool without a problem.
    self.assertRaises(ValueError, sa.AddPool, 'test2', 'a0')

  def testAlloc_ClassAllocationWithInvalidPoolsRaisesAssertion(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('test', 'a0')
    self.assertRaises(AssertionError, sa.Alloc, 'test',
                      pools=('test', 'invalid'))

  def testAlloc_SameClassWithDifferentConfigsRaisesAssertion(self):
    sa = slave_alloc.SlaveAllocator()
    sa.Alloc('myclass', subtype='a', exclusive=True)
    self.assertRaises(AssertionError,
                      sa.Alloc, 'myclass', subtype='a', exclusive=False)

  def testJoin_FailureToAllocateRaisesAssertion(self):
    sa = slave_alloc.SlaveAllocator()
    sa.AddPool('test', 'a0', 'a1')
    sa.Join('key', sa.Alloc('myclass', count=3))
    self.assertRaises(AssertionError, sa._GetSlaveClassMap)


if __name__ == '__main__':
  unittest.main()
