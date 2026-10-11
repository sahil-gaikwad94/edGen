"""Functional-dependency generator — attribute closure / candidate keys / normal form.

Solver A: frozenset fixpoint closure + itertools subset key search + textbook
NF checks.
Solver B: integer bitmask closure + sub-mask minimality key search + NF checks
written from the superkey oracle only.
"""
from __future__ import annotations

import itertools
from typing import Any

from ..protocol import BaseGenerator, MistakeModel, Step, register

MODES = ("closure", "keys", "normal_form")
NF_ORDER = ("1NF", "2NF", "3NF", "BCNF")


# --- shared helpers ----------------------------------------------------------

def _closure_sets(attrs: list[str], fds: list[list[str]], xs: set[str]) -> set[str]:
    closure = set(xs)
    changed = True
    while changed:
        changed = False
        for lhs, rhs in fds:
            if set(lhs) <= closure and rhs not in closure:
                closure.add(rhs)
                changed = True
    return closure


# --- solver A ----------------------------------------------------------------

def _solve_a(params: dict) -> Any:
    attrs = params["attrs"]
    fds = params["fds"]
    full = set(attrs)
    if params["mode"] == "closure":
        return sorted(_closure_sets(attrs, fds, set(params["query"])) )

    # keys via minimal subsets
    keys: list[frozenset[str]] = []
    for size in range(1, len(attrs) + 1):
        for combo in itertools.combinations(attrs, size):
            c = frozenset(combo)
            if any(k <= c for k in keys):
                continue
            if _closure_sets(attrs, fds, set(c)) == full:
                keys.append(c)
    if params["mode"] == "keys":
        return keys

    prime = set().union(*keys) if keys else set()
    superkey = lambda x: _closure_sets(attrs, fds, set(x)) == full

    # 2NF: no non-prime attribute partially dependent on a candidate key
    viol_2nf = False
    for lhs, rhs in fds:
        if rhs in prime:
            continue
        for k in keys:
            if set(lhs) < set(k):
                viol_2nf = True
                break
        if viol_2nf:
            break
    # 3NF: no non-prime RHS determined by a non-superkey LHS
    viol_3nf = any(rhs not in prime and not superkey(set(lhs)) for lhs, rhs in fds)
    # BCNF: every LHS a superkey
    viol_bcnf = any(not superkey(set(lhs)) for lhs, rhs in fds)

    if viol_bcnf:
        pass
    if not viol_bcnf:
        return "BCNF"
    if not viol_3nf:
        return "3NF"
    if not viol_2nf:
        return "2NF"
    return "1NF"


# --- solver B: bitmask world --------------------------------------------------

def _closure_mask(n: int, fds: list[list[str]], mask: int) -> int:
    changed = True
    while changed:
        changed = False
        for lhs, rhs in fds:
            lm = 0
            for ch in lhs:
                lm |= 1 << (ord(ch) - 65)
            if (lm & ~mask) == 0:  # lhs ⊆ mask
                rm = 1 << (ord(rhs) - 65)
                if not (mask & rm):
                    mask |= rm
                    changed = True
    return mask


