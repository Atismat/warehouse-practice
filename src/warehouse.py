"""Учебный процедурный прототип склада. Количества — целые коробки."""
from copy import deepcopy
from datetime import datetime


def positive(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Количество должно быть положительным целым числом')


def new_state():
    return {'clients': ['C1', 'C2'], 'products': ['P1', 'P2'],
            'cells': {'A01': {'capacity': 100, 'used': 0},
                      'A02': {'capacity': 60, 'used': 0}},
            'lots': {}, 'orders': {}, 'movements': [], 'next_seq': 1}


def best_fit(cells, quantity):
    """Один линейный проход; минимум свободного места после размещения."""
    positive(quantity)
    best, best_free = None, None
    for cell_id, cell in cells.items():
        free = cell['capacity'] - cell['used']
        if free >= quantity and (best is None or (free, cell_id) < (best_free, best)):
            best, best_free = cell_id, free
    if best is None:
        raise ValueError('Нет ячейки для размещения всей партии')
    return best


def receive(state, lot_id, client, product, quantity, received_at):
    """Партия уникальна; проверка всех входов предшествует изменениям."""
    positive(quantity)
    if not isinstance(lot_id, str) or not lot_id or lot_id in state['lots']:
        raise ValueError('Некорректный или повторный номер партии')
    if client not in state['clients'] or product not in state['products']:
        raise ValueError('Неизвестный клиент или товар')
    timestamp = datetime.fromisoformat(received_at)
    if timestamp.tzinfo is None:
        raise ValueError('Необходим часовой пояс времени приёмки')
    cell_id = best_fit(state['cells'], quantity)
    seq = state['next_seq']
    state['lots'][lot_id] = {'client': client, 'product': product,
        'cell': cell_id, 'quantity': quantity, 'reserved': 0,
        'received_at': timestamp.isoformat(), 'seq': seq, 'blocked': False}
    state['cells'][cell_id]['used'] += quantity
    state['movements'].append({'type': 'RECEIVE', 'lot': lot_id,
                              'quantity': quantity, 'order': None})
    state['next_seq'] += 1
    return cell_id


def fifo_plan(lots, client, product, quantity):
    """Возвращает план без изменения остатков; при дефиците отказывает."""
    positive(quantity)
    candidates = [(lot_id, lot) for lot_id, lot in lots.items()
                  if lot['client'] == client and lot['product'] == product
                  and not lot['blocked'] and lot['quantity'] > lot['reserved']]
    candidates.sort(key=lambda item: (datetime.fromisoformat(item[1]['received_at']),
                                      item[1]['seq']))
    remaining, plan = quantity, []
    for lot_id, lot in candidates:
        take = min(remaining, lot['quantity'] - lot['reserved'])
        plan.append((lot_id, take))
        remaining -= take
        if remaining == 0:
            return plan
    raise ValueError('Недостаточно доступного товара данного клиента')


def reserve_order(state, order_id, client, items):
    """Резерв всего заказа атомарен при ошибке входных данных/дефиците."""
    if not isinstance(order_id, str) or not order_id or order_id in state['orders']:
        raise ValueError('Некорректный или повторный номер заказа')
    if client not in state['clients'] or not isinstance(items, dict) or not items:
        raise ValueError('Некорректный клиент или пустой заказ')
    work_lots = deepcopy(state['lots'])
    plan = []
    for product, quantity in items.items():
        if product not in state['products']:
            raise ValueError('Неизвестный товар')
        for lot_id, take in fifo_plan(work_lots, client, product, quantity):
            work_lots[lot_id]['reserved'] += take
            plan.append((lot_id, take))
    state['lots'] = work_lots
    state['orders'][order_id] = {'client': client, 'items': dict(items),
                                 'status': 'RESERVED', 'plan': plan}
    return list(plan)


def ship_order(state, order_id):
    """Списание только по действующему резерву. Повторная выдача запрещена."""
    order = state['orders'].get(order_id)
    if order is None or order['status'] != 'RESERVED':
        raise ValueError('Заказ не существует или не находится в резерве')
    # Сначала проверить весь план, затем применить его.
    for lot_id, quantity in order['plan']:
        lot = state['lots'][lot_id]
        if lot['blocked'] or lot['reserved'] < quantity or lot['quantity'] < quantity:
            raise ValueError('Выдача невозможна: блокировка или нарушение резерва')
    for lot_id, quantity in order['plan']:
        lot = state['lots'][lot_id]
        lot['quantity'] -= quantity
        lot['reserved'] -= quantity
        state['cells'][lot['cell']]['used'] -= quantity
        state['movements'].append({'type': 'SHIP', 'lot': lot_id,
                                  'quantity': -quantity, 'order': order_id})
    order['status'] = 'SHIPPED'


def cancel_order(state, order_id):
    order = state['orders'].get(order_id)
    if order is None or order['status'] != 'RESERVED':
        raise ValueError('Отменить можно только зарезервированный заказ')
    for lot_id, quantity in order['plan']:
        state['lots'][lot_id]['reserved'] -= quantity
    order['status'] = 'CANCELLED'


def available_stock(state, client, product):
    return sum(lot['quantity'] - lot['reserved'] for lot in state['lots'].values()
               if lot['client'] == client and lot['product'] == product
               and not lot['blocked'])


def check_invariants(state):
    """Контроль количества, вместимости, резервов и журнала движений."""
    for lot_id, lot in state['lots'].items():
        assert 0 <= lot['reserved'] <= lot['quantity']
        active = sum(q for order in state['orders'].values()
                     if order['status'] == 'RESERVED'
                     for lid, q in order['plan'] if lid == lot_id)
        assert active == lot['reserved']
        assert sum(m['quantity'] for m in state['movements'] if m['lot'] == lot_id) == lot['quantity']
    for cell_id, cell in state['cells'].items():
        assert cell['used'] == sum(l['quantity'] for l in state['lots'].values() if l['cell'] == cell_id)
        assert 0 <= cell['used'] <= cell['capacity']
