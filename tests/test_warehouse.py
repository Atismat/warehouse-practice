"""Запуск: python3 -m unittest discover -s tests -v"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import unittest
from copy import deepcopy
from warehouse import *

class WarehouseTests(unittest.TestCase):
    def setUp(self):
        self.s = new_state()
        receive(self.s, 'L1', 'C1', 'P1', 40, '2026-09-01T09:00:00+03:00')
        receive(self.s, 'L2', 'C1', 'P1', 50, '2026-09-02T09:00:00+03:00')
        receive(self.s, 'L3', 'C2', 'P1', 10, '2026-09-01T08:00:00+03:00')
    def tearDown(self):
        check_invariants(self.s)
    def unchanged(self, fn, *args):
        before = deepcopy(self.s)
        with self.assertRaises(ValueError): fn(self.s, *args)
        self.assertEqual(before, self.s)
    def test_best_fit(self):
        self.assertEqual(self.s['lots']['L1']['cell'], 'A02')
    def test_tie(self):
        self.assertEqual(best_fit({'B': {'capacity': 10, 'used': 0}, 'A': {'capacity': 10, 'used': 0}}, 10), 'A')
    def test_invalid_quantity(self):
        for q in [0, -1, 1.5, True]:
            self.unchanged(receive, 'BAD', 'C1', 'P1', q, '2026-09-01T09:00:00+03:00')
    def test_overflow(self):
        self.unchanged(receive, 'BIG', 'C1', 'P1', 61, '2026-09-01T09:00:00+03:00')
    def test_duplicate_lot(self):
        self.unchanged(receive, 'L1', 'C1', 'P1', 1, '2026-09-01T09:00:00+03:00')
    def test_unknown_client(self):
        self.unchanged(receive, 'L4', 'OTHER', 'P1', 1, '2026-09-01T09:00:00+03:00')
    def test_timestamp(self):
        self.unchanged(receive, 'L4', 'C1', 'P1', 1, '2026-09-01')
    def test_fifo(self):
        self.assertEqual(reserve_order(self.s, 'O1', 'C1', {'P1': 60}), [('L1', 40), ('L2', 20)])
    def test_owner_isolation(self):
        self.unchanged(reserve_order, 'O1', 'C1', {'P1': 95})
    def test_reserved_not_reused(self):
        reserve_order(self.s, 'O1', 'C1', {'P1': 60})
        self.unchanged(reserve_order, 'O2', 'C1', {'P1': 31})
    def test_order_atomicity(self):
        self.unchanged(reserve_order, 'O1', 'C1', {'P1': 60, 'P2': 1})
    def test_blocked(self):
        self.s['lots']['L1']['blocked'] = True
        self.unchanged(reserve_order, 'O1', 'C1', {'P1': 60})
    def test_ship(self):
        reserve_order(self.s, 'O1', 'C1', {'P1': 60})
        ship_order(self.s, 'O1')
        self.assertEqual([self.s['lots'][x]['quantity'] for x in ['L1','L2','L3']], [0,30,10])
    def test_repeat_ship(self):
        reserve_order(self.s, 'O1', 'C1', {'P1': 60})
        ship_order(self.s, 'O1')
        self.unchanged(ship_order, 'O1')
    def test_cancel(self):
        reserve_order(self.s, 'O1', 'C1', {'P1': 60})
        cancel_order(self.s, 'O1')
        self.assertEqual(available_stock(self.s, 'C1', 'P1'), 90)
        self.unchanged(ship_order, 'O1')
    def test_block_after_reserve(self):
        reserve_order(self.s, 'O1', 'C1', {'P1': 60})
        self.s['lots']['L2']['blocked'] = True
        self.unchanged(ship_order, 'O1')
    def test_duplicate_order(self):
        reserve_order(self.s, 'O1', 'C1', {'P1': 1})
        self.unchanged(reserve_order, 'O1', 'C1', {'P1': 1})
    def test_empty_order(self):
        self.unchanged(reserve_order, 'O1', 'C1', {})
    def test_timezone_order(self):
        self.s['lots']['L1']['received_at'] = '2026-09-02T10:00:00+03:00'
        self.s['lots']['L2']['received_at'] = '2026-09-02T08:00:00+00:00'
        self.assertEqual(reserve_order(self.s, 'O1', 'C1', {'P1': 1}), [('L1',1)])

if __name__ == '__main__': unittest.main()
