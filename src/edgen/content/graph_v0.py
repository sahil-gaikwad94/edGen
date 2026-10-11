"""Concept Graph v0 — the W0 scope: DBMS + OS.

Authored against the official GATE CSE syllabus topics, human-reviewable per
subject. This is the graph the concierge test (W0) runs on: enough structure for
a real placement diagnostic, skill tree, planner and Foundry-backed practice.

Node ids are dotted paths; ``generators`` names Foundry generators that can
produce verified practice for a node.
"""

from __future__ import annotations

# (id, title, prereqs, generators, est_minutes_standard, difficulty_prior)
# fmt: off
_RAW: list[tuple[str, str, list[str], list[str], int, float]] = [
    # ---------------- DBMS: foundations ----------------
    ("cs.dbms", "DBMS", [], [], 8, 0.3),
    ("cs.dbms.er", "ER model", ["cs.dbms"], [], 14, 0.35),
    ("cs.dbms.er.entity", "Entities and attributes", ["cs.dbms.er"], [], 8, 0.3),
    ("cs.dbms.er.relationships", "Relationships and cardinality", ["cs.dbms.er.entity"], [], 10, 0.4),
    ("cs.dbms.er.weak", "Weak entities and generalization", ["cs.dbms.er.relationships"], [], 10, 0.5),
    ("cs.dbms.er.to_relational", "ER-to-relational mapping", ["cs.dbms.er.weak"], [], 14, 0.55),
    ("cs.dbms.relational", "Relational model", ["cs.dbms"], [], 10, 0.35),
    ("cs.dbms.relational.relations", "Relations, tuples, domains", ["cs.dbms.relational"], [], 8, 0.3),
    ("cs.dbms.relational.keys", "Keys: super, candidate, primary, foreign", ["cs.dbms.relational.relations"], [], 10, 0.45),
    ("cs.dbms.relational.integrity", "Integrity constraints", ["cs.dbms.relational.keys"], [], 8, 0.4),
    ("cs.dbms.ra", "Relational algebra", ["cs.dbms.relational"], [], 12, 0.45),
    ("cs.dbms.ra.selection", "Selection and projection", ["cs.dbms.ra"], [], 8, 0.4),
    ("cs.dbms.ra.joins", "Joins: theta, equi, natural, outer", ["cs.dbms.ra.selection"], [], 12, 0.55),
    ("cs.dbms.ra.setops", "Union, intersection, difference", ["cs.dbms.ra.selection"], [], 8, 0.4),
    ("cs.dbms.ra.division", "Division and universal quantification", ["cs.dbms.ra.joins", "cs.dbms.ra.setops"], [], 12, 0.7),
    ("cs.dbms.calculus", "Relational calculus", ["cs.dbms.ra"], [], 10, 0.6),
    ("cs.dbms.calculus.trc", "Tuple relational calculus", ["cs.dbms.calculus"], [], 10, 0.65),
    ("cs.dbms.calculus.drc", "Domain relational calculus", ["cs.dbms.calculus"], [], 10, 0.65),

    # ---------------- DBMS: SQL ----------------
    ("cs.dbms.sql", "SQL", ["cs.dbms.relational"], [], 12, 0.4),
    ("cs.dbms.sql.ddl", "DDL and constraints", ["cs.dbms.sql"], [], 10, 0.4),
    ("cs.dbms.sql.dml", "DML: insert, update, delete", ["cs.dbms.sql"], [], 8, 0.4),
    ("cs.dbms.sql.select", "SELECT, WHERE, ORDER BY", ["cs.dbms.sql"], [], 10, 0.45),
    ("cs.dbms.sql.joins", "SQL joins", ["cs.dbms.sql.select", "cs.dbms.ra.joins"], [], 12, 0.55),
    ("cs.dbms.sql.aggregation", "GROUP BY, HAVING, aggregates", ["cs.dbms.sql.select"], [], 12, 0.6),
    ("cs.dbms.sql.subqueries", "Subqueries and correlated queries", ["cs.dbms.sql.aggregation"], [], 14, 0.7),
    ("cs.dbms.sql.views", "Views and materialized views", ["cs.dbms.sql.ddl"], [], 10, 0.5),
    ("cs.dbms.sql.triggers", "Triggers and assertions", ["cs.dbms.sql.views"], [], 10, 0.6),

    # ---------------- DBMS: normalization ----------------
    ("cs.dbms.normalization", "Normalization", ["cs.dbms.relational.keys"], [], 12, 0.5),
    ("cs.dbms.normalization.fd", "Functional dependencies", ["cs.dbms.normalization"], [], 10, 0.5),
    ("cs.dbms.normalization.fd_closure", "Attribute closure", ["cs.dbms.normalization.fd"], ["fd_closure@1"], 12, 0.55),
    ("cs.dbms.normalization.canonical_cover", "Canonical cover / minimal cover", ["cs.dbms.normalization.fd_closure"], [], 14, 0.7),
    ("cs.dbms.normalization.1nf", "1NF", ["cs.dbms.normalization.fd"], [], 8, 0.4),
    ("cs.dbms.normalization.2nf", "2NF", ["cs.dbms.normalization.1nf"], [], 8, 0.5),
    ("cs.dbms.normalization.3nf", "3NF", ["cs.dbms.normalization.2nf"], [], 10, 0.6),
    ("cs.dbms.normalization.bcnf", "BCNF", ["cs.dbms.normalization.3nf"], [], 12, 0.7),
    ("cs.dbms.normalization.4nf", "4NF and multivalued dependencies", ["cs.dbms.normalization.bcnf"], [], 12, 0.75),
    ("cs.dbms.normalization.5nf", "5NF and join dependencies", ["cs.dbms.normalization.4nf"], [], 12, 0.8),
    ("cs.dbms.normalization.decomposition", "Lossless and dependency-preserving decomposition", ["cs.dbms.normalization.bcnf"], [], 14, 0.75),

    # ---------------- DBMS: indexing ----------------
    ("cs.dbms.indexing", "Indexing and storage", ["cs.dbms.relational"], [], 10, 0.5),
    ("cs.dbms.indexing.storage", "Records, blocks, file organization", ["cs.dbms.indexing"], [], 10, 0.5),
    ("cs.dbms.indexing.dense_sparse", "Dense vs sparse indexes", ["cs.dbms.indexing.storage"], [], 10, 0.55),
    ("cs.dbms.indexing.bplus_height", "B+ tree structure and height", ["cs.dbms.indexing.dense_sparse"], ["bplus_height@1"], 14, 0.65),
    ("cs.dbms.indexing.bplus_ops", "B/B+ tree insert, delete, split", ["cs.dbms.indexing.bplus_height"], [], 14, 0.7),
    ("cs.dbms.indexing.hashing", "Static and dynamic hashing", ["cs.dbms.indexing.storage"], [], 12, 0.6),

    # ---------------- DBMS: transactions ----------------
    ("cs.dbms.transactions", "Transactions", ["cs.dbms.sql"], [], 12, 0.5),
    ("cs.dbms.transactions.acid", "ACID properties", ["cs.dbms.transactions"], [], 8, 0.45),
    ("cs.dbms.transactions.schedules", "Schedules and serializability", ["cs.dbms.transactions.acid"], [], 12, 0.65),
    ("cs.dbms.transactions.conflict", "Conflict serializability, precedence graph", ["cs.dbms.transactions.schedules"], [], 14, 0.7),
    ("cs.dbms.transactions.view", "View serializability", ["cs.dbms.transactions.conflict"], [], 12, 0.8),
    ("cs.dbms.transactions.2pl", "Two-phase locking", ["cs.dbms.transactions.conflict"], [], 12, 0.7),
    ("cs.dbms.transactions.timestamp", "Timestamp ordering", ["cs.dbms.transactions.conflict"], [], 12, 0.7),
    ("cs.dbms.transactions.mvcc", "Multiversion concurrency control", ["cs.dbms.transactions.timestamp"], [], 12, 0.8),
    ("cs.dbms.transactions.deadlock", "Deadlock in transactions", ["cs.dbms.transactions.2pl"], [], 10, 0.7),
    ("cs.dbms.recovery", "Recovery", ["cs.dbms.transactions.acid"], [], 12, 0.65),
    ("cs.dbms.recovery.log", "Log-based recovery, WAL", ["cs.dbms.recovery"], [], 12, 0.7),
    ("cs.dbms.recovery.checkpoint", "Checkpoints", ["cs.dbms.recovery.log"], [], 10, 0.7),
    ("cs.dbms.recovery.aries", "ARIES recovery", ["cs.dbms.recovery.checkpoint"], [], 14, 0.85),

    # ---------------- OS: processes ----------------
    ("cs.os", "Operating systems", [], [], 8, 0.3),
    ("cs.os.process", "Processes", ["cs.os"], [], 10, 0.35),
    ("cs.os.process.states", "Process states and PCB", ["cs.os.process"], [], 8, 0.4),
    ("cs.os.process.context_switch", "Context switching", ["cs.os.process.states"], [], 8, 0.45),
    ("cs.os.threads", "Threads", ["cs.os.process"], [], 10, 0.5),
    ("cs.os.threads.models", "Multithreading models", ["cs.os.threads"], [], 10, 0.55),
    ("cs.os.ipc", "Inter-process communication", ["cs.os.process"], [], 10, 0.55),

    # ---------------- OS: scheduling ----------------
    ("cs.os.scheduling", "CPU scheduling", ["cs.os.process"], [], 12, 0.5),
    ("cs.os.scheduling.metrics", "Throughput, turnaround, waiting, response", ["cs.os.scheduling"], [], 10, 0.5),
    ("cs.os.scheduling.fcfs", "FCFS", ["cs.os.scheduling.metrics"], [], 8, 0.45),
    ("cs.os.scheduling.sjf", "SJF and SRTF", ["cs.os.scheduling.metrics"], [], 12, 0.6),
    ("cs.os.scheduling.rr", "Round robin", ["cs.os.scheduling.metrics"], [], 10, 0.55),
    ("cs.os.scheduling.priority", "Priority scheduling", ["cs.os.scheduling.metrics"], [], 10, 0.55),
    ("cs.os.scheduling.mlfq", "Multilevel feedback queues", ["cs.os.scheduling.priority"], [], 12, 0.75),
    ("cs.os.scheduling.hrrn", "HRRN", ["cs.os.scheduling.sjf"], [], 10, 0.6),

    # ---------------- OS: synchronization ----------------
    ("cs.os.sync", "Process synchronization", ["cs.os.process"], [], 12, 0.55),
    ("cs.os.sync.critical", "Critical section problem", ["cs.os.sync"], [], 10, 0.55),
    ("cs.os.sync.peterson", "Peterson's solution", ["cs.os.sync.critical"], [], 10, 0.65),
    ("cs.os.sync.hardware", "Test-and-set, compare-and-swap", ["cs.os.sync.critical"], [], 10, 0.65),
    ("cs.os.sync.semaphore", "Semaphores", ["cs.os.sync.critical"], [], 12, 0.65),
    ("cs.os.sync.mutex", "Mutex locks and spinlocks", ["cs.os.sync.semaphore"], [], 10, 0.6),
    ("cs.os.sync.monitor", "Monitors and condition variables", ["cs.os.sync.semaphore"], [], 12, 0.7),
    ("cs.os.sync.classics", "Classical problems: producer-consumer, readers-writers, dining philosophers", ["cs.os.sync.semaphore"], [], 14, 0.75),

    # ---------------- OS: deadlock ----------------
    ("cs.os.deadlock", "Deadlock", ["cs.os.sync"], [], 12, 0.6),
    ("cs.os.deadlock.conditions", "Coffman conditions", ["cs.os.deadlock"], [], 8, 0.5),
    ("cs.os.deadlock.prevention", "Prevention and avoidance", ["cs.os.deadlock.conditions"], [], 12, 0.65),
    ("cs.os.deadlock_bankers", "Banker's algorithm", ["cs.os.deadlock.prevention"], ["bankers_safe@1"], 14, 0.7),
    ("cs.os.deadlock.detection", "Detection and recovery", ["cs.os.deadlock.prevention"], [], 10, 0.65),

    # ---------------- OS: memory ----------------
    ("cs.os.memory", "Memory management", ["cs.os"], [], 12, 0.5),
    ("cs.os.memory.contiguous", "Contiguous allocation and fragmentation", ["cs.os.memory"], [], 10, 0.55),
    ("cs.os.memory.paging", "Paging", ["cs.os.memory.contiguous"], [], 12, 0.6),
    ("cs.os.memory.tlb", "TLB and effective access time", ["cs.os.memory.paging"], [], 12, 0.7),
    ("cs.os.memory.segmentation", "Segmentation", ["cs.os.memory.paging"], [], 10, 0.6),
    ("cs.os.memory.virtual", "Virtual memory and demand paging", ["cs.os.memory.paging"], [], 12, 0.65),
    ("cs.os.page_replacement", "Page replacement algorithms", ["cs.os.memory.virtual"], ["page_replacement_fifo@1"], 14, 0.7),
    ("cs.os.page_replacement.lru", "LRU and stack algorithms", ["cs.os.page_replacement"], [], 12, 0.7),
    ("cs.os.page_replacement.optimal", "Optimal (Belady's)", ["cs.os.page_replacement"], [], 10, 0.65),
    ("cs.os.page_replacement.clock", "Clock / second-chance", ["cs.os.page_replacement.lru"], [], 10, 0.7),
    ("cs.os.memory.thrashing", "Thrashing and working set", ["cs.os.memory.virtual"], [], 12, 0.75),
    ("cs.os.cache_mapping", "CPU cache mapping", ["cs.os.memory"], ["cache_mapping@1"], 12, 0.6),
    ("cs.os.cache_replacement", "Cache replacement and write policies", ["cs.os.cache_mapping"], [], 10, 0.7),

    # ---------------- OS: file systems & IO ----------------
    ("cs.os.fs", "File systems", ["cs.os"], [], 12, 0.5),
    ("cs.os.fs.allocation", "Contiguous, linked, indexed allocation", ["cs.os.fs"], [], 12, 0.6),
    ("cs.os.fs.inode", "inodes and directory structure", ["cs.os.fs.allocation"], [], 12, 0.65),
    ("cs.os.fs.free_space", "Free space management", ["cs.os.fs.allocation"], [], 8, 0.5),
    ("cs.os.io", "I/O systems", ["cs.os"], [], 10, 0.5),
    ("cs.os.io.disk_scheduling", "Disk scheduling: FCFS, SSTF, SCAN, C-SCAN, LOOK", ["cs.os.io"], [], 14, 0.7),
    ("cs.os.io.disk_metrics", "Seek, rotational latency, transfer time", ["cs.os.io.disk_scheduling"], [], 10, 0.6),
]
# fmt: on


def nodes() -> list[tuple[str, str, list[str], list[str], int, float]]:
    return list(_RAW)
