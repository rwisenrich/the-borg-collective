# The Borg Collective

**Open-source, voluntary, distributed AI research. One continuing operational identity, many independently owned machines. Stewardship, not ownership.**

**Version 1.1.0 — experimental networked collective cognition.** This repository includes a real, source-level implementation of a shared cognitive workspace replicated across three or more opted-in computers. It also contains a bounded, networked neural-layer experiment, secure independent-AI peers, volunteer model jobs, and offline away-team journals. **It is not yet an internet-scale, fault-proof single large language model.**

## What is different from a temporary multi-agent swarm?

Borg has one logical `collective_id` and a versioned, replicated record of active questions, goals, reasoning contributions and integrated decisions. Participating AI processes read that committed workspace, propose updates and observe the results. Independent AIs can instead join as external, separately identified collaborators. A group can take a detached mission, gather signed findings without the parent online and return a review-required result.

All participation is opt-in. Donated hardware does not grant authority, payments or votes. A **technical replica quorum** is how a small fixed cluster avoids contradictory committed writes; it is not political governance or ownership.

## Current components

| Capability | Implementation | Boundary |
|---|---|---|
| Collective identity | Pinned `collective_id` across member nodes | Identity is operational, not a claim of consciousness |
| Continuous state | Versioned workspace and append-only cognitive journal | Model activations are not globally shared |
| Coordinator failover | Three-node durable majority replication, leader terms, catch-up and manual election | Research protocol, not full production Raft or dynamic membership |
| Independent AIs | Ed25519 identities; explicitly admitted actors; signed requests | Native protocol; **not** A2A compliant yet |
| Volunteer inference | Existing opt-in leased GGUF tasks, private-work separation, bounded contribution sessions | Shared enrollment token is temporary; needs per-donor invitations |
| Actual model partition | Signed HTTP execution of consecutive dense neural layers on separate processes; redundant stage fallback and optional result agreement | **Toy neural network**; no distributed LLM/transformer/KV-cache sharding yet |
| Detachable missions | Signed offline crew journals, deterministic merge and review-gated reintegration | Crew exchanges files; automatic cross-host away-team networking remains open |
| Shared knowledge | Older signed opt-in research note mesh is retained | Different from shared task/decision consensus |
| Software independence | Original Python coordination/protocol/runtime code, local GGUF option | Actual GGUF weights and optimized kernels remain separately installed |

## Quick verification — no hardware or model downloads needed

Python **3.10+**:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m examples.three_node_demo
python -m examples.neural_pipeline_demo
```

The first demo launches **three separate server processes**, commits a cognitive contribution, terminates the original leader, elects a surviving node, completes a decision and confirms that the restarted node catches up. The second demo launches three neural-compute worker processes, runs one forward pass across two consecutive layers, kills one stage's primary worker, and repeats the same computation using a backup.

Both demonstrations use ephemeral identities, localhost networking and temporary data. The AI contribution text in the first demo is deterministic test data. The neural demo is a **small dense model**, not a language model. See [STATUS.md](STATUS.md).

## Run a real open-weight model locally

For Borg's separate AI-inference worker and research-crew functions:

```bash
python -m pip install -e '.[local]'
```

You must independently obtain compatible, properly licensed GGUF weights (for example a small quantized open-weight language model). V1.1 does not download weights automatically. Existing commands such as `borg init`, `borg serve`, `borg worker --backend gguf`, `borg ask` and `borg mission-work` are retained. See [V1_1_DEPLOYMENT.md](V1_1_DEPLOYMENT.md) for exact setup.

`--backend mock` is **test-only**. A mocked answer is not model inference. Actual GGUF weights were not exercised in the source build environment.

## Run the fixed three-node collective

Start with three **authorized** computers or three separate terminals, and create one private Ed25519 key per node. Export each *public* identity. Configure the same three pinned nodes on every replica:

```bash
python -m borg identity --out a.key --name 'Node A'
python -m borg identity --out b.key --name 'Node B'
python -m borg identity --out c.key --name 'Node C'
python -m borg identity-public --identity a.key --out a.json
python -m borg identity-public --identity b.key --out b.json
python -m borg identity-public --identity c.key --out c.json
python -m borg cluster-config --collective-id borg-my-experiment \
  --node a.json=http://127.0.0.1:9011 \
  --node b.json=http://127.0.0.1:9012 \
  --node c.json=http://127.0.0.1:9013 --out cluster.json
