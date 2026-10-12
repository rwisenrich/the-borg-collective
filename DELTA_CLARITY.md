# Delta Clarity — V1.0 to V1.1

**Highest-priority gap in V1.0:** Multiple machines could share a `collective_id` and research notes, but no majority-committed active reasoning state existed.

**V1.1 resolves this gap for a fixed, authenticated local cluster** by introducing a deterministic journal of collective workspaces and technical majority agreement over committed updates. The next step is WAN and scale testing, not claiming consciousness from coordinated software.

| Gap | Change in V1.1 | Evidence | Next gate |
|---|---|---|---|
| Parallel model calls lacked shared live state | `borg/quorum.py`, `borg/brain.py` | Concurrently accessible committed workspace/goal/contributions/decision | Shared activation/KV states |
| Coordinator failure stopped the work queue | Fixed 3-node leader election and durable journal | Kill/restart separate process, survivor commit, eventual catch-up | Production consensus, leases and membership changes |
| Could not split any neural computation | `borg/tensor.py` | Signed 2-layer dense network across processes; backup failover, verified replicas | Open-weight transformer sharding, state migration, WAN benchmarking |
| Offline missions had unsigned data | `borg/away.py` | Cryptographically verified independent crew entries; deterministic merge and audit | Autonomous multi-machine away networking |
| Public donated compute had weak limit controls | `borg/volunteer.py` | Session opt-in, CPU/time/job bounds and optional OS memory limit | Installer, more granular permissions, measured throughput |
| Donated resources could dominate scheduling | Existing equal actor scheduling plus V1.1 active-workspace limits | Donor contributions do not buy state authority | Anti-Sybil admission with privacy |

**What we explicitly did not do:** import huge proprietary libraries, decompile NVIDIA executables, bundle pretrained weights, deploy the network on public cloud, or create an uncontrolled autonomous agent population. Each of those is separate from the verified code in the repository.

## Next measurable milestone

Run three Borg nodes on three *different authorized physical computers* over authenticated TLS or an authorized private overlay; repeat leader loss and partition tests while gathering latency. Then run an actual open-weight quantized transformer on real donated resources and instrument layer/KV partition costs.
