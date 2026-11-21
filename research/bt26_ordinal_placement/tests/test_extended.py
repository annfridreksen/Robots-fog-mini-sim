import copy,json,unittest,random
from pathlib import Path
from fractions import Fraction as F
from dataclasses import replace
from bt26 import *
from bt26.scheduler import build_plan,NoSchedule,plan_from_dict,earliest_route,earliest_slot
from bt26.replay import replay
from bt26.search import command_vector
from run_study import synthetic
from itertools import product
ROOT=Path(__file__).resolve().parents[1]
class ExtendedTests(unittest.TestCase):
    def setUp(self):self.d=json.loads((ROOT/'examples/minimal.json').read_text());self.f=json.loads((ROOT/'examples/forecast.json').read_text())
    def test_replan_busy(self):
        self.d['deadline_s']='0.007';self.d['busy']={'cpu:F':[['0','0.004']]};m=make_model(self.d);r=reconsider(m,m.previous,self.f);p=plan_from_dict(r['search']['plan']);self.assertEqual(p.identifier,('E','F','F'));self.assertEqual(p.makespan,F(7,1000))
    def test_keep_monotone(self):
        m=make_model(self.d);f=copy.deepcopy(self.f);f['commands']={'E':10,'F':100};self.assertEqual(reconsider(m,m.previous,f,self.f,allow_preference_change=True)['action'],'KEEP')
    def test_replay_identical(self):
        for s in range(10):
            d,f,_=synthetic(s);m=make_model(d)
            for mode in ('P','B'):
                p=search(m,f,mode).plan;self.assertEqual(replay(m,p)['plan'],p)
    def test_hidden_busy(self):
        m=make_model(self.d);p=search(m,self.f,'B').plan;self.d['busy']={'cpu:F':[['0','0.004']]};self.d['infrastructure_version']='changed';r=replay(make_model(self.d),p);self.assertEqual(r['plan'].identifier,p.identifier);self.assertEqual(r['plan'].makespan,F(8,1000))
    def test_replay_unavailable(self):
        p=search(make_model(self.d),self.f,'B').plan;self.d['devices'][1]['available']=False;self.assertEqual(replay(make_model(self.d),p)['status'],'EXECUTION_UNAVAILABLE')
    def test_fork_join_shared(self):
        d=self.d;d['operations']=[{'id':v,'memory_bytes':1,'duration_s':{'E':'0.001','F':'0.001'}} for v in 'abcd'];d['blocks']=[{'id':v.upper(),'operations':[v]} for v in 'abcd'];d['edges']=[{'src':a,'dst':b,'bits':8000} for a,b in [('a','b'),('a','c'),('b','d'),('c','d')]];d['previous']={v:'F' for v in 'ABCD'}
        for l in d['links']:l['shared_resources']=['shared:radio']
        m=make_model(d);p=build_plan(m,{'A':'E','B':'F','C':'F','D':'E'});self.assertEqual(verify_plan(m,p),());xs=sorted((h.start,h.end) for t in p.transfers for h in t.hops);self.assertTrue(all(a[1]<=b[0] for a,b in zip(xs,xs[1:])))
    def test_mutated_collision(self):
        m=make_model(self.d);p=search(m,self.f,'B').plan;r=p.runs[1];p=replace(p,runs=(p.runs[0],replace(r,start=F(0),end=r.end-r.start),p.runs[2]));self.assertTrue(any('resource_conflict' in x for x in verify_plan(m,p)))
    def test_mutated_memory(self):
        m=make_model(self.d);p=search(m,self.f,'B').plan;self.d['devices'][1]['memory_bytes']=5000000;n=make_model(self.d);self.assertIn('memory:F',verify_plan(n,replace(p,fingerprint=n.fingerprint)))
    def test_D_not_first_certificate(self):self.assertNotEqual(search(make_model(self.d),self.f,'D',max_checks=1).status,'FEASIBLE_CERTIFIED')
    def test_nan_profile(self):
        self.d['operations'][0]['duration_s']['E']='nan'
        with self.assertRaises(InputError):make_model(self.d)
    def test_calendar_overlap(self):
        self.d['busy']={'cpu:E':[['0','1'],['0.5','2']]}
        with self.assertRaises(InputError):make_model(self.d)
    def test_equal_route_order(self):
        self.d['devices'] += [{'id':x,'layer':'router','memory_bytes':0} for x in ['R1','R2']]
        self.d['links']=[{'id':x,'src':a,'dst':b,'bandwidth_bps':16000000,'latency_s':0} for x,a,b in [('ER1','E','R1'),('R1F','R1','F'),('ER2','E','R2'),('R2F','R2','F'),('FE','F','E')]]
        a={'A':'E','B':'F','C':'F'};p=build_plan(make_model(self.d),a);self.d['links'].reverse();p2=build_plan(make_model(self.d),a);self.assertEqual(p.transfers,p2.transfers);self.assertEqual(p.transfers[0].hops[0].link,'ER1')
    def test_input_list_permutation(self):
        p=search(make_model(self.d),self.f).plan
        for name in ['operations','blocks','devices','links','edges']:self.d[name].reverse()
        p2=search(make_model(self.d),self.f).plan;self.assertEqual(p.assignment,p2.assignment);self.assertEqual(p.runs,p2.runs)
    def test_extra_20_differential(self):
        for seed in range(60,80):
            d,f,_=synthetic(seed);m=make_model(d)
            for mode in ('P','B','D'):
                p,_,_=reference(m,f,mode);r=search(m,f,mode);self.assertEqual(p,r.plan);self.assertTrue(r.certified)
    def test_malformed_contract(self):
        for d in (None,[],{}, {'task_version':'v'}):
            with self.assertRaises(InputError):make_model(d)
    def test_load_scope(self):
        self.f['load_scope']='different';r=search(make_model(self.d),self.f);self.assertEqual(r.method,'B');self.assertEqual(r.forecast_status,'incompatible_contract')
    def test_bad_forecast_container(self):
        for f in ([],42,{'commands':[]}):self.assertEqual(search(make_model(self.d),f).method,'B')
    def test_bound_all_completions(self):
        for seed in range(8):
            d,f,_=synthetic(seed);m=make_model(d);c,_=prepare_forecast(m,f)
            if c is None:continue
            for vals in product(*(m.candidates[b] for b in m.blocks)):
                r=command_vector(dict(zip(m.blocks,vals)),c)
                for k in range(len(vals)+1):
                    lb=tuple(sorted([c[d] for d in vals[:k]]+[min(c[d] for d in m.candidates[b]) for b in m.blocks[k:]],reverse=True));self.assertLessEqual(lb,r)
    def test_routes_vs_simple_paths(self):
        for seed in range(25):
            rng=random.Random(seed);d=copy.deepcopy(self.d);d['devices'] += [{'id':x,'layer':'router','memory_bytes':0} for x in ['R1','R2']];names=['E','F','R1','R2'];d['links']=[];d['busy']={}
            for a in names:
                for b in names:
                    if a!=b and (rng.random()<0.65 or (a,b)==('E','F')):
                        name=a+'_'+b;d['links'].append({'id':name,'src':a,'dst':b,'bandwidth_bps':rng.choice([4000000,8000000,16000000]),'latency_s':str(F(rng.randrange(3),1000))})
                        if rng.random()<0.6:
                            s=F(rng.randrange(6),1000);d['busy']['net:'+name]=[[str(s),str(s+F(rng.randrange(1,4),1000))]]
            m=make_model(d);ready=F(rng.randrange(4),1000);_,actual=earliest_route(m,m.busy,'E','F',ready,8000)
            def walk(node,at,seen):
                if node=='F':return [at]
                out=[]
                for l in m.outgoing[node]:
                    if l.dst in seen:continue
                    dur=F(8000)/l.bps;t=earliest_slot(m.busy,l.resources,at,dur);out+=walk(l.dst,t+dur+l.latency,seen|{l.dst})
                return out
            self.assertEqual(actual,min(walk('E',ready,{'E'})))
    def test_full_equal_group(self):
        self.d['deadline_s']='0.007';m=make_model(self.d);p,_,_=reference(m,self.f);r=search(m,self.f);self.assertEqual(p,r.plan);self.assertEqual(p.identifier,('E','F','F'))
    def test_limit_is_not_infeasibility(self):
        r=search(make_model(self.d),self.f,max_expansions=0);self.assertEqual(r.status,'SEARCH_LIMIT_NO_PLAN');self.assertFalse(r.certified)
    def test_repeatability(self):
        d,f,_=synthetic(23);m=make_model(d)
        for mode in ('P','B','D'):
            a=search(m,f,mode);b=search(m,f,mode);self.assertEqual(a.plan,b.plan)
            for k in ('expanded','enqueued','memory_pruned','complete_checked','feasible','stop_reason'):self.assertEqual(a.stats[k],b.stats[k])
if __name__=='__main__':unittest.main()