def _solve_b(params: dict) -> Any:
    attrs = params["attrs"]
    fds = params["fds"]
    n = len(attrs)
    full = (1 << n) - 1
    amap = {ch: 1 << i for i, ch in enumerate(attrs)}

    if params["mode"] == "closure":
        mask = 0
        for ch in params["query"]:
            mask |= amap[ch]
        out = _closure_mask(n, fds, mask)
        return sorted(ch for ch in attrs if out & amap[ch])

    # candidate keys: minimal masks whose closure is everything
    key_masks: list[int] = []
    for m in range(1, 1 << n):
        # skip masks that are non-minimal (contain a known key)
        if any((k & ~m) == 0 for k in key_masks):
            continue
        if _closure_mask(n, fds, m) == full:
            # minimality against all sub-masks (not only found keys)
            subs_ok = True
            sub = (m - 1) & m
            while sub:
                if _closure_mask(n, fds, sub) == full:
                    subs_ok = False
                    break
                sub = (sub - 1) & m
            if subs_ok:
                key_masks.append(m)
    if params["mode"] == "keys":
        return key_masks  # canonicalised outside

    prime = 0
    for k in key_masks:
        prime |= k

    def is_superkey(lhs: list[str]) -> bool:
        mask = 0
        for ch in lhs:
            mask |= amap[ch]
        return _closure_mask(n, fds, mask) == full

    viol_bcnf = any(not is_superkey(lhs) for lhs, _ in fds)
    viol_3nf = any((not (amap[rhs] & prime)) and not is_superkey(lhs) for lhs, rhs in fds)
    viol_2nf = False
    for lhs, rhs in fds:
        if amap[rhs] & prime:
            continue
        lm = 0
        for ch in lhs:
            lm |= amap[ch]
        for k in key_masks:
            if (lm & ~k) == 0 and lm != k:  # lhs ⊊ key
                viol_2nf = True
                break
        if viol_2nf:
            break

    if not viol_bcnf:
        return "BCNF"
    if not viol_3nf:
        return "3NF"
    if not viol_2nf:
        return "2NF"
    return "1NF"


def _keys_to_str(keys: list) -> str:
    """Canonical: each key sorted, keys sorted lexicographically, joined by commas."""
    norm: list[str] = []
    for k in keys:
        if isinstance(k, frozenset):
            norm.append("".join(sorted(k)))
        elif isinstance(k, int):
            norm.append(k)  # resolved by caller with attrs
        else:
            norm.append("".join(sorted(str(k))))
    return norm


