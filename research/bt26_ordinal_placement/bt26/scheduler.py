"""Deterministic non-preemptive blocks and store-and-forward messages."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from fractions import Fraction as F
import heapq
from .model import Model
class NoSchedule(ValueError):pass
@dataclass(frozen=True)
class Run:
    block:str;device:str;start:F;end:F
@dataclass(frozen=True)
class Hop:
    link:str;start:F;end:F;arrival:F
@dataclass(frozen=True)
class Transfer:
    src:str;dst:str;bits:int;hops:tuple[Hop,...];arrival:F
@dataclass(frozen=True)
class Plan:
    fingerprint:str;assignment:tuple[tuple[str,str],...];runs:tuple[Run,...];transfers:tuple[Transfer,...];makespan:F
    @property
    def identifier(self):return tuple(d for _,d in self.assignment)

def earliest_slot(calendars,resources,ready,duration):
    if duration==0:return ready
    t=ready
    for a,b in sorted(x for r in resources for x in calendars.get(r,())):
        if b<=t:continue
        if t+duration<=a:return t
        if t<b and a<t+duration:t=b
    return t

def reserve(calendars,resources,start,end):
    if end==start:return
    for r in resources:calendars.setdefault(r,[]).append((start,end));calendars[r].sort()

def earliest_route(model,calendars,src,dst,ready,bits):
    if src==dst:return (),ready
    if not model.devices[src].available or not model.devices[dst].available:raise NoSchedule('unavailable route endpoint')
    distance={src:ready};previous={};queue=[(ready,src)];settled=set()
    while queue:
        at,u=heapq.heappop(queue)
        if u in settled:continue
        settled.add(u)
        if u==dst:
            route=[]
            while u!=src:u,hop=previous[u];route.append(hop)
            return tuple(reversed(route)),at
        for link in model.outgoing[u]:
            if not link.available or link.bps<=0 or link.dst in settled or not model.devices[link.dst].available:continue
            duration=F(bits)/link.bps;start=earliest_slot(calendars,link.resources,at,duration);end=start+duration;arrival=end+link.latency
            if link.dst not in distance or arrival<distance[link.dst]:
                distance[link.dst]=arrival;previous[link.dst]=(u,Hop(link.id,start,end,arrival));heapq.heappush(queue,(arrival,link.dst))
    raise NoSchedule('no permitted directed path')

def build_plan(model,assignment):
    if set(assignment)!=set(model.blocks):raise NoSchedule('partial or surplus assignment')
    usage={d:0 for d in model.devices}
    for b,d in assignment.items():
        if d not in model.candidates[b]:raise NoSchedule('incompatible assignment or missing profile')
        usage[d]+=model.memory[b]
    if any(usage[d]>model.devices[d].memory for d in usage):raise NoSchedule('joint memory exceeded')
    calendars={r:list(xs) for r,xs in model.busy.items()};runs={};transfers=[]
    for b in model.topo:
        ready=max(model.launch,model.release[b]);d=assignment[b]
        for a in model.predecessors[b]:
            bits=model.messages[a,b];hops,arrival=earliest_route(model,calendars,assignment[a],d,runs[a].end,bits)
            for h in hops:reserve(calendars,model.links[h.link].resources,h.start,h.end)
            transfers.append(Transfer(a,b,bits,hops,arrival));ready=max(ready,arrival)
        duration=model.duration[b,d];start=earliest_slot(calendars,('cpu:'+d,),ready,duration);end=start+duration
        reserve(calendars,('cpu:'+d,),start,end);runs[b]=Run(b,d,start,end)
    return Plan(model.fingerprint,tuple(sorted(assignment.items())),tuple(runs[b] for b in model.blocks),tuple(transfers),max(r.end for r in runs.values()))

def plan_to_dict(plan):
    if plan is None:return None
    def convert(x):
        if isinstance(x,F):return str(x)
        if isinstance(x,dict):return {k:convert(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [convert(v) for v in x]
        return x
    return convert(asdict(plan))

def plan_from_dict(d):
    return Plan(d['fingerprint'],tuple(tuple(x) for x in d['assignment']),
        tuple(Run(x['block'],x['device'],F(x['start']),F(x['end'])) for x in d['runs']),
        tuple(Transfer(x['src'],x['dst'],x['bits'],tuple(Hop(h['link'],F(h['start']),F(h['end']),F(h['arrival'])) for h in x['hops']),F(x['arrival'])) for x in d['transfers']),F(d['makespan']))
