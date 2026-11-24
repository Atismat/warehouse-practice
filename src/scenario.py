"""Shared TSV protocol: RESET, RECEIVE, RESERVE, SHIP, CANCEL, BLOCK, AVAILABLE."""
from copy import deepcopy
from datetime import datetime, timezone
import json, sys
from warehouse import new_state, receive, reserve_order, ship_order, cancel_order, available_stock, check_invariants

def normalized(state):
    s=deepcopy(state)
    for lot in s['lots'].values():
        lot['received_at']=datetime.fromisoformat(lot['received_at'].replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
    return json.loads(json.dumps(s))

def run_file(path):
    state=new_state();rows=[]
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith('#'):continue
        a=line.split('\t');result=None;status='OK'
        try:
            if a[0]=='RESET':state=new_state()
            elif a[0]=='RECEIVE':result=receive(state,a[1],a[2],a[3],int(a[4]),a[5])
            elif a[0]=='RESERVE':
                items={}
                if len(a)>3 and a[3]:
                    for pair in a[3].split(','):
                        k,v=pair.split(':')
                        if k in items:raise ValueError('Duplicate product')
                        items[k]=int(v)
                result=reserve_order(state,a[1],a[2],items)
            elif a[0]=='SHIP':ship_order(state,a[1])
            elif a[0]=='CANCEL':cancel_order(state,a[1])
            elif a[0]=='BLOCK':
                if a[1] not in state['lots']:raise ValueError('Unknown lot')
                state['lots'][a[1]]['blocked']=a[2]=='1'
            elif a[0]=='AVAILABLE':result=available_stock(state,a[1],a[2])
            else:raise ValueError('Unknown operation')
        except ValueError:status='ERROR'
        check_invariants(state)
        rows.append(json.loads(json.dumps({'status':status,'result':result,'state':normalized(state)})))
    return rows

if __name__=='__main__':
    from pathlib import Path
    for row in run_file(Path(sys.argv[1])):print(json.dumps(row,ensure_ascii=False))
