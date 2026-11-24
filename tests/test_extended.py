import sys, unittest, sqlite3, json, subprocess
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from warehouse import *
from scenario import run_file
from storage import connect, create, save, load
ROOT=Path(__file__).resolve().parents[1]
class InputRegressionTests(unittest.TestCase):
 def test_missing_timestamp_is_domain_error(self):
  for timestamp in [None,123,[],{}]:
   s=new_state();before=deepcopy(s)
   with self.assertRaises(ValueError):receive(s,'L1','C1','P1',1,timestamp)
   self.assertEqual(s,before)
 def test_exact_capacity_and_empty_stock(self):
  s=new_state();receive(s,'L1','C1','P1',60,'2026-09-01T09:00:00Z');receive(s,'L2','C1','P1',100,'2026-09-01T09:00:00Z')
  with self.assertRaises(ValueError):receive(s,'L3','C1','P1',1,'2026-09-01T09:00:00Z')
  reserve_order(s,'O1','C1',{'P1':160});ship_order(s,'O1');self.assertEqual(available_stock(s,'C1','P1'),0);check_invariants(s)
 def test_same_instant_uses_seq(self):
  s=new_state();receive(s,'Z','C1','P1',1,'2026-09-01T09:00:00+03:00');receive(s,'A','C1','P1',1,'2026-09-01T06:00:00Z')
  self.assertEqual(reserve_order(s,'O1','C1',{'P1':1}),[('Z',1)])
class DatabaseTests(unittest.TestCase):
 def setUp(self):
  self.db=connect(':memory:');create(self.db);self.s=run_file(ROOT/'data/demo.tsv')[-1]['state']
  for o in self.s['orders'].values():o['plan']=[tuple(x) for x in o['plan']]
  save(self.db,self.s)
 def tearDown(self):self.db.close()
 def rejects(self,sql):
  with self.assertRaises(sqlite3.IntegrityError):
   with self.db:self.db.execute(sql)
 def test_round_trip(self):self.assertEqual(load(self.db),self.s)
 def test_foreign_key(self):self.rejects("UPDATE lot SET client_id='OTHER' WHERE lot_id='L3'")
 def test_duplicate(self):self.rejects("INSERT INTO client VALUES ('C1')")
 def test_negative(self):self.rejects("UPDATE lot SET quantity=-1 WHERE lot_id='L3'")
 def test_capacity(self):self.rejects("UPDATE lot SET quantity=61 WHERE lot_id='L3'")
 def test_capacity_reduction(self):self.rejects("UPDATE warehouse_cell SET capacity=1 WHERE cell_id='A02'")
 def test_status(self):self.rejects("UPDATE outbound_order SET status='NEW'")
 def test_owner_and_product(self):self.rejects("UPDATE reservation SET lot_id='L3' WHERE lot_id='L1'")
 def test_movement_sign(self):self.rejects("UPDATE movement SET quantity=10 WHERE type='SHIP'")
 def test_not_null(self):self.rejects("UPDATE lot SET received_at=NULL WHERE lot_id='L3'")
 def test_invalid_time(self):self.rejects("UPDATE lot SET received_at='2026-09-01' WHERE lot_id='L3'")
 def test_strict_quantity(self):self.rejects("UPDATE lot SET quantity=1.5 WHERE lot_id='L3'")
 def test_transaction_rollback(self):
  bad=deepcopy(self.s);bad['clients'].remove('C1')
  with self.assertRaises(sqlite3.IntegrityError):save(self.db,bad)
  self.assertEqual(load(self.db),self.s)
 def test_invalid_snapshot_preserves_database(self):
  bad=deepcopy(self.s);bad['lots']['L3']['quantity']=9
  with self.assertRaises(ValueError):save(self.db,bad)
  self.assertEqual(load(self.db),self.s)
 def test_reserved_cancelled_round_trip(self):
  s=new_state();receive(s,'L1','C1','P1',10,'2026-09-01T09:00:00Z');reserve_order(s,'O1','C1',{'P1':3});save(self.db,s);self.assertEqual(load(self.db),s)
  cancel_order(s,'O1');save(self.db,s);self.assertEqual(load(self.db),s)
 def test_integrity(self):
  self.assertEqual(list(self.db.execute('PRAGMA foreign_key_check')),[]);self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
class CrossLanguageTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  (ROOT/'build').mkdir(exist_ok=True)
  subprocess.run(['javac','-Xlint:all','-d',str(ROOT/'build'),*map(str,(ROOT/'java/src/warehouse').glob('*.java'))],check=True,capture_output=True,text=True)
 def test_all_shared_operations(self):
  expected=run_file(ROOT/'data/scenarios.tsv')
  result=subprocess.run(['java','-cp',str(ROOT/'build'),'warehouse.Runner',str(ROOT/'data/scenarios.tsv')],check=True,capture_output=True,text=True)
  actual=[json.loads(x) for x in result.stdout.splitlines()];self.assertEqual(actual,expected)
  print(f'Compared {len(expected)} operation snapshots in 15 scenarios')
  for i,row in enumerate(actual):
   if row['status']=='ERROR':self.assertEqual(row['state'],actual[i-1]['state'])
 def test_control_oracle(self):
  rows=run_file(ROOT/'data/demo.tsv');s=rows[-1]['state']
  self.assertEqual(rows[3]['result'],[['L1',40],['L2',20]]);self.assertEqual(rows[4]['result'],30)
  self.assertEqual([s['lots'][x]['quantity'] for x in ['L1','L2','L3']],[0,30,10])
  self.assertEqual([s['cells'][x]['used'] for x in ['A01','A02']],[30,10]);self.assertEqual(s['orders']['O1']['status'],'SHIPPED')
