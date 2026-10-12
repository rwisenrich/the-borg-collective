# Version 1 verification and boundaries

Date: October 12, 2026

This repository is the original clean Version 1. Earlier DACO packages are not imported as released source. The present changes move from vendor-specific adapters toward Borg's own signed node-to-node synchronization, local model execution, and offline research crews.

**Local automated tests:** 24 passing (Python unittest; includes mock/stubbed GGUF, not full model weights).

**Implemented:** one logical collective ID, native signed peer identity and message protocol, manual cross-installation admission, HTTP pull/push of explicitly opted-in content-addressed research notes, SQLite persistent scheduling, donated-model jobs, trusted worker token separation, independent external AI identities, parallel three-role reasoning and trusted integration, offline three-role mission report creation and review-gated reunion.

**Not implemented:** provider-independent raw transformer kernels, automatic P2P DHT/discovery, serverless consensus and replicated task queues, model parallelism across a physical network, a verified production global collective mind, a public free hosting service, or unbounded self-replication.

**Security model:** Loopback-only server by default. Transport to nonlocal hosts requires HTTPS. Mesh peers must exchange Ed25519 public identities by an explicit trust step; exchanged text is limited to opted-in research notes. Volunteer workers cannot request trusted privileges with only the ordinary donation token. No remote arbitrary-code or hidden installation endpoints.

**Known limitations:** `mesh-sync` replicates add-only research notes and does not form consensus on global decisions. Replicated unverified notes can be inaccurate. The local coordinator is a single writer for its own requests and work queue; losing it stops that queue until restarted. GGUF runtime integration has a mocked interface test but needs a machine with installed model weights for true inference validation.
