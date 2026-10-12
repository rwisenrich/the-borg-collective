# Collective roadmap

## V1.0 (this repository) — implemented and locally testable
- Original clean Python implementation, signed independent peer identities, voluntary node admission, common event history, private-by-default requests.
- Concurrent *capable* reasoning branches: explore, challenge, verify; model workers may operate on different machines. Trusted integration generates the single response.
- Ollama and OpenAI-compatible adapters; Dynamo/vLLM are external inference services, not bundled engines.
- Detached offline mission reports imported only as review-gated evidence.

## Next: V1.1 — safe external pilot
- HTTPS gateway with explicit coordinator/domain configuration, quotas and stronger abuse defenses.
- Per-node resource limits, capability attestation, signed worker updates, human-friendly donor client.
- End-to-end multi-computer tests with actual independent model hosts; private result routing, manual revocation.
- Standard A2A interoperability adapter and specification tests.

## Later: V2 — decentralized collective continuity
- libp2p peer discovery and authenticated encrypted transports.
- Replicated collective event history, consensus / leader election, quorum-based state commits, snapshot verification.
- Network partition and recovery tests: no conflicting authoritative states, offline mission merge and review.
- Robust confidentiality boundaries for donated hardware and peer-access protocols.

## Later: V3 — deep distributed cognition
- Integrate Petals-like model partitioning or NVIDIA-based multi-node inference with benchmarked communication costs.
- Incremental common workspace, memory retrieval, model/context consistency and verified synthesis.
- Multi-node away collectives that operate offline and later reconcile cryptographically signed findings.
- Separate-identity child systems only through explicit authorized provisioning and operator-controlled resources.

**No step assumes commandeering devices, evading platform terms, or making permanent copies on machines without consent.**
