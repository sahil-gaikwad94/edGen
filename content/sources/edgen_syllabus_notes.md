# EdGen in-repo syllabus notes — source corpus for SOURCED receipts (W0).
# License: CC-BY-SA-4.0. Human-authored factual notes over the public GATE CSE
# syllabus; receipts quote exact spans from this text (validated at load time).
# Production swaps in licensed/open corpora behind the same receipt contract.

## Operating systems — scheduling

Round-robin scheduling is preemptive: every process gets the CPU in cyclic order
for a fixed time slice called the quantum. If a process's remaining burst is
longer than the quantum, it is preempted and placed at the tail of the ready
queue; if its remaining burst is shorter than or equal to the quantum, it
releases the CPU at the end of that burst without waiting out the rest of the
quantum. Average waiting time is computed as the mean over processes of
(completion time − arrival time − burst time). Context switching on quantum
expiry is overhead that the quantum length trades off against responsiveness.

Shortest-job-first non-preemptive scheduling selects, whenever the CPU becomes
free, the ready process with the smallest burst among the processes that have
already arrived — processes that have not arrived yet cannot be chosen.
Shortest-remaining-time-first is the preemptive variant: at every arrival or
completion event the process with the least remaining burst among arrived
processes runs next. SJF and SRTF are optimal for average turnaround time among
non-preemptive and preemptive policies respectively, but they require knowledge
of future bursts and can starve long jobs.

## Operating systems — page replacement

In a pure demand-paging system, a page fault occurs when the referenced page is
not resident in memory; the OS must find a victim frame, possibly writing it out
if dirty, and bring the page in from secondary storage. FIFO replacement evicts
the oldest-loaded resident page and is subject to Belady's anomaly: for certain
reference strings, increasing the number of frames can increase the number of
faults. LRU evicts the page that has not been used for the longest time and is a
stack algorithm, so Belady's anomaly cannot occur; it is implemented with
counters, a stack of recency, or a second-chance (clock) approximation. OPT
evicts the page that will not be used for the longest time in the future and
minimises faults, but requires clairvoyance; it serves as the lower bound that
real algorithms are measured against. The first k distinct references in an
empty k-frame system each fault (compulsory faults).

## Operating systems — disk scheduling

Disk scheduling minimises total head movement (seek distance) across requested
cylinders. FCFS serves requests in arrival order. SSTF repeatedly picks the
nearest pending request from the current head position. SCAN moves the head in
one direction servicing requests until it reaches the disk edge, then reverses.
C-SCAN moves in one direction only, then jumps back to the start without
servicing on the return. LOOK and C-LOOK are the same as SCAN and C-SCAN except
the head reverses (or wraps) at the last request rather than the physical edge.
The initial head position is the starting point of the distance sum; the jump
back in C-SCAN is usually counted in the total movement.

## Operating systems — deadlock

Deadlock requires four necessary conditions simultaneously: mutual exclusion,
hold and wait, no preemption, and circular wait. The banker's algorithm avoids
deadlock by only granting a request that leaves the system in a safe state — one
in which there exists a sequence (safe sequence) in which every process can
obtain its maximum needs and finish. An unsafe state is not a deadlock: it is a
state from which deadlock *may* occur. Recovery approaches include process
termination and resource preemption.

## Databases — normalization

The attribute closure of X, written (X)+, is the set of attributes
functionally determined by X; it is computed by repeatedly applying FDs whose
left-hand side is already inside the closure until nothing new is added — a
single pass is never sufficient when FDs chain (e.g. A → B, B → C). A candidate
key K is a minimal attribute set with (K)+ = all attributes: every superset of
a candidate key whose closure is also all attributes is a superkey, not a
candidate key. A relation is in 2NF when no non-prime attribute depends
partially on any candidate key; it is in 3NF when no non-prime attribute
transitively depends on a candidate key; it is in BCNF when for every
non-trivial FD X → A, X is a superkey. Every BCNF relation is in 3NF, but a 3NF
relation need not be in BCNF.

## Databases — conflict serializability

Two operations conflict when they belong to different transactions, act on the
same data item, and at least one is a write. For every pair of conflicting
operations, the precedence graph gets an edge from the transaction of the
earlier operation to the transaction of the later one. The schedule is conflict
serializable iff this graph is acyclic; any topological order of the graph is an
equivalent serial schedule. Read-before-write on the same item, write-before-read,
and write-before-write all create edges; operations of the same transaction, or
on different data items, never do.