class FdClosure(BaseGenerator):
    id = "dbms.fd_closure"
    title = "Functional dependencies"
    node_ids = ["dbms.norm.closure", "dbms.norm.candidate_keys", "dbms.norm.bcnf"]
    input_spec = {"kind": "text", "placeholder": "e.g. ABC", "hint": "letters, no spaces"}
    hints = [
        "Start with the given attributes in the closure, then apply FDs whose LHS is already inside.",
        "Keep looping until no new attribute joins — one pass is never enough.",
        "A candidate key must be *minimal*: no proper subset may also determine everything.",
        "For normal form: check BCNF first (LHS must be a superkey), then 3NF (non-prime RHS), then 2NF (partial dependency).",
    ]

    _NODE_FOR_NF = {"1NF": "dbms.norm.first_nf", "2NF": "dbms.norm.second_nf",
                    "3NF": "dbms.norm.third_nf", "BCNF": "dbms.norm.bcnf"}
    _NODE_FOR_MODE = {"closure": "dbms.norm.closure", "keys": "dbms.norm.candidate_keys",
                      "normal_form": "dbms.norm.ladder"}

    def sample(self, rng, difficulty: int) -> dict[str, Any]:
        n = 3 + (1 if difficulty >= 3 else 0) + (1 if difficulty >= 5 else 0)
        n = min(n, 5)
        attrs = [chr(65 + i) for i in range(n)]
        mode = rng.choice(MODES)
        n_fds = rng.randint(n - 1, n + 1)
        fds: list[list[str]] = []
        seen: set[tuple[str, str]] = set()
        attempts = 0
        while len(fds) < n_fds and attempts < 60:
            attempts += 1
            size = rng.randint(1, min(3, n - 1))
            lhs_chars = rng.sample(attrs, size)
            rhs = rng.choice([a for a in attrs if a not in lhs_chars])
            lhs = sorted(lhs_chars)
            if ("".join(lhs), rhs) in seen:
                continue
            # skip trivial and immediately redundant
            if rhs in lhs:
                continue
            seen.add(("".join(lhs), rhs))
            fds.append([lhs, rhs])
        rng.shuffle(fds)  # order matters for the single-pass mistake model
        params: dict[str, Any] = {"mode": mode, "attrs": attrs, "fds": fds}
        if mode == "closure":
            size = rng.randint(1, n - 1)
            params["query"] = sorted(rng.sample(attrs, size))
        return params

    def node_for(self, params: dict[str, Any]) -> str:
        if params["mode"] == "normal_form":
            return self._NODE_FOR_NF.get(self.canonical(self.solve_a(params)), "dbms.norm.ladder")
        return self._NODE_FOR_MODE[params["mode"]]

    def _key_str(self, params: dict, keys: list) -> str:
        parts = ["".join(sorted(k)) if not isinstance(k, int)
                 else "".join(ch for i, ch in enumerate(params["attrs"]) if k & (1 << i))
                 for k in keys]
        return ",".join(sorted(parts))

    def canonical(self, answer: Any) -> str:
        if isinstance(answer, (list, tuple, set, frozenset)):
            parts = ["".join(sorted(k)) if not isinstance(k, int) else str(k) for k in answer]
            # int masks can't be sorted as letters here — handled by check/keys canonical
            return ",".join(sorted(parts))
        return str(answer).strip().upper()

    def statement(self, params: dict[str, Any]) -> str:
        rel = f"R({', '.join(params['attrs'])})"
        fds = ", ".join(f"{''.join(lhs)} → {rhs}" for lhs, rhs in params["fds"])
        head = f"{rel} with functional dependencies **F = {{{fds}}}**\n\n"
        if params["mode"] == "closure":
            q = "".join(params["query"])
            return head + f"Compute the attribute closure **({q})⁺**. Answer as sorted letters with no spaces (e.g. `ABCD`)."
        if params["mode"] == "keys":
            return head + "List **every candidate key**. Each key as sorted letters; separate keys with commas; keys sorted alphabetically (e.g. `AB,ACD`)."
        return head + "State the **highest normal form** of R: 1NF, 2NF, 3NF, or BCNF."

    @property
    def input_spec_for_mode(self):
        return self.input_spec

    def solve_a(self, params: dict[str, Any]) -> Any:
        return _solve_a(params)

    def solve_b(self, params: dict[str, Any]) -> Any:
        out = _solve_b(params)
        if params["mode"] == "keys":
            # convert masks to string form for agreement
            return self._key_str(params, out)
        return out

    def agree(self, params: dict[str, Any], a: Any, b: Any) -> bool:
        if params["mode"] == "keys":
            return self._key_str(params, a) == b
        if params["mode"] == "closure":
            return "".join(a) == "".join(b)
        return str(a) == str(b)

    def canonical_answer(self, params: dict, answer: Any) -> str:
        if params["mode"] == "closure":
            return "".join(answer) if not isinstance(answer, str) else answer
        if params["mode"] == "keys":
            if isinstance(answer, str):
                return answer
            return self._key_str(params, answer)
        return str(answer)

    def answer_key(self, params: dict, answer: Any) -> str:
        return self.canonical_answer(params, answer)

    def check(self, params: dict[str, Any], answer: Any) -> bool:
        submitted = str(answer).strip().upper().replace(" ", "")
        key = self.canonical_answer(params, self.solve_a(params))
        if params["mode"] == "closure":
            return submitted == key
        if params["mode"] == "keys":
            # tolerate ordering: compare sets of sets
            def parse(s: str) -> set[frozenset[str]]:
                groups = [g for g in s.replace(";", ",").split(",") if g]
                return {frozenset(g) for g in groups}
            try:
                return parse(submitted) == parse(key)
            except Exception:
                return False
        return submitted in {"1NF", "2NF", "3NF", "BCNF"} and submitted == key

    def properties(self, params: dict[str, Any], answer: Any) -> list[tuple[str, bool]]:
        props: list[tuple[str, bool]] = []
        if params["mode"] == "closure":
            q = set(params["query"])
            props.append(("query_subset_of_closure", q <= set(answer)))
            props.append(("closure_within_attrs", set(answer) <= set(params["attrs"])))
            # monotonicity: closure of a superset contains the closure
            extra = [a for a in params["attrs"] if a not in q]
            if extra:
                bigger = _closure_sets(params["attrs"], params["fds"], q | {extra[0]})
                props.append(("monotone", set(answer) <= bigger))
        elif params["mode"] == "keys":
            if isinstance(answer, str):
                parts = answer.split(",")
            else:  # solve_a returns a list of frozensets
                parts = ["".join(sorted(k)) for k in answer]
            props.append(("keys_non_empty", len(parts) >= 1))
            for p in parts:
                c = _closure_sets(params["attrs"], params["fds"], set(p))
                props.append((f"key_{p}_determines_all", c == set(params["attrs"])))
                props.append((f"key_{p}_minimal", all(
                    _closure_sets(params["attrs"], params["fds"], set(p) - {ch}) != set(params["attrs"])
                    for ch in p
                )))
        else:
            props.append(("nf_valid", answer in NF_ORDER))
        return props

    def trace(self, params: dict[str, Any]) -> list[Step]:
        steps: list[Step] = []
        if params["mode"] == "closure":
            closure = set(params["query"])
            steps.append(Step(text=f"Start: closure = {{{', '.join(sorted(closure))}}}"))
            changed = True
            while changed:
                changed = False
                for lhs, rhs in params["fds"]:
                    if set(lhs) <= closure and rhs not in closure:
                        closure.add(rhs)
                        steps.append(Step(text=f"{''.join(lhs)} → {rhs} applies; closure = {{{', '.join(sorted(closure))}}}"))
                        changed = True
            steps.append(Step(text=f"Final ({''.join(params['query'])})⁺ = {''.join(sorted(closure))}"))
        else:
            ans = self.canonical_answer(params, self.solve_a(params))
            if params["mode"] == "keys":
                steps.append(Step(text="Find minimal attribute sets whose closure is all attributes."))
                steps.append(Step(text=f"Candidate keys = {ans}"))
            else:
                steps.append(Step(text="Compute candidate keys, then test each normal-form condition top-down (BCNF → 3NF → 2NF)."))
                steps.append(Step(text=f"Highest normal form = {ans}"))
        return steps

    def mistakes(self, params: dict[str, Any]) -> list[MistakeModel]:
        out: list[MistakeModel] = []
        key = self.canonical_answer(params, self.solve_a(params))
        attrs, fds = params["attrs"], params["fds"]

        if params["mode"] == "closure":
            # single pass over fds in stored order (no fixpoint)
            closure = set(params["query"])
            for lhs, rhs in fds:
                if set(lhs) <= closure:
                    closure.add(rhs)
            alt = "".join(sorted(closure))
            if alt != key:
                out.append(MistakeModel(
                    tag="no_transitive_closure", title="Stopped after one pass",
                    answer=alt,
                    feedback="Apply FDs repeatedly until nothing new is added — chaining (A→B, B→C) needs several passes.",
                ))
        elif params["mode"] == "keys":
            # every superkey, not just minimal ones
            full = set(attrs)
            supers = []
            for size in range(1, len(attrs) + 1):
                for combo in itertools.combinations(attrs, size):
                    if _closure_sets(attrs, fds, set(combo)) == full:
                        supers.append("".join(combo))
            alt = ",".join(sorted(supers))
            if alt != key:
                out.append(MistakeModel(
                    tag="superkey_as_key", title="Listed superkeys as candidate keys",
                    answer=alt,
                    feedback="Candidate keys must be minimal — drop any key that properly contains another key.",
                ))
        else:
            idx = NF_ORDER.index(key)
            # phantom violation: report a lower form than the truth
            if idx >= 1:
                out.append(MistakeModel(
                    tag="undercounted_nf", title=f"Said {NF_ORDER[idx - 1]} instead of {key}",
                    answer=NF_ORDER[idx - 1],
                    feedback="Recheck the defining condition of the higher form — you may have found a violation that isn't there.",
                ))
            # missed violation: claim a higher form than the truth
            if idx < 3:
                out.append(MistakeModel(
                    tag="missed_violation", title=f"Said {NF_ORDER[idx + 1]} instead of {key}",
                    answer=NF_ORDER[idx + 1],
                    feedback=f"You missed a violating FD — the highest form is {key}. Test every FD against the definition.",
                ))
        return out


register(FdClosure())
