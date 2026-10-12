# Software research -> Borg native engineering map

The design uses published source code and documented algorithms as references. The Borg V1 source is newly written; it does **not** copy/vend third-party engine code or claim to include those full engines. When adapting code directly, its specific license and attribution requirements must be preserved. Open source normally makes binary decompilation unnecessary.

| Research source / pattern | Borg implementation now | Remaining distinction |
|---|---|---|
| [NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo): distributed inference routing | Independent worker scheduling, leases and model-agnostic backends | No NVIDIA required or bundled; prefill/decode and KV-cache redistribution not implemented |
| [Petals](https://github.com/bigscience-workshop/petals): voluntarily hosted transformer partitions | Opt-in workers and parallel collective tasks | Does not partition one transformer across donated GPU nodes yet |
| [llama.cpp](https://github.com/ggml-org/llama.cpp): efficient GGUF inference | Optional local direct GGUF execution through `llama-cpp-python` | Mathematical kernels/weights remain a separately installed and licensed dependency |
| [libp2p](https://github.com/libp2p): peer identification and message exchange | Native Ed25519 identities, signed peer exchange, manual trusted-peer discovery | No Kademlia DHT, NAT traversal or libp2p transport conformance yet |
| [Automerge](https://github.com/automerge/automerge): local-first eventual synchronization | Content-addressed, add-only, two-way replicated research notes | Not a general CRDT with arbitrary edits or consensus for task state |
| [Temporal](https://github.com/temporalio/temporal): durable workflows | SQLite leases, job retry and restart persistence | No replicated workflow authority, transactional cross-node recovery, or Temporal runtime |
| [BOINC](https://github.com/BOINC/boinc): voluntary donor compute | Explicit admission, opt-in model work, contributor resource independence | No public installer / measured donated-resource accounting yet |
| [Conway Automaton](https://github.com/Conway-Research/automaton): evolving autonomous agents / lineage | Separate AI identities, detachable reviewed mission reports | No self-hosting descendant provisioning or automatic code mutation/deployment yet |
| Open AI interoperability protocols such as [A2A](https://a2a-protocol.org/) | Independently signed external AI peers | Native protocol is **not** A2A compliant; adapter tests remain to be built |

## Compatibility and rights

- Borg's own runtime is MIT licensed. It contains no automatically downloaded third-party weights and no copied vendor inference engine.
- Libraries may be used when their licenses permit. The exact library version/license and any model-weight license must be checked before redistributing third-party files.
- Recompilation does not cancel copyright, trademark, or contractual restrictions. We can adapt compatible open-source code with notices, or independently implement documented algorithms.
- All external resource sharing is by explicit opt-in; donor devices do not run arbitrary remotely submitted executables.

## Honest engineering status

The code now includes an original two-way signed **knowledge** mesh, not a full consensus-backed distributed neural mind. The global-workspace problem, inference sharding, trust/reputation, private computation on donated hardware, strong volunteer resource limits, and multi-machine disconnected sub-collectives remain the substantial research and engineering work.
