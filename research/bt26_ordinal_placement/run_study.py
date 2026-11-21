"""Reproduce synthetic diagnostics. No neural model is trained or claimed."""
from pathlib import Path
from fractions import Fraction as F
from itertools import product
import argparse,copy,csv,hashlib,json,platform,random,statistics,sys,time
from bt26 import make_model,search,reference,reconsider,verify_plan
from bt26.scheduler import build_plan,NoSchedule,plan_to_dict
from bt26.replay import replay
ROOT=Path(__file__).resolve().parent

def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def synthetic(seed):
    rng=random.Random(seed);nodes=['E','F1','F2']
    d={'data_status':'SYNTHETIC_DIAGNOSTIC_NOT_REAL_MEASUREMENTS','task_version':f'synthetic-{seed}',
       'partition_version':'four-pairs-v1','infrastructure_version':f'snapshot-{seed}',
       'task_class':'synthetic-four-blocks','load_scope':'synthetic-four-blocks-empty-calendars-v1',
       'decision_time_s':'0','planning_delay_s':'0','apply_delay_s':'0','deadline_s':'0.060',
       'devices':[{'id':x,'layer':'edge' if x=='E' else 'fog','memory_bytes':6000000} for x in nodes],
       'operations':[],'blocks':[],'edges':[],'links':[],'busy':{}}
    for i in range(4):
        profiles=[{x:str(F(rng.randint(1,7),1000)) for x in nodes} for _ in range(2)]
        for j in range(2):d['operations'].append({'id':f'v{i}{j}','memory_bytes':1000000,'duration_s':profiles[j]})
        d['blocks'].append({'id':f'B{i}','operations':[f'v{i}0',f'v{i}1']})
        d['edges'].append({'src':f'v{i}0','dst':f'v{i}1','bits':0})
        if i:d['edges'].append({'src':f'v{i-1}1','dst':f'v{i}0','bits':rng.choice([4000,8000,16000])})
    if seed%2:d['edges'].append({'src':'v01','dst':'v30','bits':4000})
    for a in nodes:
        for b in nodes:
            if a!=b:d['links'].append({'id':a+'_'+b,'src':a,'dst':b,'bandwidth_bps':8000000,'latency_s':'0.0002'})
    h={x:rng.randint(0,16) for x in nodes}
    f={'data_status':'SYNTHETIC_HISTORICAL_RANK_NOT_NEURAL','kind':'synthetic_control',
       'provenance':f'predecision historical observations; seed {seed}','task_class':d['task_class'],
       'partition_version':d['partition_version'],'load_scope':d['load_scope'],
       'scale_id':'historical-busy-order','direction':'smaller_is_preferred','issued_at_s':'0','valid_until_s':'1',
       'commands':{x:1+sum(h[y]<h[x] for y in nodes) for x in nodes}}
    return d,f,h

