"""CPU scheduling generator — FCFS / SJF / SRTF / Round Robin.

Two independent solvers (ADR 8):
  A = unit-step simulation (advance one tick at a time)
  B = event/segment driven (arithmetic jumps between events)
Both implement the documented tie-break rules exactly:
  * FCFS order: (arrival, input index)
  * SJF: smallest burst among arrived (tie: input index); non-preemptive
  * SRTF: argmin (remaining, input index) among arrived incomplete at every event
  * RR: ready queue FIFO; arrivals at time t enqueue before the process whose
    quantum expired at t; quantum expiry / completion trigger rescheduling.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from ..protocol import BaseGenerator, MistakeModel, Step, register

MODES = ("fcfs", "sjf", "srtf", "rr")
MODE_LABEL = {
    "fcfs": "FCFS",
    "sjf": "SJF (non-preemptive)",
    "srtf": "Shortest remaining time first (preemptive)",
    "rr": "Round robin",
}
METRIC_LABEL = {"waiting": "average waiting time", "turnaround": "average turnaround time"}


# --- solver A: unit-step -----------------------------------------------------

def _simulate_units(params: dict) -> tuple[list[int], list[tuple[int, int, int]]]:
    """Returns (completion times, timeline segments [(start, end, pid)])."""
    mode = params["mode"]
    procs = params["processes"]
    n = len(procs)
    at = [p["at"] for p in procs]
    bt = [p["bt"] for p in procs]
    rem = bt[:]
    ct = [0] * n
    enrolled = [False] * n
    ready: deque[int] = deque()
    running: int | None = None
    q_left = 0
    preempted_at_boundary: int | None = None
    finished = 0
    t = 0
    segments: list[tuple[int, int, int]] = []
    seg_start: int | None = None

    while finished < n:
        if t > 100_000:
            raise RuntimeError("simulation ran away")
        # (a) enroll arrivals at t, in input order
        for i in range(n):
            if at[i] == t and not enrolled[i]:
                enrolled[i] = True
                if i != running:
                    ready.append(i)
        # (b) a process whose quantum expired at boundary t joins after arrivals
        if preempted_at_boundary is not None:
            ready.append(preempted_at_boundary)
            preempted_at_boundary = None

        # (c) select
        if running is None and ready:
            if mode == "fcfs":
                running = ready.popleft()
                q_left = 10**9
            elif mode == "rr":
                running = ready.popleft()
                q_left = params["quantum"]
            elif mode == "sjf":
                running = min(ready, key=lambda i: (bt[i], i))
                ready.remove(running)
                q_left = 10**9
            elif mode == "srtf":
                candidates = list(ready) + [running] if running is not None else list(ready)
                best = min(candidates, key=lambda i: (rem[i], i))
                if best != running:
                    if running is not None:
                        ready.append(running)
                    if best in ready:
                        ready.remove(best)
                    running = best
                q_left = 10**9
            seg_start = t
        elif mode == "srtf" and running is not None and ready:
            # preemptive re-check every tick (invariant keeps it at events only)
            best = min(list(ready) + [running], key=lambda i: (rem[i], i))
            if best != running:
                if seg_start is not None:
                    segments.append((seg_start, t, running))
                    seg_start = None
                ready.append(running)
                ready.remove(best)
                running = best
                seg_start = t

        if running is None:
            t += 1
            continue

        # (d) run exactly one tick
        rem[running] -= 1
        q_left -= 1
        done = rem[running] == 0
        quantum_out = mode == "rr" and q_left == 0 and not done
        if done:
            ct[running] = t + 1
            finished += 1
            if seg_start is not None:
                segments.append((seg_start, t + 1, running))
                seg_start = None
            running = None
        elif quantum_out:
            if seg_start is not None:
                segments.append((seg_start, t + 1, running))
                seg_start = None
            preempted_at_boundary = running
            running = None
        t += 1

    return ct, segments


# --- solver B: event / segment driven ---------------------------------------

def _simulate_events(params: dict) -> list[int]:
    mode = params["mode"]
    procs = params["processes"]
    n = len(procs)
    at = [p["at"] for p in procs]
    bt = [p["bt"] for p in procs]
    rem = bt[:]
    ct = [0] * n
    done = [False] * n
    t = 0
    completed = 0
    guard = 0
    while completed < n:
        guard += 1
        if guard > 10_000:
            raise RuntimeError("event sim ran away")
        arrived = [i for i in range(n) if at[i] <= t and not done[i]]
        if not arrived:
            t = min(at[i] for i in range(n) if not done[i])
            continue
        if mode == "fcfs":
            # arithmetic: strictly (at, index) order
            order = sorted(range(n), key=lambda i: (at[i], i))
            for i in order:
                t = max(t, at[i])
                t += bt[i]
                ct[i] = t
            return ct
        if mode == "sjf":
            i = min(arrived, key=lambda j: (bt[j], j))
            t += rem[i]
            ct[i] = t
            done[i] = True
            completed += 1
            continue
        if mode == "srtf":
            i = min(arrived, key=lambda j: (rem[j], j))
            next_arrival = min((at[j] for j in range(n) if at[j] > t and not done[j]), default=None)
            run_to = t + rem[i]
            if next_arrival is not None and next_arrival < run_to:
                rem[i] -= next_arrival - t  # partial run before the arrival event
                t = next_arrival
                continue
            t = run_to
            ct[i] = t
            done[i] = True
            completed += 1
            continue
        raise ValueError(mode)
    return ct


def _rr_events(params: dict) -> list[int]:
    """Clean event-based RR (no function-attribute hacks)."""
    procs = params["processes"]
    n = len(procs)
    at = [p["at"] for p in procs]
    bt = [p["bt"] for p in procs]
    rem = bt[:]
    ct = [0] * n
    done = [False] * n
    q: deque[int] = deque()
    t = 0
    completed = 0
    enrolled = [False] * n
    while completed < n:
        for i in range(n):
            if at[i] <= t and not enrolled[i] and not done[i]:
                enrolled[i] = True
                q.append(i)
        if not q:
            t = min((at[i] for i in range(n) if not done[i]), default=t + 1)
            continue
        i = q.popleft()
        start = max(t, at[i])
        t = start
        dur = min(rem[i], params["quantum"])
        seg_end = t + dur
        for j in range(n):
            if t < at[j] <= seg_end and not enrolled[j] and not done[j]:
                enrolled[j] = True
                q.append(j)
        t = seg_end
        rem[i] -= dur
        if rem[i] == 0:
            ct[i] = t
            done[i] = True
            completed += 1
        else:
            q.append(i)
    return ct


def _metrics(params: dict, ct: list[int]) -> dict[str, float]:
    procs = params["processes"]
    wts = [ct[i] - procs[i]["at"] - procs[i]["bt"] for i in range(len(procs))]
    tats = [ct[i] - procs[i]["at"] for i in range(len(procs))]
    return {
        "waiting": sum(wts) / len(wts),
        "turnaround": sum(tats) / len(tats),
        "_waiting_each": wts,  # type: ignore[dict-item]
        "_turnaround_each": tats,  # type: ignore[dict-item]
        "_ct": ct,  # type: ignore[dict-item]
    }


def solve(params: dict, which: str) -> float:
    """which='a' → unit-step simulation (all modes); which='b' → event-driven."""
    if which == "a":
        ct, _ = _simulate_units(params)
    else:
        ct = _rr_events(params) if params["mode"] == "rr" else _simulate_events(params)
    m = _metrics(params, ct)
    return round(m[params["metric"]], 2)


class CpuScheduling(BaseGenerator):
    id = "os.cpu_scheduling"
    title = "CPU scheduling"
    node_ids = ["os.scheduling.fcfs", "os.scheduling.sjf", "os.scheduling.srtf", "os.scheduling.rr"]
    input_spec = {"kind": "number", "placeholder": "e.g. 4.67", "hint": "two decimal places"}
    hints = [
        "Draw the Gantt chart: mark every arrival on the time axis first.",
        "Waiting time = completion − arrival − burst for each process, then average.",
        "Remember the tie-break: equal bursts → earlier arrival (input order) goes first.",
        "Work one process at a time and keep a running clock — don't compute in parallel.",
    ]

    _NODE_FOR = {
        "fcfs": "os.scheduling.fcfs",
        "sjf": "os.scheduling.sjf",
        "srtf": "os.scheduling.srtf",
        "rr": "os.scheduling.rr",
    }

    def sample(self, rng, difficulty: int) -> dict[str, Any]:
        mode = rng.choice(MODES if difficulty >= 3 else ["fcfs", "sjf", "rr"])
        n = 3 + (1 if difficulty >= 3 else 0) + (1 if difficulty >= 5 else 0)
        n = min(n, 5)
        procs = []
        total = 0
        for i in range(n):
            bt = rng.randint(3, 6 + difficulty)
            at = rng.randint(0, max(1, total // 2)) if i else 0
            procs.append({"pid": f"P{i}", "at": at, "bt": bt, "index": i})
            total += bt
        procs.sort(key=lambda p: (p["at"], p["index"]))
        for i, p in enumerate(procs):
            p["index"] = i  # FCFS tie-break = input order after arrival sort
        params: dict[str, Any] = {
            "mode": mode,
            "processes": procs,
            "metric": rng.choice(["waiting", "turnaround"]),
        }
        if mode == "rr":
            params["quantum"] = rng.randint(1, max(2, difficulty - 1))
        # ensure non-trivial: at least two different arrivals
        if len({p["at"] for p in procs}) < 2:
            procs[-1]["at"] = procs[0]["bt"]
        return params

    def node_for(self, params: dict[str, Any]) -> str:
        return self._NODE_FOR[params["mode"]]

    def statement(self, params: dict[str, Any]) -> str:
        rows = "\n".join(f"| {p['pid']} | {p['at']} | {p['bt']} |" for p in params["processes"])
        q = f" Quantum **q = {params['quantum']}**." if params["mode"] == "rr" else ""
        metric = METRIC_LABEL[params["metric"]]
        return (
            f"**{MODE_LABEL[params['mode']]}** scheduling.{q} "
            f"(AT = arrival time, BT = burst time):\n\n"
            f"| PID | AT | BT |\n|-----|----|----|\n{rows}\n\n"
            f"Compute the **{metric}**, rounded to 2 decimal places."
        )

    def solve_a(self, params: dict[str, Any]) -> Any:
        return solve(params, "a")

    def solve_b(self, params: dict[str, Any]) -> Any:
        return solve(params, "b")

    def check(self, params: dict[str, Any], answer: Any) -> bool:
        return self.grade_numeric(self.solve_a(params), answer)

    def properties(self, params: dict[str, Any], answer: Any) -> list[tuple[str, bool]]:
        ct, _ = _simulate_units(params)
        m = _metrics(params, ct)
        w = m["_waiting_each"]
        t_ = m["_turnaround_each"]
        return [  # type: ignore[return-value]
            ("waiting_equals_turnaround_minus_burst", all(abs(w[i] + params["processes"][i]["bt"] - t_[i]) < 1e-9 for i in range(len(w)))),
            ("non_negative_waiting", all(x >= -1e-9 for x in w)),
            ("every_process_completes", len(set(ct)) >= 1 and all(c >= params["processes"][i]["at"] + params["processes"][i]["bt"] for i, c in enumerate(ct))),
            ("rr_large_quantum_equals_fcfs", self._rr_eq_fcfs(params)),
        ]

    @staticmethod
    def _rr_eq_fcfs(params: dict[str, Any]) -> bool:
        if params["mode"] != "rr":
            return True
        big = dict(params, mode="rr", quantum=10**6)
        f = dict(params, mode="fcfs")
        return solve(big, "a") == solve(f, "a")

    def trace(self, params: dict[str, Any]) -> list[Step]:
        _, segments = _simulate_units(params)
        steps: list[Step] = []
        for (s, e, pid) in segments:
            steps.append(Step(text=f"t={s}–{e}: {params['processes'][pid]['pid']} runs", detail={"from": s, "to": e, "pid": pid}))
        ct, _ = _simulate_units(params)
        m = _metrics(params, ct)
        steps.append(Step(text=f"Completion times: " + ", ".join(f"{p['pid']}={ct[i]}" for i, p in enumerate(params["processes"]))))
        steps.append(Step(text=f"{METRIC_LABEL[params['metric']]} = {m[params['metric']]:.2f}"))
        return steps[:24]

    def mistakes(self, params: dict[str, Any]) -> list[MistakeModel]:
        key = self.solve_a(params)
        out: list[MistakeModel] = []
        ct, _ = _simulate_units(params)
        m = _metrics(params, ct)
        if params["metric"] == "waiting":
            alt = round(m["turnaround"], 2)
            if alt != key:
                out.append(MistakeModel(
                    tag="turnaround_for_waiting",
                    title="Reported turnaround as waiting time",
                    answer=alt,
                    feedback="You used turnaround time (completion − arrival). Waiting time also subtracts the burst time.",
                ))
            # ignore arrivals: treat every process as arriving at 0
            w0 = [ct[i] - params["processes"][i]["bt"] for i in range(len(ct))]
            alt2 = round(sum(w0) / len(w0), 2)
            if alt2 != key:
                out.append(MistakeModel(
                    tag="arrival_ignored",
                    title="Ignored arrival times",
                    answer=alt2,
                    feedback="You computed as if every process arrived at t=0. Subtract the arrival time too.",
                ))
        if params["mode"] in ("sjf", "srtf", "rr"):
            fcfs_val = solve(dict(params, mode="fcfs"), "a")
            if fcfs_val != key:
                tag = {"sjf": "sjf_as_fcfs", "srtf": "srtf_as_fcfs", "rr": "rr_as_fcfs"}[params["mode"]]
                out.append(MistakeModel(
                    tag=tag,
                    title="Solved it as FCFS",
                    answer=fcfs_val,
                    feedback=f"The schedule differs from FCFS — {MODE_LABEL[params['mode']]} reorders or preempts processes.",
                ))
        return out


register(CpuScheduling())
