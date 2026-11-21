"""Validated graph/partition/resource contracts. Times are exact rational seconds.

This is a new research implementation, not the conference simulator.
No numeric value in examples is a measurement of real hardware.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
from collections import defaultdict
import hashlib
import json
import math
from typing import Any


class InputError(ValueError):
    """An input contract was violated, not a failed placement search."""


def q(value: Any, label: str = 'number') -> F:
    if isinstance(value, bool):
        raise InputError(f'{label}: boolean is not a number')
    try:
        result = F(str(value))
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise InputError(f'{label}: expected a finite rational number') from exc
    return result


def nonneg(value: Any, label: str) -> F:
    result = q(value, label)
    if result < 0:
        raise InputError(f'{label}: must be nonnegative')
    return result


def integer(value: Any, label: str) -> int:
    result = nonneg(value, label)
    if result.denominator != 1:
        raise InputError(f'{label}: must be an integer')
    return int(result)


def topo(vertices, edges):
    import heapq
    vertices = set(vertices)
    outgoing = {v: [] for v in vertices}
    degree = {v: 0 for v in vertices}
    for a, b in edges:
        if a not in vertices or b not in vertices or a == b:
            raise InputError('invalid directed edge')
        outgoing[a].append(b)
        degree[b] += 1
    heap = [v for v in vertices if degree[v] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        v = heapq.heappop(heap)
        order.append(v)
        for w in sorted(outgoing[v]):
            degree[w] -= 1
            if degree[w] == 0:
                heapq.heappush(heap, w)
    if len(order) != len(vertices):
        raise InputError('directed cycle')
    return tuple(order)


def weakly_connected(vertices, edges):
    vertices = set(vertices)
    if not vertices:
        return False
    graph = {v: set() for v in vertices}
    for a, b in edges:
        if a in vertices and b in vertices:
            graph[a].add(b)
            graph[b].add(a)
    todo = [min(vertices)]
    seen = set(todo)
    while todo:
        for w in graph[todo.pop()]:
            if w not in seen:
                seen.add(w)
                todo.append(w)
    return seen == vertices


@dataclass(frozen=True)
class Device:
    id: str
    layer: str
    memory: int
    available: bool
    features: frozenset[str]


@dataclass(frozen=True)
class Link:
    id: str
    src: str
    dst: str
    bps: F
    latency: F
    available: bool
    shared: tuple[str, ...]

    @property
    def resources(self):
        return ('net:' + self.id,) + self.shared


@dataclass
class Model:
    source: dict
    fingerprint: str
    blocks: tuple[str, ...]
    topo: tuple[str, ...]
    members: dict[str, tuple[str, ...]]
    devices: dict[str, Device]
    links: dict[str, Link]
    outgoing: dict[str, tuple[Link, ...]]
    memory: dict[str, int]
    duration: dict[tuple[str, str], F]
    candidates: dict[str, tuple[str, ...]]
    messages: dict[tuple[str, str], int]
    busy: dict[str, tuple[tuple[F, F], ...]]
    release: dict[str, F]
    deadline: F
    decision_time: F
    planning_delay: F
    apply_delay: F
    previous: dict[str, str] | None
    partition_version: str
    task_class: str
    load_scope: str

    @property
    def launch(self):
        return self.planning_delay + self.apply_delay

    @property
    def predecessors(self):
        return {b: tuple(sorted(a for a, z in self.messages if z == b))
                for b in self.blocks}


def _make_model(data: dict) -> Model:
    """Make a self-contained snapshot. No mutation of caller data.

    Missing execution profiles remove a device from a block's candidates;
    they are never interpreted as zero duration. An empty candidate set is
    a legitimate no-plan search outcome. Structural errors raise InputError.
    """
    data = json.loads(json.dumps(data, allow_nan=False))
    for field in ('task_version', 'partition_version', 'infrastructure_version', 'task_class', 'load_scope'):
        if not isinstance(data.get(field), str) or not data[field]:
            raise InputError(f'missing {field}')
    devices = {}
    for d in data.get('devices', []):
        name = d['id']
        if not isinstance(name, str) or not name or name in devices:
            raise InputError('invalid/duplicate device id')
        layer = d.get('layer')
        if layer not in ('edge', 'fog', 'cloud', 'router'):
            raise InputError('unknown device layer')
        if type(d.get('available', True)) is not bool:
            raise InputError('device availability must be Boolean')
        devices[name] = Device(name, layer, integer(d['memory_bytes'], 'memory'),
                               d.get('available', True), frozenset(d.get('features', [])))
    if not devices:
        raise InputError('devices are empty')
    ops = {}
    for op in data.get('operations', []):
        name = op['id']
        if not isinstance(name, str) or not name or name in ops:
            raise InputError('invalid/duplicate operation id')
        profiles = {}
        for k, v in op.get('duration_s', {}).items():
            if k not in devices:
                raise InputError('profile references unknown device')
            if v is not None:
                profiles[k] = nonneg(v, 'execution time')
        allowed = op.get('allowed_devices', list(devices))
        if not isinstance(allowed, list) or not set(allowed) <= devices.keys():
            raise InputError('invalid allowed_devices')
        ops[name] = (integer(op['memory_bytes'], 'operation memory'), profiles,
                     frozenset(op.get('requires', [])), frozenset(allowed))
    if not ops:
        raise InputError('operations are empty')
    arcs = {}
    for e in data.get('edges', []):
        key = (e['src'], e['dst'])
        if key in arcs:
            raise InputError('duplicate task edge; aggregate explicitly')
        arcs[key] = integer(e['bits'], 'message size')
    topo(ops, arcs)
    if not weakly_connected(ops, arcs):
        raise InputError('task graph is not weakly connected')
    members = {}
    owner = {}
    for b in data.get('blocks', []):
        name, items = b['id'], b['operations']
        if not isinstance(name, str) or not name or name in members or not items:
            raise InputError('invalid/duplicate/empty block')
        if len(set(items)) != len(items):
            raise InputError('repeated operation in block')
        for op in items:
            if op not in ops or op in owner:
                raise InputError('partition does not assign each operation once')
            owner[op] = name
        if not weakly_connected(items, arcs):
            raise InputError('block is not weakly connected')
        members[name] = topo(items, [(a,b) for a,b in arcs if a in items and b in items])
    if set(owner) != set(ops):
        raise InputError('partition does not cover graph')
    messages = defaultdict(int)
    for (a, b), size in arcs.items():
        if owner[a] != owner[b]:
            messages[owner[a], owner[b]] += size
    block_order = topo(members, messages)
    memory, durations, candidates = {}, {}, {}
    for b, items in members.items():
        memory[b] = sum(ops[v][0] for v in items)
        valid = []
        for d in sorted(devices):
            dev = devices[d]
            if (dev.layer not in ('edge', 'fog') or not dev.available or memory[b] > dev.memory):
                continue
            if all(d in ops[v][1] and ops[v][2] <= dev.features and d in ops[v][3] for v in items):
                durations[b,d] = sum((ops[v][1][d] for v in items), F(0))
                valid.append(d)
        candidates[b] = tuple(valid)
    links = {}
    outgoing = defaultdict(list)
    allowed_resources = {'cpu:'+d for d in devices}
    for e in data.get('links', []):
        name, a, b = e['id'], e['src'], e['dst']
        if not isinstance(name, str) or not name or name in links or a not in devices or b not in devices or a == b:
            raise InputError('invalid/duplicate network link')
        if type(e.get('available', True)) is not bool:
            raise InputError('link availability must be Boolean')
        shared = tuple(e.get('shared_resources', []))
        if len(set(shared)) != len(shared) or any(not isinstance(x,str) or not x.startswith('shared:') for x in shared):
            raise InputError('shared resource names must start with shared:')
        link = Link(name,a,b,nonneg(e['bandwidth_bps'],'bandwidth'),
                    nonneg(e.get('latency_s',0),'latency'),e.get('available',True),shared)
        links[name] = link
        outgoing[a].append(link)
        allowed_resources.update(link.resources)
    busy = {}
    for r, intervals in data.get('busy', {}).items():
        if r not in allowed_resources:
            raise InputError('unknown resource calendar: '+r)
        checked = []
        for interval in intervals:
            if len(interval) != 2:
                raise InputError('calendar interval requires two endpoints')
            a,b = [nonneg(x,'calendar endpoint') for x in interval]
            if b < a:
                raise InputError('negative calendar interval')
            if b > a:
                checked.append((a,b))
        checked.sort()
        if any(checked[i][1] > checked[i+1][0] for i in range(len(checked)-1)):
            raise InputError('overlapping external reservations')
        busy[r] = tuple(checked)
    release = {b: nonneg(data.get('release_s',{}).get(b,0),'release') for b in members}
    if not set(data.get('release_s',{})) <= members.keys():
        raise InputError('release references unknown block')
    previous = data.get('previous')
    if previous is not None:
        if data.get('previous_partition_version') != data['partition_version']:
            raise InputError('previous plan has a different partition version')
        if set(previous) != set(members) or not set(previous.values()) <= devices.keys():
            raise InputError('previous placement is incomplete/unknown')
    fingerprint = hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),
                                            ensure_ascii=False).encode()).hexdigest()
    return Model(data, fingerprint, tuple(sorted(members)), block_order, members, devices,
                 links, {d:tuple(sorted(outgoing[d],key=lambda l:l.id)) for d in devices},
                 memory,durations,candidates,dict(messages),busy,release,
                 nonneg(data['deadline_s'],'deadline'),nonneg(data.get('decision_time_s',0),'decision time'),
                 nonneg(data.get('planning_delay_s',0),'planning delay'),
                 nonneg(data.get('apply_delay_s',0),'application delay'),previous,
                 data['partition_version'], data['task_class'], data['load_scope'])



def make_model(data: dict) -> Model:
    """Validate the JSON boundary; malformed input is not a search failure."""
    if not isinstance(data, dict):
        raise InputError('problem must be a JSON object')
    try:
        return _make_model(data)
    except InputError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
        raise InputError(f'malformed problem: {exc}') from exc



def prepare_forecast(model: Model, forecast: dict | None):
    """Validate an external interface, not forecast accuracy; no learning here."""
    if forecast is None:
        return None, 'absent'
    if not isinstance(forecast, dict) or not isinstance(forecast.get('commands'), dict):
        return None, 'invalid_contract'
    if (forecast.get('kind') not in ('synthetic_control','external_neural','external_ordinal')
        or not forecast.get('provenance') or not forecast.get('scale_id')
        or forecast.get('direction') != 'smaller_is_preferred'
        or forecast.get('task_class') != model.task_class
        or forecast.get('load_scope') != model.load_scope
        or forecast.get('partition_version') != model.partition_version):
        return None, 'incompatible_contract'
    try:
        start = nonneg(forecast['issued_at_s'],'issued_at')
        end = nonneg(forecast['valid_until_s'],'valid_until')
        if not start <= model.decision_time < end:
            return None, 'not_current'
        relevant = set(d for ds in model.candidates.values() for d in ds)
        if not relevant <= forecast.get('commands',{}).keys():
            return None, 'incomplete'
        commands = {d:q(forecast['commands'][d], 'ordinal command') for d in relevant}
    except (KeyError,InputError):
        return None, 'invalid_values'
    if len(set(commands.values())) <= 1:
        return None, 'constant'
    return commands, forecast['kind']