def study(seeds,out):
    out.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
    f=json.loads((ROOT/'examples/forecast.json').read_text());controls={}
    for name in ['minimal','no_feasible','deadline_filter','failed_node']:
        m=make_model(json.loads((ROOT/f'examples/{name}.json').read_text()))
        controls[name]={mode:search(m,f,mode).to_dict() for mode in ['P','B','D']}
    m=make_model(json.loads((ROOT/'examples/minimal.json').read_text()));rows=[]
    for vals in product(['E','F'],repeat=3):
        a=dict(zip(m.blocks,vals))
        try:
            p=build_plan(m,a);rows.append({'assignment':a,'duration_ms':float(p.makespan*1000),'violations':verify_plan(m,p),'plan':plan_to_dict(p)})
        except NoSchedule as ex:rows.append({'assignment':a,'rejection':str(ex)})
    controls['enumerated_minimal']=rows;dump(out/'control_results.json',controls)
    mm=make_model(json.loads((ROOT/'examples/replan.json').read_text()));dump(out/'replan_result.json',reconsider(mm,mm.previous,f))
    comparisons=[];records=[];budgets=[];inputs=[];selected=[];traces=[]
    for seed in range(seeds):
        d,f,h=synthetic(seed);m=make_model(d);inputs.append({'seed':seed,'problem':d,'forecast':f,'history':h})
        results={mode:search(m,f,mode) for mode in ['P','B','D']}
        for mode,r in results.items():
            ref,n,k=reference(m,f,mode)
            assert r.plan==ref,(seed,mode,'reference mismatch')
            selected.append({'seed':seed,'method':mode,'result':r.to_dict()})
            comparisons.append({'seed':seed,'method':mode,'matches_reference':r.plan==ref,
              'reference_assignments':n,'reference_feasible':k,'checks':r.stats['complete_checked'],
              'expanded':r.stats['expanded'],'elapsed_seconds':r.stats['elapsed_seconds'],
              'schedule_seconds':r.stats['schedule_seconds'],'verify_seconds':r.stats['verify_seconds'],
              'status':r.status,'plan_id':','.join(r.plan.identifier) if r.plan else '',
              'planned_ms':float(r.plan.makespan*1000) if r.plan else None})
        assert results['P'].plan==results['D'].plan
        for cap in (1,4,16):
            for mode in ['P','D']:
                r=search(m,f,mode,max_checks=cap,early_stop=False)
                budgets.append({'seed':seed,'method':mode,'budget':cap,'checks':r.stats['complete_checked'],
                    'expanded':r.stats['expanded'],'status':r.status,'matches_full_choice':r.plan==results['P'].plan,
                    'plan_found':r.plan is not None,'elapsed_seconds':r.stats['elapsed_seconds']})
        for regime in ['persistent','reversed','constant_commands']:
            actual=copy.deepcopy(d);load=h if regime!='reversed' else {x:16-v for x,v in h.items()}
            actual['busy']={'cpu:'+x:[['0',str(F(v,1000))]] for x,v in load.items() if v}
            actual['infrastructure_version']=f'replay-{seed}-{regime}';am=make_model(actual);ff=copy.deepcopy(f)
            if regime=='constant_commands':ff['commands']={x:1 for x in h}
            for mode in ['P','B']:
                r=search(m,ff,mode)
                if r.plan is None:
                    records.append({'seed':seed,'regime':regime,'method':mode,'plan_found':False,'completed':False,'deadline_met':False,'actual_ms':None,'planned_ms':None});continue
                ex=replay(am,r.plan);ep=ex['plan']
                if ep is not None:assert not any(x!='deadline' for x in ex['violations']),ex['violations']
                traces.append({'seed':seed,'regime':regime,'method':mode,'planned':plan_to_dict(r.plan),
                    'executed':plan_to_dict(ep),'events':ex['events'],'violations':ex['violations'],'background':actual['busy']})
                records.append({'seed':seed,'regime':regime,'method':mode,'plan_found':True,'completed':ep is not None,
                    'deadline_met':ep is not None and not ex['violations'],'actual_ms':float(ep.makespan*1000) if ep else None,
                    'planned_ms':float(r.plan.makespan*1000),'plan_id':','.join(r.plan.identifier)})
    def csvsave(name,rows):
        fields=list(dict.fromkeys(k for row in rows for k in row))
        with (out/name).open('w',encoding='utf-8',newline='') as fp:
            w=csv.DictWriter(fp,fieldnames=fields);w.writeheader();w.writerows(rows)
    csvsave('reference_comparison.csv',comparisons);csvsave('order_ablation.csv',budgets);csvsave('replay_results.csv',records)
    dump(out/'synthetic_inputs.json',inputs);dump(out/'selected_plans.json',selected);dump(out/'execution_traces.json',traces)
    agg={}
    for mode in ['P','B','D']:
        rr=[x for x in comparisons if x['method']==mode]
        agg[mode]={'runs':len(rr),'reference_matches':sum(x['matches_reference'] for x in rr),
                  'mean_checks':statistics.mean(x['checks'] for x in rr),'mean_expanded':statistics.mean(x['expanded'] for x in rr),
                  'median_elapsed_ms':statistics.median(x['elapsed_seconds']*1000 for x in rr)}
    abl={str(cap):{mode:{'found':sum(x['plan_found'] for x in budgets if x['budget']==cap and x['method']==mode),
        'matches_full':sum(x['matches_full_choice'] for x in budgets if x['budget']==cap and x['method']==mode)} for mode in ['P','D']} for cap in (1,4,16)}
    rep={}
    for regime in ['persistent','reversed','constant_commands']:
        diff=[]
        for seed in range(seeds):
            pair=[x for x in records if x['seed']==seed and x['regime']==regime]
            p=next(x for x in pair if x['method']=='P');b=next(x for x in pair if x['method']=='B')
            if p['actual_ms'] is not None and b['actual_ms'] is not None:diff.append(p['actual_ms']-b['actual_ms'])
        modes={mode:{'mean_actual_ms':statistics.mean(x['actual_ms'] for x in records if x['regime']==regime and x['method']==mode and x['actual_ms'] is not None),
            'deadline_met':sum(x['deadline_met'] for x in records if x['regime']==regime and x['method']==mode)} for mode in ['P','B']}
        rep[regime]={'methods':modes,'paired_runs':len(diff),'mean_P_minus_B_ms':statistics.mean(diff),
                    'P_faster':sum(x<0 for x in diff),'ties':sum(x==0 for x in diff),'P_slower':sum(x>0 for x in diff)}
    summary={'data_status':'ALL_NEW_INPUTS_SYNTHETIC; NO_NEURAL_NETWORK_EVALUATED','seed_range':[0,seeds-1],
             'reference':agg,'order_ablation':abl,'replay':rep,'elapsed_seconds':time.perf_counter()-start,
             'interpretation':'Diagnostics in a finite synthetic class; not universal superiority or real-neural forecast validation.'}
    dump(out/'summary.json',summary)
    dump(out/'environment.json',{'python':sys.version,'platform':platform.platform(),'date':'2026-11-21',
         'command':f'python run_study.py --seeds {seeds} --out {out}',
         'units':'seconds, exact Fraction arithmetic; summary in ms','randomness':'independent random.Random(seed), seeds0..59',
         'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*.py')) if '__pycache__' not in str(p)}})
    print(json.dumps(summary,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seeds',type=int,default=60);p.add_argument('--out',type=Path,default=ROOT/'results');a=p.parse_args()
    if not 1<=a.seeds<=10000:p.error('seeds between1 and10000')
    study(a.seeds,a.out)
