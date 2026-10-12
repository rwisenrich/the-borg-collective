# V1 validation and claim boundaries

Date: 2026-10-12

This repository starts at V1.0, with a clean implementation rather than copying any previous DACO archive into Git history. Earlier experimental code supplied design lessons but is not part of this release.

Implemented: signed external AI identities, signed approved worker identities, unified hash-linked event history, SQLite task queue, three independent reasoning roles, trusted final integration, private-by-default volunteer and shared-memory opt-in, retries after lease expiry, request fair scheduling, model adapters, local detached mission return.

Not implemented: global permanent AI brain, distributed consensus, public P2P discovery, multi-host neural-model sharding, verified independent AI consciousness, uncontrolled autonomous replication, public production security.

Test command: `python -m unittest discover -s tests -v`.
