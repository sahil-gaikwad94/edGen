"""Conflict-serializability generator — precedence graphs, cycle → serial order.

Solver A: DFS colouring for cycles + DFS post-order topological sort.
Solver B: Kahn peeling (indegree counters) for both cycle detection and order.
Grading accepts ANY valid serial order (checked independently), so the two
solvers may legitimately return different orders — `agree` validates both.
"""
from __future__ import annotations

from typing import Any

from ..protocol import BaseGenerator, MistakeModel, Step, register


def _parse_ops(params: dict) -> list[tuple[str, str, str]]:
    """[(tx, r|w, item), ...] in schedule order."""
    return [(o["tx"], o["rw"], o["item"]) for o in params["ops"]]


def _edges(params: dict, mode: str = "full") -> list[tuple[str, str, str]]:
    """Precedence edges (u, v, why). mode: full | wr_only | reversed | any_share."""
    ops = _parse_ops(params)
    edges: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for i, (t1, rw1, d1) in enumerate(ops):
        for j in range(i + 1, len(ops)):
            t2, rw2, d2 = ops[j]
            if t1 == t2 or d1 != d2:
                continue
            conflict = (rw1 == "w" or rw2 == "w")
            if mode == "wr_only":
                conflict = (rw1 == "w" and rw2 == "r")
            if mode == "any_share":
                conflict = True  # wrong: reads treated as conflicting
            if not conflict:
                continue
            edge = (t1, t2, f"{t1}:{rw1}({d1}) before {t2}:{rw2}({d2}) at {i + 1}→{j + 1}")
            if mode == "reversed":
                edge = (t2, t1, edge[2])
            if (edge[0], edge[1]) not in seen:
                seen.add((edge[0], edge[1]))
                edges.append(edge)
    return edges


def _txs(params: dict) -> list[str]:
    return sorted({o["tx"] for o in params["ops"]})


# --- solver A: DFS -----------------------------------------------------------

def _solve_a(params: dict) -> str:
    edges = _edges(params)
    adj: dict[str, list[str]] = {t: [] for t in _txs(params)}
    for u, v, _ in edges:
        adj[u].append(v)
    WHITE, GRAY, BLACK = 0, 1, 2
    colour = {t: WHITE for t in adj}
    cycle = False

    def dfs(u: str) -> None:
        nonlocal cycle
        colour[u] = GRAY
        for v in adj[u]:
            if colour[v] == GRAY:
                cycle = True
                return
            if colour[v] == WHITE:
                dfs(v)
                if cycle:
                    return
        colour[u] = BLACK

    for t in sorted(adj):
        if colour[t] == WHITE:
            dfs(t)
            if cycle:
                return "NONE"
    # topological order via DFS post-order (reverse)
    order: list[str] = []
    colour = {t: WHITE for t in adj}

    def topo(u: str) -> None:
        colour[u] = GRAY
        for v in adj[u]:
            if colour[v] == WHITE:
                topo(v)
        colour[u] = BLACK
        order.append(u)

    for t in sorted(adj):
        if colour[t] == WHITE:
            topo(t)
    return ",".join(reversed(order))


# --- solver B: Kahn peeling ---------------------------------------------------

def _solve_b(params: dict) -> str:
    edges = _edges(params)
    txs = _txs(params)
    indeg = {t: 0 for t in txs}
    adj: dict[str, list[str]] = {t: [] for t in txs}
    for u, v, _ in edges:
        adj[u].append(v)
        indeg[v] += 1
    ready = sorted(t for t in txs if indeg[t] == 0)
    order: list[str] = []
    while ready:
        t = ready.pop(0)
        order.append(t)
        changed = False
        for v in adj[t]:
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
                ready.sort()
        changed = True
    if len(order) != len(txs):
        return "NONE"
    return ",".join(order)


def _is_valid_order(params: dict, order: str) -> bool:
    txs = _txs(params)
    parts = [p.strip().upper().replace(" ", "") for p in order.replace(";", ",").split(",") if p.strip()]
    if len(parts) != len(txs) or set(parts) != set(txs) or len(set(parts)) != len(parts):
        return False
    pos = {t: i for i, t in enumerate(parts)}
    for u, v, _ in _edges(params):
        if pos[u] > pos[v]:
            return False
    return True


