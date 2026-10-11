"""Page-replacement generator — FIFO / LRU / OPT.

Solver A: simulations with idiom-accurate structures (deque for FIFO,
timestamp dict for LRU, precomputed next-use table for OPT).
Solver B: different structures (ring buffer for FIFO, recency stack for LRU,
forward-search for OPT).
Tie-break (OPT): victim = max next-use, then smallest page id.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from ..protocol import BaseGenerator, MistakeModel, Step, register

MODES = ("fifo", "lru", "opt")
MODE_LABEL = {"fifo": "FIFO", "lru": "LRU", "opt": "OPT (optimal)"}


# --- solver A ---------------------------------------------------------------

def _faults_a(mode: str, k: int, refs: list[int]) -> tuple[int, list[str]]:
    frames: list[int] = []
    faults = 0
    log: list[str] = []
    fifo_q: deque[int] = deque()
    last_used: dict[int, int] = {}
    # precompute next-use table for OPT: nxt[pos][p] = next index > pos where p
    # appears (10**9 if never) — for EVERY page, not just refs[pos].
    all_pages = sorted(set(refs))
    nxt_after: dict[int, int] = {p: 10**9 for p in all_pages}
    nxt_table: list[dict[int, int]] = [{} for _ in refs]
    for pos in range(len(refs) - 1, -1, -1):
        nxt_table[pos] = dict(nxt_after)
        nxt_after[refs[pos]] = pos

    for pos, page in enumerate(refs):
        if page in frames:
            hit = True
        else:
            hit = False
            faults += 1
            if len(frames) == k:
                if mode == "fifo":
                    victim = fifo_q.popleft()
                    frames.remove(victim)
                elif mode == "lru":
                    victim = min(frames, key=lambda p: last_used[p])
                    frames.remove(victim)
                else:  # opt — precomputed next-use table
                    victim = min(frames, key=lambda p: (-nxt_table[pos].get(p, 10**9), p))
                    frames.remove(victim)
            frames.append(page)
            if mode == "fifo":
                fifo_q.append(page)
        if mode == "lru":
            last_used[page] = pos
        log.append(f"ref {page}: {'HIT ' if hit else 'FAULT'} frames={frames}")
    return faults, log


# --- solver B ---------------------------------------------------------------

def _faults_b(mode: str, k: int, refs: list[int]) -> int:
    if mode == "fifo":
        ring: list[int] = [-1] * k
        ptr = 0
        resident: set[int] = set()
        faults = 0
        for page in refs:
            if page in resident:
                continue
            faults += 1
            evicted = ring[ptr]
            if evicted != -1:
                resident.discard(evicted)
            ring[ptr] = page
            resident.add(page)
            ptr = (ptr + 1) % k
        return faults
    if mode == "lru":
        stack: list[int] = []  # index 0 = most recent
        faults = 0
        for page in refs:
            if page in stack:
                stack.remove(page)
                stack.insert(0, page)
                continue
            faults += 1
            if len(stack) == k:
                stack.pop()  # least recent at the end
            stack.insert(0, page)
        return faults
    # OPT via forward search
    resident: list[int] = []
    faults = 0
    for pos, page in enumerate(refs):
        if page in resident:
            continue
        faults += 1
        if len(resident) == k:
            def nxt(p: int) -> int:
                for j in range(pos + 1, len(refs)):
                    if refs[j] == p:
                        return j
                return 10**9
            victim = min(resident, key=lambda p: (-nxt(p), p))
            resident.remove(victim)
        resident.append(page)
    return faults


class PageReplacement(BaseGenerator):
    id = "os.page_replacement"
    title = "Page replacement"
    node_ids = ["os.vmemory.page_replacement"]
    input_spec = {"kind": "number", "placeholder": "e.g. 9", "hint": "whole number of faults"}
    hints = [
        "Fill the empty frames first — those initial fills ARE page faults.",
        "Write the frame contents after every single reference; don't skip hits.",
        "FIFO evicts the oldest *loaded* page; LRU evicts the least recently *used*.",
        "OPT peeks into the future: evict the page whose next use is farthest away (or never).",
    ]

    def sample(self, rng, difficulty: int) -> dict[str, Any]:
        mode = rng.choice(MODES)
        k = rng.randint(3, 3 + (1 if difficulty >= 3 else 0) + (1 if difficulty >= 5 else 0))
        k = min(k, 4)
        distinct = k + rng.randint(2, 4)
        length = rng.randint(12, 12 + difficulty)
        pages = list(range(distinct))
        refs = [rng.choice(pages) for _ in range(length)]
        # ensure every frame fills and some eviction happens
        head = pages[:]
        rng.shuffle(head)
        refs = head[:k] + refs
        return {"mode": mode, "frames": k, "refs": refs}

    def node_for(self, params: dict[str, Any]) -> str:
        return "os.vmemory.page_replacement"

    def statement(self, params: dict[str, Any]) -> str:
        refs = " ".join(str(r) for r in params["refs"])
        return (
            f"**{MODE_LABEL[params['mode']]}** page replacement with **{params['frames']} frames**, "
            f"starting empty.\n\nReference string:\n\n`{refs}`\n\n"
            "How many **page faults** occur? (The first load of each page into an empty frame counts.)"
        )

    def solve_a(self, params: dict[str, Any]) -> Any:
        faults, _ = _faults_a(params["mode"], params["frames"], params["refs"])
        return faults

    def solve_b(self, params: dict[str, Any]) -> Any:
        return _faults_b(params["mode"], params["frames"], params["refs"])

    def check(self, params: dict[str, Any], answer: Any) -> bool:
        try:
            return int(str(answer).strip()) == self.solve_a(params)
        except (TypeError, ValueError):
            return False

    def properties(self, params: dict[str, Any], answer: Any) -> list[tuple[str, bool]]:
        k, refs = params["frames"], params["refs"]
        distinct = len(set(refs))
        opt = _faults_b("opt", k, refs)
        fifo = _faults_b("fifo", k, refs)
        lru_k = _faults_b("lru", k, refs)
        lru_k1 = _faults_b("lru", k + 1, refs)
        return [
            ("at_least_compulsory_faults", answer >= distinct),
            ("at_most_one_fault_per_reference", answer <= len(refs)),
            ("opt_no_worse_than_fifo", opt <= fifo),
            # LRU is a stack algorithm: Belady's anomaly cannot occur —
            # more frames means fewer-or-equal faults.
            # (FIFO deliberately has NO such property — we teach Belady's anomaly.)
            ("lru_stack_property", lru_k1 <= lru_k),
        ]

    def trace(self, params: dict[str, Any]) -> list[Step]:
        _, log = _faults_a(params["mode"], params["frames"], params["refs"])
        return [Step(text=line) for line in log] + [Step(text=f"Total faults = {self.solve_a(params)}")]

    def mistakes(self, params: dict[str, Any]) -> list[MistakeModel]:
        key = self.solve_a(params)
        out: list[MistakeModel] = []
        distinct = len(set(params["refs"]))
        forget_initial = key - min(params["frames"], distinct)
        if forget_initial >= 0 and forget_initial != key:
            out.append(MistakeModel(
                tag="forgets_initial_faults",
                title="Didn't count the initial fills",
                answer=forget_initial,
                feedback="Filling empty frames is still a page fault — the page wasn't in memory.",
            ))
        more_frames = _faults_b(params["mode"], params["frames"] + 1, params["refs"])
        if more_frames != key:
            out.append(MistakeModel(
                tag="off_by_one_frames",
                title="Used the wrong number of frames",
                answer=more_frames,
                feedback=f"Recount with exactly {params['frames']} frames — you simulated {params['frames'] + 1}.",
            ))
        if params["mode"] == "lru":
            fifo = _faults_b("fifo", params["frames"], params["refs"])
            if fifo != key:
                out.append(MistakeModel(
                    tag="lru_as_fifo",
                    title="Evicted by load order, not recency",
                    answer=fifo,
                    feedback="You evicted the oldest *loaded* page (FIFO). LRU evicts the least recently *used* page.",
                ))
        if params["mode"] == "opt":
            lru = _faults_b("lru", params["frames"], params["refs"])
            if lru != key:
                out.append(MistakeModel(
                    tag="opt_looks_backwards",
                    title="Looked into the past, not the future",
                    answer=lru,
                    feedback="OPT compares *next* uses. If you evicted based on last use, that's LRU.",
                ))
        if params["mode"] == "fifo":
            lru = _faults_b("lru", params["frames"], params["refs"])
            if lru != key:
                out.append(MistakeModel(
                    tag="fifo_as_lru",
                    title="Evicted by recency, not load order",
                    answer=lru,
                    feedback="FIFO ignores when pages were used — it evicts the page that has been resident the longest.",
                ))
        return out


register(PageReplacement())
