# Borg Collective V1.1 — verified status

Date: October 12, 2026

- Core platform: **RUNNABLE** (Python 3.10+, cryptography dependency).
- Old V1.0 compatibility: earlier signed volunteer endpoints, GGUF/Ollama connectors, separate research-note mesh retained.
- New cognitive journal: **LOCALHOST THREE-NODE PASS** — fixed-membership Ed25519 replicas, majority-committed log, term-based manual elections, stale leader rejection, follower catch-up, recovery with current-term no-op, revision checks and local digest audits.
- New unified workspace: **PASS** — opt-in shared questions/goals, actor contributions, integrated decisions; replicated content survives the original coordinator's loss. Still not one continuously shared neural activation state.
- New offline away crew: **PASS** — separate authorized identities produce signed contributions, deterministic file merge, tamper and outsider rejection, then review-required return to a recovered collective. No automatic multi-machine crew transport.
- New networked layer computation: **PASS, SMALL NETWORK** — two real dense neural layers run as distinct HTTP services, forward pass matches local calculation; alternate stage worker survives primary-process termination. Optional two-matching-replica verification rejects a single malicious/incorrect output.
- New volunteer donation session: **PASS, preflight-only tests** — opt-in, time/job/CPU limits; optional POSIX RAM address-space limit; a public downloader/UI not built.
- New full-process demo: **PASS** — three distinct OS server processes, coordinator killed and restarted, committed cognitive state identical across all three after catch-up.
- All regression tests: run `python -m unittest discover -s tests -v` for current count.

## Unresolved engineering gates

1. **OPEN:** Real language-model layer/tensor/KV-cache sharding across unrelated donated machines, with acceptable WAN latency and privacy.
2. **OPEN:** Production Raft-grade automatic elections, leader leases, membership changes, snapshots, and safety testing under network delay/crashes.
3. **OPEN:** Public-internet discovery and NAT traversal, abuse mitigation, signed distribution, per-volunteer admission credentials, remote credential recovery.
4. **OPEN:** Direct independent-AI A2A protocol compliance (current interface is signed Borg JSON, not full A2A).
5. **OPEN:** Autonomously communicating multi-machine away crews while isolated from the home collective (current crews merge signed files).
6. **OPEN:** Reproducible real GGUF/quantized transformer model execution on donated physical hardware; models not embedded.
7. **OPEN:** External security audit and WAN multi-host end-to-end test.

This is experimental research code, **not** a commercial-ready AI cloud service, a proven globally decentralized mind, or a self-replicating network.
