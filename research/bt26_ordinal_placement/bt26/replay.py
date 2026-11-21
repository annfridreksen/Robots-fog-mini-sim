"""Execution replay with frozen routes/assignments and exogenous calendars.
No finite arrival queues or live replanning. Hidden calendars go only to executor.
"""
from fractions import Fraction as F
from .scheduler import Run,Hop,Transfer,Plan,earliest_slot,reserve,NoSchedule
from .verify import verify_plan

def replay(model,selected_plan):
    assignment=dict(selected_plan.assignment)
    if set(assignment)!=set(model.blocks):raise NoSchedule('assignment coverage changed')
    if any(d not in model.candidates[b] for b,d in assignment.items()):return {'status':'EXECUTION_UNAVAILABLE','plan':None,'violations':['assignment_unavailable'],'events':[]}
    template_runs={r.block:r for r in selected_plan.runs};template_messages={(t.src,t.dst):t for t in selected_plan.transfers}
    calendars={r:list(xs) for r,xs in model.busy.items()};runs={};transfers=[];events=[]
    for b in model.topo:
        d=assignment[b];ready=max(model.launch,model.release[b],template_runs[b].start)
        for a in model.predecessors[b]:
            t=template_messages[a,b];at=runs[a].end;current=assignment[a];hops=[]
            for old in t.hops:
                link=model.links.get(old.link)
                if link is None or not link.available or link.bps<=0 or link.src!=current or not model.devices[link.dst].available:
                    return {'status':'EXECUTION_UNAVAILABLE','plan':None,'violations':['route_unavailable'],'events':events}
                duration=F(model.messages[a,b])/link.bps;start=earliest_slot(calendars,link.resources,max(at,old.start),duration)
                end=start+duration;at=end+link.latency;reserve(calendars,link.resources,start,end)
                hops.append(Hop(link.id,start,end,at));current=link.dst
                events.extend([(start,'send_start',a+'->'+b,link.id),(at,'arrival',a+'->'+b,link.id)])
            if current!=d:raise NoSchedule('template endpoint mismatch')
            transfers.append(Transfer(a,b,model.messages[a,b],tuple(hops),at));ready=max(ready,at)
        duration=model.duration[b,d];start=earliest_slot(calendars,('cpu:'+d,),ready,duration);end=start+duration
        reserve(calendars,('cpu:'+d,),start,end);runs[b]=Run(b,d,start,end)
        events.extend([(start,'compute_start',b,d),(end,'compute_end',b,d)])
    p=Plan(model.fingerprint,selected_plan.assignment,tuple(runs[b] for b in model.blocks),tuple(transfers),max(r.end for r in runs.values()))
    errors=verify_plan(model,p)
    return {'status':'COMPLETED' if not errors else 'COMPLETED_WITH_VIOLATIONS','plan':p,'violations':list(errors),
        'events':[(str(t),kind,obj,r) for t,kind,obj,r in sorted(events)]}
