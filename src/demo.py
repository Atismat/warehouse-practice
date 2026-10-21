"""Запуск: python3 src/demo.py"""
import json
from warehouse import new_state, receive, reserve_order, ship_order, available_stock, check_invariants

state = new_state()
receive(state, 'L1', 'C1', 'P1', 40, '2026-09-01T09:00:00+03:00')
receive(state, 'L2', 'C1', 'P1', 50, '2026-09-02T09:00:00+03:00')
receive(state, 'L3', 'C2', 'P1', 10, '2026-09-01T08:00:00+03:00')
print('Размещение:', {key: lot['cell'] for key, lot in state['lots'].items()})
print('План FIFO:', reserve_order(state, 'O1', 'C1', {'P1': 60}))
print('Доступно C1 после резерва:', available_stock(state, 'C1', 'P1'))
ship_order(state, 'O1')
check_invariants(state)
print('Остатки:', {key: lot['quantity'] for key, lot in state['lots'].items()})
print('Заказ:', state['orders']['O1']['status'])
print('Контроль инвариантов: OK')
print(json.dumps(state, ensure_ascii=False, indent=2))
