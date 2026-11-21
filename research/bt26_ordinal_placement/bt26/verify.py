"""Independent invariant checker: it does NOT call the schedule generator.

Checks feasibility, not earliest-start optimality or completeness of search.
It deliberately rederives resource occupancy from the supplied plan.
"""
from collections import defaultdict
from fractions import Fraction as F
from .model import Model
from .scheduler import Plan


def verify_plan(model: Model, plan: Plan) -> tuple[str, ...]:
    errors = []
    if plan.fingerprint != model.fingerprint:
        errors.append('snapshot_mismatch')
    assignments = dict(plan.assignment)
    runs = {r.block:r for r in plan.runs}
    if len(assignments) != len(plan.assignment) or set(assignments) != set(model.blocks):
        return tuple(errors+['assignment_coverage'])
    if len(runs) != len(plan.runs) or set(runs) != set(model.blocks):
        return tuple(errors+['run_coverage'])
    memory = defaultdict(int)
    reservations = defaultdict(list)
    for r,xs in model.busy.items():
        for a,b in xs:
            reservations[r].append((a,b,'external'))
    for b in model.blocks:
        d = assignments[b]
        run = runs[b]
        if d not in model.candidates[b] or run.device != d:
            errors.append('incompatible:'+b)
            continue
        if run.start < max(model.launch,model.release[b]) or run.end < run.start:
            errors.append('release:'+b)
        if run.end-run.start != model.duration[b,d]:
            errors.append('duration:'+b)
        memory[d] += model.memory[b]
        if run.end > run.start:
            reservations['cpu:'+d].append((run.start,run.end,'block:'+b))
    for d,total in memory.items():
        if total > model.devices[d].memory:
            errors.append('memory:'+d)
    byedge = {(t.src,t.dst):t for t in plan.transfers}
    if len(byedge) != len(plan.transfers) or set(byedge) != set(model.messages):
        return tuple(errors+['message_coverage'])
    for (a,b),bits in model.messages.items():
        transfer = byedge[a,b]
        if transfer.bits != bits:
            errors.append('message_size:'+a+'->'+b)
        src,dst = assignments[a],assignments[b]
        ready = runs[a].end
        current = src
        visited = {src}
        if src == dst and transfer.hops:
            errors.append('nonempty_local_route')
        if src != dst and not transfer.hops:
            errors.append('missing_route')
        for hop in transfer.hops:
            link = model.links.get(hop.link)
            if link is None or link.src != current:
                errors.append('route_continuity')
                break
            if not link.available or link.bps <= 0 or not model.devices[link.dst].available:
                errors.append('route_unavailable')
                break
            if link.dst in visited:
                errors.append('cyclic_route')
            visited.add(link.dst)
            if hop.start < ready or hop.start < 0:
                errors.append('message_readiness')
            if hop.end-hop.start != F(bits)/link.bps:
                errors.append('serialization_duration')
            if hop.arrival != hop.end+link.latency:
                errors.append('propagation_delay')
            if hop.end > hop.start:
                for resource in link.resources:
                    reservations[resource].append((hop.start,hop.end,'message:'+a+'->'+b))
            current,ready = link.dst,hop.arrival
        if current != dst:
            errors.append('route_destination')
        if transfer.arrival != ready:
            errors.append('arrival_mismatch')
        if runs[b].start < transfer.arrival:
            errors.append('precedence:'+a+'->'+b)
    for resource, intervals in reservations.items():
        ordered = sorted(intervals)
        for i in range(1,len(ordered)):
            if ordered[i][0] < ordered[i-1][1]:
                errors.append('resource_conflict:'+resource)
    if plan.makespan != max(r.end for r in runs.values()):
        errors.append('makespan_mismatch')
    if plan.makespan > model.deadline:
        errors.append('deadline')
    return tuple(sorted(set(errors)))
