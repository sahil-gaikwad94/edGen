"""Disk-scheduling generator — FCFS / SSTF / SCAN / C-SCAN / LOOK / C-LOOK.

Solver A: state-machine service loop (repeatedly choose the next request,
including explicit edge stops for SCAN/C-SCAN).
Solver B: sorted-list construction (split at the head, concatenate per rules).

Distance = Σ |h(i+1) − h(i)| starting from the head. Cylinders 0..max_cyl−1.
Conventions (documented, both solvers must match):
  * SCAN travels to the physical edge even when no requests remain that way.
  * C-SCAN wrap = travel to edge, jump edge→0 (or 0→edge), jump counts.
  * C-LOOK wrap = jump between extreme requests, jump counts.
"""
from __future__ import annotations

from typing import Any

from ..protocol import BaseGenerator, MistakeModel, Step, register

MODES = ("fcfs", "sstf", "scan", "cscan", "look", "clook")
MODE_LABEL = {
    "fcfs": "FCFS",
    "sstf": "SSTF",
    "scan": "SCAN",
    "cscan": "C-SCAN",
    "look": "LOOK",
    "clook": "C-LOOK",
}
NEEDS_DIR = {"scan", "cscan", "look", "clook"}


def _dist(head: int, order: list[int]) -> int:
    total, cur = 0, head
    for c in order:
        total += abs(c - cur)
        cur = c
    return total


def _dedupe(order: list[int]) -> list[int]:
    out: list[int] = []
    for c in order:
        if out and out[-1] == c:
            continue
        out.append(c)
    return out


# --- solver A: state machine ------------------------------------------------

def _order_a(params: dict) -> list[int]:
    mode = params["mode"]
    head = params["head"]
    reqs = list(params["requests"])
    last = params["max_cyl"] - 1
    direction = params.get("direction", "right")

    if mode == "fcfs":
        return list(reqs)

    if mode == "sstf":
        pending, order, cur = list(reqs), [], head
        while pending:
            nxt = min(pending, key=lambda c: (abs(c - cur), c))
            order.append(nxt)
            pending.remove(nxt)
            cur = nxt
        return order

    if mode == "scan":
        served: set[int] = set()
        order: list[int] = []
        cur, d = head, (1 if direction == "right" else -1)
        while len(served) < len(reqs):
            if d == 1:
                cands = [c for c in reqs if c not in served and c >= cur]
                if cands:
                    t = min(cands)
                else:
                    if cur != last:
                        order.append(last)
                        cur = last
                    d = -1
                    continue
            else:
                cands = [c for c in reqs if c not in served and c <= cur]
                if cands:
                    t = max(cands)
                else:
                    if cur != 0:
                        order.append(0)
                        cur = 0
                    d = 1
                    continue
            order.append(t)
            served.add(t)
            cur = t
        return _dedupe(order)

    if mode == "look":
        served = set()
        order = []
        cur, d = head, (1 if direction == "right" else -1)
        while len(served) < len(reqs):
            if d == 1:
                cands = [c for c in reqs if c not in served and c >= cur]
                if cands:
                    t = min(cands)
                else:
                    d = -1
                    continue
            else:
                cands = [c for c in reqs if c not in served and c <= cur]
                if cands:
                    t = max(cands)
                else:
                    d = 1
                    continue
            order.append(t)
            served.add(t)
            cur = t
        return _dedupe(order)

    if mode in ("cscan", "clook"):
        served = set()
        order = []
        cur, d = head, (1 if direction == "right" else -1)
        while len(served) < len(reqs):
            if d == 1:
                cands = [c for c in reqs if c not in served and c >= cur]
                if cands:
                    t = min(cands)
                    order.append(t)
                    served.add(t)
                    cur = t
                    continue
                if mode == "cscan":
                    if cur != last:
                        order.append(last)
                        cur = last
                    order.append(0)
                    cur = 0
                else:  # clook: jump to lowest unserved request
                    t = min(c for c in reqs if c not in served)
                    order.append(t)
                    served.add(t)
                    cur = t
            else:
                cands = [c for c in reqs if c not in served and c <= cur]
                if cands:
                    t = max(cands)
                    order.append(t)
                    served.add(t)
                    cur = t
                    continue
                if mode == "cscan":
                    if cur != 0:
                        order.append(0)
                        cur = 0
                    order.append(last)
                    cur = last
                else:
                    t = max(c for c in reqs if c not in served)
                    order.append(t)
                    served.add(t)
                    cur = t
        return _dedupe(order)

    raise ValueError(mode)