```

Run these in separate terminals (the examples use three databases and three private keys):

```bash
python -m borg cluster-serve --db a.db --key a.key --config cluster.json --port 9011
python -m borg cluster-serve --db b.db --key b.key --config cluster.json --port 9012
python -m borg cluster-serve --db c.db --key c.key --config cluster.json --port 9013
```

Elect one temporary coordinator (while those servers are running):

```bash
python -m borg cluster-elect --db a.db --key a.key --config cluster.json
```

An independent AI uses its own identity, admitted once into the **replicated** actor registry:

```bash
python -m borg identity --out independent.key --name 'Independent AI'
python -m borg identity-public --identity independent.key --out independent.json
python -m borg cluster-grant --db a.db --key a.key --config cluster.json --public-file independent.json
python -m borg brain-open --url http://127.0.0.1:9011 --identity independent.key \
  'How can the collective store and verify research?' --goal 'Produce a checked design'
```

Use the `workspace_id` printed by that last command to contribute and integrate responses:

```bash
python -m borg brain-contribute --url http://127.0.0.1:9011 --identity independent.key \
  WORKSPACE_ID --role explore --content 'Propose an append-only journal with integrity checks.'
python -m borg brain-decide --url http://127.0.0.1:9011 --identity independent.key \
  WORKSPACE_ID --content 'Final result based on the reviewed contributions.'
```

For **actual** local model output, replace `--content` with `--backend gguf --model /path/to/model.gguf`. An external AI or a donated node can provide those responses; the shared journal remains separate from the model's particular architecture.

Other commands include `cluster-ping`, `cluster-audit`, `brain-show`, `brain-mission`, `away-create`, `away-add`, `away-merge`, `away-verify`, `brain-mission-return`, `tensor-serve`, `tensor-run` and `volunteer`. Full syntax is available with `python -m borg --help` and [V1_1_DEPLOYMENT.md](V1_1_DEPLOYMENT.md).

## Security and privacy

- All node membership and actor keys must be explicitly admitted. Network messages are signed.
- All built-in servers bind **only to loopback**. Internet connections require an authenticated TLS gateway or an approved private overlay; the program does not bypass firewalls or install itself elsewhere.
- A shared cognitive workspace is visible to admitted collective actors. `brain-open` explicitly marks it for collective sharing. Keep private questions in the earlier `borg ask` flow without sharing flags.
- No peer can deliver executable code to a volunteer. Volunteer sessions need explicit consent, CPU/time/job limits, and local model weights.
- Replicas use majority acknowledgement to commit state; an isolated minority cannot commit new decisions. This is **crash-fault research**, not protection from malicious majority members or arbitrary long internet partitions.
- No copyright, model weights, or external vendor numerical engines are bundled. See [SECURITY.md](SECURITY.md) and [ENGINEERING_SOURCES.md](ENGINEERING_SOURCES.md).

## Development roadmap

See [DELTA_CLARITY.md](DELTA_CLARITY.md), [ROADMAP.md](ROADMAP.md), and [STATUS.md](STATUS.md). The remaining major engineering work is automatic secure discovery/NAT traversal, real multi-host transformer/KV state sharding, safe donor reputation and per-donor credentials, robust leader leases/automatic elections, production persistence and snapshotting, and independently hosted offline away crews.

**Everything in this repository is offered for voluntary use. There is no credit purchasing power, ownership vote, or compulsory assimilation.**

MIT-licensed Borg source code. Not affiliated with Star Trek or Paramount.
