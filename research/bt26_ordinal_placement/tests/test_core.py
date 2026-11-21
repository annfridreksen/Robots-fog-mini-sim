import copy,json,unittest
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from bt26 import make_model,search,reference,verify_plan,InputError,prepare_forecast,reconsider
from bt26.scheduler import build_plan,earliest_slot,plan_to_dict,plan_from_dict,NoSchedule
ROOT=Path(__file__).resolve().parents[1]
def inputs():return json.loads((ROOT/'examples/minimal.json').read_text()),json.loads((ROOT/'examples/forecast.json').read_text())
class CoreTests(unittest.TestCase):
    def setUp(self):self.d,self.f=inputs();self.m=make_model(self.d)
    def test_minimal_P(self):
        r=search(self.m,self.f);self.assertEqual(r.plan.identifier,('E','F','E'));self.assertEqual(r.plan.makespan,F(8,1000));self.assertTrue(r.certified);self.assertEqual(verify_plan(self.m,r.plan),())
    def test_minimal_B(self):
        r=search(self.m,self.f,'B');self.assertEqual(r.plan.identifier,('F','F','F'));self.assertEqual(r.plan.makespan,F(4,1000))
    def test_D_same_exact_result(self):self.assertEqual(search(self.m,self.f).plan,search(self.m,self.f,'D').plan)
    def test_reference_matches(self):
        for mode in ('P','B','D'):
            p,n,k=reference(self.m,self.f,mode);self.assertEqual((n,k),(8,6));self.assertEqual(p,search(self.m,self.f,mode).plan)
    def test_no_feasible_deadline(self):
        self.d['deadline_s']='0.003';r=search(make_model(self.d),self.f);self.assertIsNone(r.plan);self.assertEqual(r.status,'NO_PLAN_IN_CLASS')
    def test_deadline_filter(self):
        self.d['deadline_s']='0.007';r=search(make_model(self.d),self.f);self.assertEqual(r.plan.identifier,('E','F','F'));self.assertEqual(r.plan.makespan,F(6,1000))
    def test_deadline_boundary(self):
        self.d['deadline_s']='0.008';self.assertEqual(search(make_model(self.d),self.f).plan.identifier,('E','F','E'))
    def test_missing_forecast(self):self.assertEqual(search(self.m).plan,search(self.m,None,'B').plan)
    def test_constant(self):
        self.f['commands']={'E':7,'F':7};r=search(self.m,self.f);self.assertEqual(r.method,'B');self.assertEqual(r.forecast_status,'constant')
    def test_incomplete(self):
        del self.f['commands']['E'];self.assertEqual(search(self.m,self.f).method,'B')
    def test_stale(self):
        self.f['valid_until_s']='0';self.assertEqual(search(self.m,self.f).forecast_status,'not_current')
    def test_future(self):
        self.f['issued_at_s']='0.5';self.assertEqual(search(self.m,self.f).method,'B')
    def test_direction(self):
        self.f['direction']='larger_is_preferred';self.assertEqual(search(self.m,self.f).method,'B')
    def test_nan_command(self):
        self.f['commands']['E']='NaN';self.assertEqual(search(self.m,self.f).method,'B')
    def test_monotone(self):
        p=search(self.m,self.f).plan;self.f['commands']={'E':13,'F':1001};self.assertEqual(search(self.m,self.f).plan,p)
    def test_unfavourable_not_excluded(self):
        self.f['commands']['F']=1000000;self.assertIn('F',search(self.m,self.f).plan.identifier)
    def test_partial(self):
        with self.assertRaises(NoSchedule):build_plan(self.m,{'A':'E'})
    def test_joint_memory(self):
        with self.assertRaises(NoSchedule):build_plan(self.m,dict.fromkeys(self.m.blocks,'E'))
    def test_memory_boundary(self):self.assertEqual(verify_plan(self.m,build_plan(self.m,{'A':'F','B':'E','C':'E'})),())
    def test_unknown_profile(self):
        del self.d['operations'][0]['duration_s']['E'];self.assertEqual(make_model(self.d).candidates['A'],('F',))
    def test_empty_candidates(self):
        self.d['operations'][2]['duration_s']={};r=search(make_model(self.d),self.f);self.assertIsNone(r.plan);self.assertTrue(r.certified)
    def test_cycle(self):
        self.d['edges'].append({'src':'c','dst':'a1','bits':1})
        with self.assertRaises(InputError):make_model(self.d)
    def test_disconnected(self):
        self.d['edges']=self.d['edges'][:1]
        with self.assertRaises(InputError):make_model(self.d)
    def test_quotient_cycle(self):
        self.d['edges'].append({'src':'a1','dst':'c','bits':1});self.d['blocks']=[{'id':'X','operations':['a1','c']},{'id':'Y','operations':['a2','b']}];self.d.pop('previous');self.d.pop('previous_partition_version')
        with self.assertRaises(InputError):make_model(self.d)
    def test_duplicate_member(self):
        self.d['blocks'][1]['operations'].append('a1')
        with self.assertRaises(InputError):make_model(self.d)
    def test_empty_block(self):
        self.d['blocks'][0]['operations']=[]
        with self.assertRaises(InputError):make_model(self.d)
    def test_previous_partition(self):
        self.d['previous_partition_version']='other'
        with self.assertRaises(InputError):make_model(self.d)
    def test_touching(self):self.assertEqual(earliest_slot({'x':[(F(0),F(1)),(F(2),F(3))]},('x',),F(1),F(1)),F(1))
    def test_shared_slot(self):self.assertEqual(earliest_slot({'x':[(F(1),F(3))],'y':[(F(0),F(2))]},('x','y'),F(0),F(1)),F(3))
    def test_zero_duration(self):self.assertEqual(earliest_slot({'x':[(F(0),F(99))]},('x',),F(1),F(0)),F(1))
    def test_zero_bandwidth(self):
        self.d['links'][0]['bandwidth_bps']=0
        with self.assertRaises(NoSchedule):build_plan(make_model(self.d),{'A':'E','B':'F','C':'F'})
    def test_local(self):self.assertTrue(all(not t.hops for t in build_plan(self.m,dict.fromkeys(self.m.blocks,'F')).transfers))
    def test_no_network(self):
        self.d['links']=[]
        with self.assertRaises(NoSchedule):build_plan(make_model(self.d),{'A':'E','B':'F','C':'E'})
    def test_bad_duration(self):
        p=search(self.m,self.f).plan;r=p.runs[0];self.assertTrue(verify_plan(self.m,replace(p,runs=(replace(r,end=r.end+1),)+p.runs[1:])))
    def test_bad_coverage(self):
        p=search(self.m,self.f).plan;self.assertTrue(verify_plan(self.m,replace(p,assignment=(('A','E'),))))
    def test_bad_message(self):
        p=search(self.m,self.f).plan;self.assertTrue(verify_plan(self.m,replace(p,transfers=p.transfers[:1])))
    def test_bad_route(self):
        p=search(self.m,self.f).plan;t=p.transfers[0];t=replace(t,hops=(replace(t.hops[0],link='FE'),));self.assertTrue(verify_plan(self.m,replace(p,transfers=(t,)+p.transfers[1:])))
    def test_bad_arrival(self):
        p=search(self.m,self.f).plan;t=p.transfers[0];self.assertTrue(verify_plan(self.m,replace(p,transfers=(replace(t,arrival=F(0)),)+p.transfers[1:])))
    def test_snapshot(self):
        p=search(self.m,self.f).plan;self.d['infrastructure_version']='new';self.assertIn('snapshot_mismatch',verify_plan(make_model(self.d),p))
    def test_source_immutable(self):
        old=copy.deepcopy(self.m.source);search(self.m,self.f);search(self.m,None,'B');self.assertEqual(old,self.m.source)
    def test_roundtrip(self):
        p=search(self.m,self.f).plan;self.assertEqual(p,plan_from_dict(plan_to_dict(p)))
    def test_zero_budget(self):
        r=search(self.m,self.f,max_checks=0);self.assertEqual(r.status,'SEARCH_LIMIT_NO_PLAN');self.assertFalse(r.certified)
    def test_limited_D(self):self.assertFalse(search(self.m,self.f,'D',max_checks=1).certified)
    def test_negative_budget(self):
        with self.assertRaises(InputError):search(self.m,self.f,max_checks=-1)
    def test_overheads(self):
        self.d['planning_delay_s']='0.005';self.d['apply_delay_s']='0.002';self.assertIsNone(search(make_model(self.d),self.f).plan)
    def test_reconsider_keep(self):self.assertEqual(reconsider(self.m,self.m.previous,self.f)['action'],'KEEP')
    def test_reconsider_authorized(self):
        r=reconsider(self.m,self.m.previous,self.f,allow_preference_change=True);self.assertEqual(r['action'],'RESELECT');self.assertEqual(r['search']['plan']['assignment'],[['A','E'],['B','F'],['C','E']])
    def test_no_repartition(self):
        with self.assertRaises(InputError):reconsider(self.m,{'A':'F'},self.f)
    def test_multihop(self):
        self.d['devices'].append({'id':'R','layer':'router','memory_bytes':0})
        self.d['links']=[{'id':x,'src':a,'dst':b,'bandwidth_bps':speed,'latency_s':0} for x,a,b,speed in [('ER','E','R',16000000),('RF','R','F',16000000),('FE','F','E',8000000)]]
        m=make_model(self.d);p=build_plan(m,{'A':'E','B':'F','C':'E'});self.assertEqual(len(p.transfers[0].hops),2);self.assertEqual(p.makespan,F(8,1000));self.assertEqual(verify_plan(m,p),())
    def test_busy(self):
        self.d['busy']={'cpu:F':[['0','0.003']]};m=make_model(self.d);p=build_plan(m,dict.fromkeys(m.blocks,'F'));self.assertEqual(p.makespan,F(7,1000));self.assertEqual(verify_plan(m,p),())
    def test_cloud(self):
        self.d['devices'][1]['layer']='cloud';self.assertIsNone(search(make_model(self.d),self.f).plan)
if __name__=='__main__':unittest.main()