# --- solver B: sorted-list construction -------------------------------------

def _dist_b(params: dict) -> int:
    mode = params["mode"]
    head = params["head"]
    reqs = list(params["requests"])
    last = params["max_cyl"] - 1
    direction = params.get("direction", "right")

    if mode == "fcfs":
        return _dist(head, reqs)

    if mode == "sstf":
        remaining = sorted(reqs)
        order: list[int] = []
        cur = head
        while remaining:
            best = remaining[0]
            for c in remaining:
                if (abs(c - cur), c) < (abs(best - cur), best):
                    best = c
            order.append(best)
            remaining.remove(best)
            cur = best
        return _dist(head, order)

    at_head = sorted(c for c in reqs if c == head)
    rest = [c for c in reqs if c != head]

    if mode == "scan":
        above = sorted(c for c in rest if c > head)
        below = sorted(c for c in rest if c < head)
        # Edge leg only when unserved requests remain beyond it; if everything is
        # already serviced, distance stops at the final request (matches solver A).
        if direction == "right":
            seq = at_head + above + ([last] if below else []) + sorted(below, reverse=True)
        else:
            seq = at_head + sorted(below, reverse=True) + ([0] if above else []) + above
        return _dist(head, seq)

    if mode == "look":
        if direction == "right":
            seq = at_head + sorted(c for c in rest if c > head) + sorted((c for c in rest if c < head), reverse=True)
        else:
            seq = at_head + sorted((c for c in rest if c < head), reverse=True) + sorted(c for c in rest if c > head)
        return _dist(head, seq)

    if mode == "cscan":
        above = sorted(c for c in rest if c > head)
        below = sorted(c for c in rest if c < head)
        # Wrap only when requests remain on the far side.
        if direction == "right":
            seq = at_head + above + ([last, 0] if below else []) + below
        else:
            seq = at_head + sorted(below, reverse=True) + ([0, last] if above else []) + sorted(above, reverse=True)
        return _dist(head, seq)

    if mode == "clook":
        lo, hi = min(reqs), max(reqs)
        below = sorted(c for c in rest if c < head)
        above = sorted(c for c in rest if c > head)
        if direction == "right":
            seq = at_head + above + ([lo] if below else []) + below
        else:
            seq = at_head + sorted(below, reverse=True) + ([hi] if above else []) + sorted(above, reverse=True)
        return _dist(head, seq)

    raise ValueError(mode)