class Serializability(BaseGenerator):
    id = "dbms.serializability"
    title = "Conflict serializability"
    node_ids = ["dbms.txn.conflict_serializable"]
    input_spec = {
        "kind": "text",
        "placeholder": "e.g. T1,T2  or  NONE",
        "hint": "a serial order, or NONE",
    }
    hints = [
        "List every operation with its step number, marking writes with a star.",
        "Draw an edge u → v whenever an operation of u conflicts with a later one of v.",
        "Conflict = different transactions, same data item, at least one write.",
        "The schedule is conflict serializable iff the graph has no cycle; any topological order works.",
    ]

    def sample(self, rng, difficulty: int) -> dict[str, Any]:
        n_tx = 2 + (1 if difficulty >= 4 else 0)
        n_tx = min(n_tx, 3)
        n_ops = 5 + (1 if difficulty >= 3 else 0) + (1 if difficulty >= 5 else 0)
        n_ops = min(n_ops, 8)
        items = ["X", "Y", "Z"][: rng.randint(2, 3)]
        txs = [f"T{i + 1}" for i in range(n_tx)]
        for _attempt in range(80):
            ops = [
                {"tx": rng.choice(txs), "rw": rng.choice(["r", "w"]), "item": rng.choice(items)}
                for _ in range(n_ops)
            ]
            # every transaction must actually appear
            if {o["tx"] for o in ops} != set(txs):
                continue
            if not _edges({"ops": ops}):
                continue
            return {"ops": ops}
        # deterministic fallback: guaranteed interesting schedule
        return {"ops": [
            {"tx": "T1", "rw": "r", "item": "X"},
            {"tx": "T2", "rw": "w", "item": "X"},
            {"tx": "T1", "rw": "w", "item": "X"},
            {"tx": "T2", "rw": "r", "item": "Y"},
            {"tx": "T1", "rw": "w", "item": "Y"},
        ]}

    def node_for(self, params: dict[str, Any]) -> str:
        return "dbms.txn.conflict_serializable"

    def statement(self, params: dict[str, Any]) -> str:
        rows = "\n".join(
            f"{i + 1}. {o['tx']}:{'w' if o['rw'] == 'w' else 'r'}({o['item']})"
            for i, o in enumerate(params["ops"])
        )
        return (
            "**Schedule:**\n\n" + rows + "\n\n"
            "Is this schedule **conflict serializable**? If yes, give one valid serial order "
            "(e.g. `T1,T2`). If no, answer `NONE`."
        )

    def solve_a(self, params: dict[str, Any]) -> Any:
        return _solve_a(params)

    def solve_b(self, params: dict[str, Any]) -> Any:
        return _solve_b(params)

    def agree(self, params: dict[str, Any], a: Any, b: Any) -> bool:
        a, b = str(a).upper(), str(b).upper()
        if a == "NONE" or b == "NONE":
            return a == b == "NONE"
        return _is_valid_order(params, a) and _is_valid_order(params, b)

    def canonical(self, answer: Any) -> str:
        s = str(answer).strip().upper().replace(" ", "")
        return s

    def check(self, params: dict[str, Any], answer: Any) -> bool:
        s = self.canonical(answer)
        if s in ("NONE", "N/A", "NOTSERIALIZABLE", "NOT-SERIALIZABLE"):
            return _solve_a(params) == "NONE"
        return _is_valid_order(params, s)

    def properties(self, params: dict[str, Any], answer: Any) -> list[tuple[str, bool]]:
        props: list[tuple[str, bool]] = []
        if answer == "NONE":
            # graph must actually cycle
            props.append(("none_implies_cycle", _solve_a(params) == "NONE"))
        else:
            props.append(("order_is_valid", _is_valid_order(params, str(answer))))
            props.append(("order_covers_all_tx", set(str(answer).split(",")) == set(_txs(params))))
        # B agrees on serializability verdict
        props.append(("verdict_stable", (_solve_b(params) == "NONE") == (_solve_a(params) == "NONE")))
        return props

    def trace(self, params: dict[str, Any]) -> list[Step]:
        edges = _edges(params)
        steps = [Step(text=f"Edge {u} → {v}  ({why})") for u, v, why in edges] or [
            Step(text="No conflicting pairs → no edges.")
        ]
        verdict = _solve_a(params)
        if verdict == "NONE":
            steps.append(Step(text="The precedence graph has a cycle → NOT conflict serializable."))
        else:
            steps.append(Step(text=f"Acyclic → conflict serializable; one serial order: {verdict}"))
        return steps

    def mistakes(self, params: dict[str, Any]) -> list[MistakeModel]:
        key = self.canonical(self.solve_a(params))
        out: list[MistakeModel] = []

        alt_wr = _solve_a_with(params, mode="wr_only")
        if alt_wr != key:
            out.append(MistakeModel(
                tag="missing_rw_ww_edges", title="Only drew write→read edges",
                answer=alt_wr,
                feedback="Reads-before-writes and writes-before-writes are conflicts too — every pair with at least one write counts.",
            ))
        alt_rev = _solve_a_with(params, mode="reversed")
        if alt_rev != key:
            out.append(MistakeModel(
                tag="reversed_edges", title="Drew the edges backwards",
                answer=alt_rev,
                feedback="The edge points from the transaction of the *earlier* operation to the *later* one.",
            ))
        alt_any = _solve_a_with(params, mode="any_share")
        if alt_any != key:
            out.append(MistakeModel(
                tag="reads_treated_as_conflicting", title="Treated reads as conflicting",
                answer=alt_any,
                feedback="Two reads of the same item never conflict — at least one operation must be a write.",
            ))
        return out


def _solve_a_with(params: dict, mode: str) -> str:
    """Re-run solver A on a mutated edge rule (mistake model)."""
    edges = _edges(params, mode=mode)
    txs = _txs(params)
    adj: dict[str, list[str]] = {t: [] for t in txs}
    for u, v, _ in edges:
        if u in adj and v in adj:
            adj[u].append(v)
    indeg = {t: 0 for t in txs}
    for u, vs in adj.items():
        for v in vs:
            indeg[v] += 1
    ready = sorted(t for t in txs if indeg[t] == 0)
    order: list[str] = []
    while ready:
        t = ready.pop(0)
        order.append(t)
        for v in adj[t]:
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
                ready.sort()
    if len(order) != len(txs):
        return "NONE"
    return ",".join(order)


register(Serializability())
