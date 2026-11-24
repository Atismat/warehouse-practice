"""SQLite snapshot persistence; domain operations still run in Python memory."""
import sqlite3
from pathlib import Path
from warehouse import check_invariants

ROOT = Path(__file__).resolve().parents[1]

def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    return db

def create(db):
    db.executescript((ROOT / 'sql/schema.sql').read_text())

def save(db, state):
    # Assert-based diagnostics are not the only persistence guard.
    for lid, lot in state['lots'].items():
        active = sum(q for o in state['orders'].values() if o['status']=='RESERVED' for l,q in o['plan'] if l==lid)
        balance = sum(m['quantity'] for m in state['movements'] if m['lot']==lid)
        if not 0 <= lot['reserved'] <= lot['quantity'] or lot['reserved']!=active or lot['quantity']!=balance:
            raise ValueError('Inconsistent lot snapshot')
    for cid, c in state['cells'].items():
        used=sum(l['quantity'] for l in state['lots'].values() if l['cell']==cid)
        if c['used']!=used or not 0<=used<=c['capacity']:
            raise ValueError('Inconsistent cell snapshot')
    if state['next_seq'] != max((l['seq'] for l in state['lots'].values()),default=0)+1:
        raise ValueError('Inconsistent sequence')
    with db:
        for table in ['movement','reservation','order_line','outbound_order','lot','warehouse_cell','product','client']:
            db.execute('DELETE FROM '+table)
        db.executemany('INSERT INTO client VALUES (?)', [(x,) for x in state['clients']])
        db.executemany('INSERT INTO product(product_id) VALUES (?)', [(x,) for x in state['products']])
        db.executemany('INSERT INTO warehouse_cell VALUES (?,?)', [(k,c['capacity']) for k,c in state['cells'].items()])
        for lid,l in state['lots'].items():
            db.execute('INSERT INTO lot VALUES (?,?,?,?,?,?,?,?)',(lid,l['client'],l['product'],l['cell'],l['quantity'],l['received_at'],l['seq'],int(l['blocked'])))
        for oid,o in state['orders'].items():
            db.execute('INSERT INTO outbound_order VALUES (?,?,?)',(oid,o['client'],o['status']))
            for no,(product,q) in enumerate(o['items'].items(),1):
                db.execute('INSERT INTO order_line VALUES (?,?,?,?,?)',(oid,product,o['client'],q,no))
            for pos,(lid,q) in enumerate(o['plan'],1):
                db.execute('INSERT INTO reservation VALUES (?,?,?,?,?,?)',(oid,state['lots'][lid]['product'],o['client'],lid,q,pos))
        for no,m in enumerate(state['movements'],1):
            db.execute('INSERT INTO movement VALUES (?,?,?,?,?)',(no,m['lot'],m['type'],m['quantity'],m['order']))
        # Round-trip checks also reject malformed references or order plans.
        loaded=load(db)
        check_invariants(loaded)
        for o in loaded['orders'].values():
            for product,q in o['items'].items():
                if sum(n for lid,n in o['plan'] if loaded['lots'][lid]['product']==product)!=q:
                    raise ValueError('Order plan does not cover its lines')
        if loaded != state:
            raise ValueError('Snapshot differs after load')

def load(db):
    state={'clients':[r[0] for r in db.execute('SELECT client_id FROM client ORDER BY rowid')],
        'products':[r[0] for r in db.execute('SELECT product_id FROM product ORDER BY rowid')],
        'cells':{},'lots':{},'orders':{},'movements':[],'next_seq':1}
    for cid,capacity,used in db.execute('SELECT * FROM cell_balance ORDER BY cell_id'):
        state['cells'][cid]={'capacity':capacity,'used':used}
    for lid,client,product,cell,q,time,seq,blocked,reserved in db.execute('SELECT * FROM lot_balance ORDER BY seq'):
        state['lots'][lid]={'client':client,'product':product,'cell':cell,'quantity':q,'reserved':reserved,
                              'received_at':time,'seq':seq,'blocked':bool(blocked)}
        state['next_seq']=max(state['next_seq'],seq+1)
    for oid,client,status in db.execute('SELECT * FROM outbound_order ORDER BY rowid'):
        state['orders'][oid]={'client':client,'status':status,
            'items':dict(db.execute('SELECT product_id,quantity FROM order_line WHERE order_id=? ORDER BY line_no',(oid,))),
            'plan':list(db.execute('SELECT lot_id,quantity FROM reservation WHERE order_id=? ORDER BY position',(oid,)))}
    for _,lid,kind,q,oid in db.execute('SELECT * FROM movement ORDER BY movement_id'):
        state['movements'].append({'type':kind,'lot':lid,'quantity':q,'order':oid})
    return state

if __name__=='__main__':
    import argparse, json
    from scenario import run_file
    ap=argparse.ArgumentParser(description='Create a NEW database from the shared demo; never overwrite an existing file')
    ap.add_argument('path');args=ap.parse_args()
    target=Path(args.path)
    # Exclusive file creation prevents accidental replacement.
    with target.open('xb'): pass
    with connect(target) as db:
        create(db);state=run_file(ROOT/'data/demo.tsv')[-1]['state']
        for order in state['orders'].values():order['plan']=[tuple(x) for x in order['plan']]
        save(db,state)
        print(json.dumps(load(db),ensure_ascii=False,indent=2))
        print('foreign_key_check:',list(db.execute('PRAGMA foreign_key_check')))
        print('integrity_check:',db.execute('PRAGMA integrity_check').fetchone()[0])