class DiskScheduling(BaseGenerator):
    id = "os.disk_scheduling"
    title = "Disk scheduling"
    node_ids = ["os.disk.scheduling"]
    input_spec = {"kind": "number", "placeholder": "e.g. 412", "hint": "total cylinders of movement"}
    hints = [
        "Write down the exact order the head visits, starting from the initial head.",
        "Sum |next − current| for every hop — including the first move away from the head.",
        "SCAN passes the physical edge (0 or 199); LOOK reverses at the last request.",
        "For C-SCAN/C-LOOK, the wrap jump is part of the total distance.",
    ]

    def sample(self, rng, difficulty: int) -> dict[str, Any]:
        mode = rng.choice(MODES)
        n = 6 + (1 if difficulty >= 3 else 0) + (1 if difficulty >= 5 else 0)
        n = min(n, 9)
        head = rng.randint(0, 199)
        requests: list[int] = []
        while len(requests) < n:
            c = rng.randint(0, 199)
            if c != head and c not in requests:
                requests.append(c)
        params: dict[str, Any] = {"mode": mode, "head": head, "requests": requests, "max_cyl": 200}
        if mode in NEEDS_DIR:
            params["direction"] = rng.choice(["left", "right"])
        return params

    def node_for(self, params: dict[str, Any]) -> str:
        return "os.disk.scheduling"

    def statement(self, params: dict[str, Any]) -> str:
        reqs = ", ".join(str(c) for c in params["requests"])
        d = f" Current direction: **{params['direction']}**." if "direction" in params else ""
        return (
            f"**{MODE_LABEL[params['mode']]}** disk scheduling.{d} "
            f"Head starts at cylinder **{params['head']}**; cylinders run 0–199.\n\n"
            f"Queue: `{reqs}`\n\n"
            "What is the **total seek distance** (sum of all head movements)?"
        )

    def solve_a(self, params: dict[str, Any]) -> Any:
        return _dist(params["head"], _order_a(params))

    def solve_b(self, params: dict[str, Any]) -> Any:
        return _dist_b(params)

    def check(self, params: dict[str, Any], answer: Any) -> bool:
        try:
            return int(str(answer).strip()) == int(self.solve_a(params))
        except (TypeError, ValueError):
            return False

    def properties(self, params: dict[str, Any], answer: Any) -> list[tuple[str, bool]]:
        props: list[tuple[str, bool]] = [("non_negative", answer >= 0)]
        if params["mode"] == "scan":
            props.append(("look_no_worse_than_scan", _dist_b(dict(params, mode="look")) <= answer))
        if params["mode"] == "cscan":
            props.append(("clook_no_worse_than_cscan", _dist_b(dict(params, mode="clook")) <= answer))
        return props

    def trace(self, params: dict[str, Any]) -> list[Step]:
        order = _order_a(params)
        return [
            Step(text=f"Head {params['head']} → " + " → ".join(str(c) for c in order)),
            Step(text=f"Total seek distance = {self.solve_a(params)}"),
        ]

    def mistakes(self, params: dict[str, Any]) -> list[MistakeModel]:
        key = int(self.solve_a(params))
        out: list[MistakeModel] = []
        mode = params["mode"]

        if mode in ("scan", "look"):
            other = _dist_b(dict(params, mode="look" if mode == "scan" else "scan"))
            if other != key:
                if mode == "scan":
                    out.append(MistakeModel(
                        tag="scan_as_look", title="Stopped at the last request (LOOK)",
                        answer=other,
                        feedback="SCAN sweeps to the physical disk edge before reversing; LOOK stops at the last request.",
                    ))
                else:
                    out.append(MistakeModel(
                        tag="look_as_scan", title="Swept to the disk edge (SCAN)",
                        answer=other,
                        feedback="LOOK reverses as soon as no requests remain in that direction — no edge trip.",
                    ))
        if mode in ("cscan", "clook"):
            other = _dist_b(dict(params, mode="clook" if mode == "cscan" else "cscan"))
            if other != key:
                out.append(MistakeModel(
                    tag="cscan_clook_confused",
                    title="Mixed up C-SCAN and C-LOOK",
                    answer=other,
                    feedback=("C-SCAN wraps at the physical edges (to 199, jump to 0); "
                              "C-LOOK wraps directly between the extreme requests."),
                ))
            # forgetting the wrap leg entirely
            alt = _wrap_ignored(params)
            if alt != key and alt >= 0:
                out.append(MistakeModel(
                    tag="wrap_ignored", title="Didn't count the wrap",
                    answer=alt,
                    feedback="The return jump (and edge travel for C-SCAN) is part of the total distance.",
                ))
        if mode in NEEDS_DIR:
            flipped = _dist_b(dict(params, direction=("left" if params["direction"] == "right" else "right")))
            if flipped != key:
                out.append(MistakeModel(
                    tag="direction_ignored", title="Started the other way",
                    answer=flipped,
                    feedback=f"Begin in the stated direction ({params['direction']}) — the first leg changes the whole path.",
                ))
        if mode in ("fcfs", "sstf"):
            # ignoring the initial head offset: measure from the first request
            order = _order_a(params)
            if order:
                without_head = _dist(order[0], order[1:])
                if without_head != key:
                    out.append(MistakeModel(
                        tag="head_offset_ignored", title="Ignored the head's starting position",
                        answer=without_head,
                        feedback="Include the move from the initial head to the first serviced cylinder.",
                    ))
        return out


def _wrap_ignored(params: dict) -> int:
    """Total distance with the wrap jump removed (C-SCAN: 199↔0, C-LOOK: max↔min)."""
    order = _order_a(params)
    total, cur = 0, params["head"]
    lo, hi = min(params["requests"]), max(params["requests"])
    edge_lo, edge_hi = 0, params["max_cyl"] - 1
    for c in order:
        step = abs(c - cur)
        if params["mode"] == "cscan" and ((cur == edge_hi and c == edge_lo) or (cur == edge_lo and c == edge_hi)):
            step = 0
        if params["mode"] == "clook" and ((cur == hi and c == lo) or (cur == lo and c == hi)):
            step = 0
        total += step
        cur = c
    return total


register(DiskScheduling())
