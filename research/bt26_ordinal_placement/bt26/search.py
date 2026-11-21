"""Ordinal criterion with lazy optimistic-prefix search; worst case exponential."""
from dataclasses import dataclass
from itertools import product
from collections import Counter
from time import perf_counter
import heapq,math
from .model import InputError,prepare_forecast
from .scheduler import NoSchedule,build_plan,plan_to_dict
from .verify import verify_plan

@dataclass
class Result:
    status:str;method:str;forecast_status:str;plan:object;certified:bool;stats:dict;rejected:dict
    def to_dict(self):return dict(status=self.status,method=self.method,forecast_status=self.forecast_status,plan=plan_to_dict(self.plan),certified=self.certified,stats=self.stats,rejected=self.rejected)

def command_vector(assignment,commands):return tuple(sorted((commands[d] for _,d in sorted(assignment.items())),reverse=True))
def moves(model,assignment):return 0 if model.previous is None else sum(assignment[b]!=model.previous[b] for b in model.blocks)
def key(model,plan,commands=None):
    a=dict(plan.assignment);suffix=(plan.makespan,moves(model,a),plan.identifier)
    return (command_vector(a,commands),)+suffix if commands is not None else suffix

def search(model,forecast=None,method='P',*,max_checks=None,max_expansions=None,max_seconds=None,early_stop=True):
    """P: ordinal criterion/order; D: same criterion, neutral order; B: time.
    Time budgets are cooperative, checked between operations, not hard deadlines.
    A certificate concerns assignments under this schedule builder only.
    """
    if method not in ('P','B','D'):raise InputError('method must be P/B/D')
    for v in (max_checks,max_expansions):
        if v is not None and (type(v) is not int or v<0):raise InputError('invalid search limit')
    if max_seconds is not None and (not math.isfinite(max_seconds) or max_seconds<0):raise InputError('invalid time budget')
    started=perf_counter();commands,reason=prepare_forecast(model,forecast) if method!='B' else (None,'not_used')
    effective=method if commands is not None else 'B'
    stats=dict(expanded=0,enqueued=0,memory_pruned=0,complete_checked=0,feasible=0,peak_frontier=0,schedule_seconds=0.0,verify_seconds=0.0)
    rejected=Counter();best=None;certified=False;stop='exhausted'
    if any(not model.candidates[b] for b in model.blocks):
        stats['elapsed_seconds']=perf_counter()-started;stats['stop_reason']='empty_candidates'
        stats['preparation_and_search_seconds']=stats['elapsed_seconds']
        return Result('NO_PLAN_IN_CLASS',effective,reason,None,True,stats,{'empty_candidates':1})
    def bound(prefix):
        if effective!='P':return ()
        values=[commands[d] for d in prefix]+[min(commands[d] for d in model.candidates[b]) for b in model.blocks[len(prefix):]]
        return tuple(sorted(values,reverse=True))
    frontier=[(bound(()),())];stats['enqueued']=1
    while frontier:
        stats['peak_frontier']=max(stats['peak_frontier'],len(frontier))
        if effective=='P' and early_stop and best is not None and frontier[0][0]>key(model,best,commands)[0]:
            certified,stop=True,'ordinal_bound';break
        if max_seconds is not None and perf_counter()-started>=max_seconds:stop='time_budget';break
        if max_expansions is not None and stats['expanded']>=max_expansions:stop='expansion_budget';break
        lb,prefix=heapq.heappop(frontier);stats['expanded']+=1
        if len(prefix)==len(model.blocks):
            if max_checks is not None and stats['complete_checked']>=max_checks:stop='check_budget';break
            assignment=dict(zip(model.blocks,prefix));stats['complete_checked']+=1;tick=perf_counter()
            try:plan=build_plan(model,assignment)
            except NoSchedule as exc:
                stats['schedule_seconds']+=perf_counter()-tick;rejected[str(exc)]+=1;continue
            stats['schedule_seconds']+=perf_counter()-tick;tick=perf_counter();violations=verify_plan(model,plan)
            stats['verify_seconds']+=perf_counter()-tick
            if violations:rejected.update(violations);continue
            stats['feasible']+=1
            if best is None or key(model,plan,commands)<key(model,best,commands):best=plan
            continue
        b=model.blocks[len(prefix)];used=Counter()
        for old,d in zip(model.blocks,prefix):used[d]+=model.memory[old]
        for d in model.candidates[b]:
            if used[d]+model.memory[b]>model.devices[d].memory:stats['memory_pruned']+=1;continue
            child=prefix+(d,);heapq.heappush(frontier,(bound(child),child));stats['enqueued']+=1
    else:certified=True
    stats['stop_reason']=stop;stats['elapsed_seconds']=perf_counter()-started
    stats['preparation_and_search_seconds']=max(0.0,stats['elapsed_seconds']-stats['schedule_seconds']-stats['verify_seconds'])
    status=('FEASIBLE_CERTIFIED' if certified else 'FEASIBLE_LIMITED') if best else ('NO_PLAN_IN_CLASS' if certified else 'SEARCH_LIMIT_NO_PLAN')
    return Result(status,effective,reason,best,certified,stats,dict(rejected))

def reference(model,forecast=None,method='P'):
    """Cartesian assignment enumeration; same fixed scheduler, not all schedules."""
    commands,_=prepare_forecast(model,forecast) if method!='B' else (None,'not_used')
    best=None;checked=0;feasible=0
    for values in product(*(model.candidates[b] for b in model.blocks)):
        checked+=1
        try:plan=build_plan(model,dict(zip(model.blocks,values)))
        except NoSchedule:continue
        if verify_plan(model,plan):continue
        feasible+=1
        if best is None or key(model,plan,commands)<key(model,best,commands):best=plan
    return best,checked,feasible

def reconsider(model,previous_assignment,forecast=None,old_forecast=None,*,allow_preference_change=False,**limits):
    """Safe-point reassignment only: no live migration and no repartition."""
    if model.previous is None or previous_assignment!=model.previous:raise InputError('previous assignment contract mismatch')
    old_cmd,_=prepare_forecast(model,old_forecast);new_cmd,_=prepare_forecast(model,forecast)
    def relation(cmd):
        if cmd is None:return None
        ids=sorted(cmd);return tuple((a,b,(cmd[a]>cmd[b])-(cmd[a]<cmd[b])) for a in ids for b in ids)
    try:old_plan=build_plan(model,previous_assignment);old_ok=not verify_plan(model,old_plan)
    except NoSchedule:old_plan,old_ok=None,False
    if old_ok and (not allow_preference_change or relation(old_cmd)==relation(new_cmd)):
        return {'action':'KEEP','plan':plan_to_dict(old_plan),'reason':'feasible_previous_assignment'}
    result=search(model,forecast,'P',**limits)
    return {'action':'RESELECT' if result.plan is not None else 'NO_PLAN','reason':'required_or_explicitly_authorized_reselection','search':result.to_dict()}
