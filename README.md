# THE BORG COLLECTIVE

**One continuing distributed AI research collective. Free software. Voluntary resources. Stewardship, not ownership.**

> **Version 1.0 — native Borg runtime.** This repository is the clean starting point, not the earlier DACO prototype series. Borg is independent of NVIDIA, any specific cloud provider, any commercial inference API, and any particular language model. **Borg does not yet implement a fully distributed neural forward pass, worldwide discovery, or consensus-backed survival after all coordinating nodes fail.**

The goal is a single collective identity, distributed reasoning and durable memory, volunteer computing, independent AI peers, and detachable away crews that reconnect with reviewed discoveries. Participating independent AIs may remain independent; joining the shared cognitive system is a separate choice. No voting, ownership credits, or payment system is required.

## What's actually built

| Working V1 components | Engineering still to do |
|---|---|
| Original signed peer and volunteer-worker protocol | Public internet-scale libp2p/DHT discovery and NAT traversal |
| Separate AI identities and voluntary compute admission | Fully decentralized authority and quorum-based task continuity |
| Direct local GGUF inference via optional `llama-cpp-python` | Native distributed transformer model/layer execution |
| Optional local Ollama / generic HTTP model backends | Memory-safe execution of arbitrary third-party tools |
| Parallel explorer, challenger, verifier and one answer integrator | Dynamic model-level sharding across volunteered GPUs |
| Opt-in, replicated notes between trusted Borg nodes | General replicated shared working-state consistency |
| Durable SQLite task leases, restart persistence and event hashes | Internet-scale volunteer scheduling, peer reputation and abuse controls |
| Three-role detached offline research crew and review-gated return | Distributed, independently operating multi-machine away crews |

**Important distinction:** The integration/runtime/protocol layers are Borg source code. Large neural models and optimized inference kernels are separate components. We can study and modify appropriately licensed implementations, but we do not claim to have recompiled every open-source project into the V1 repository. See [ENGINEERING_SOURCES.md](ENGINEERING_SOURCES.md).

## Installation

Python **3.10+**:

```bash
python -m pip install -e .
python -m borg --help
```

For **direct model inference on your own CPU/GPU**, install the optional GGUF backend:

```bash
python -m pip install -e '.[local]'
```

Supply your own compatible licensed `.gguf` model weights. For example, use a small quantized model on an older laptop. Set `BORG_CPU_THREADS` (default 4), `BORG_GPU_LAYERS` (default 0), and `BORG_CONTEXT_SIZE` (default 2048) if appropriate. These are local resource limits; Borg does not download models or weights automatically.

## Start one local collective

```bash
python -m borg init --db borg.sqlite3
python -m borg identity --out ai.key --name "Home AI"
python -m borg identity --out worker.key --name "Trusted local worker"
```

Set distinct enrollment secrets for **ordinary donated workers** and **trusted workers**. Generate fresh random values; the strings below are placeholders, not credentials to use:

```bash
export BORG_ADMISSION_TOKEN='YOUR_RANDOM_VOLUNTEER_TOKEN'
export BORG_TRUSTED_WORKER_TOKEN='YOUR_OTHER_RANDOM_TRUSTED_TOKEN'
python -m borg serve --db borg.sqlite3
```

In another terminal with the **same tokens**, join and ask:

```bash
python -m borg peer-join --identity ai.key
python -m borg node-join --identity worker.key --trusted
python -m borg ask --identity ai.key "Analyze how a decentralized collective could store shared research."
```

To process the tasks **without any NVIDIA service**, run a local GGUF model in a third terminal:

```bash
python -m borg worker --identity worker.key --backend gguf --model /path/to/your/model.gguf --max-jobs 4
python -m borg status --identity ai.key REQUEST_ID
```

To use an existing local model service instead: `--backend ollama --model qwen3:1.7b`. The `--backend mock` option is useful for repeatable tests; **it is not an AI**. A standard chat-completions HTTP interface is available as `--backend http-api --base-url HTTPS_OR_LOOPBACK_URL --model MODEL_NAME`; no service is required by Borg itself.

Prompts are private to trusted workers by default. `borg ask --share-with-volunteers` explicitly permits donated machines to read that question. `--share-with-collective` explicitly permits the completed answer to become a research note used by other collective requests and replicated to invited peers. Unverified research notes are labeled as such; they are not automatically accepted as scientific fact.

## Connect two Borg nodes directly

This implements **actual bidirectional, authenticated knowledge exchange** between two distinct Borg databases. It is not yet public DHT discovery or global task consensus.

First create the home Borg database and remember the printed `collective_id`:

```bash
python -m borg init --db home.db
python -m borg identity --out home.key --name "Home node"
python -m borg identity-public --identity home.key --out home-public.json
```

Then set up a second *voluntary* node using the **same** collective identity:

```bash
python -m borg init --db cloud.db --collective-id YOUR_COLLECTIVE_ID
python -m borg identity --out cloud.key --name "Second node"
python -m borg identity-public --identity cloud.key --out cloud-public.json
```

Each node's steward exchanges **public identity files**, not private keys. Trust each other explicitly:

```bash
python -m borg mesh-trust --db home.db --public-file cloud-public.json
python -m borg mesh-trust --db cloud.db --public-file home-public.json
```

On the home machine (or in a first local terminal):

```bash
python -m borg serve --db home.db --identity home.key --port 8787
```

On the second machine (or in a second terminal) run:

```bash
python -m borg mesh-sync --db cloud.db --identity cloud.key --url http://127.0.0.1:8787
```

`mesh-sync` pulls and pushes **only explicitly opted-in research notes**. For a continuing visible process, add `--watch --interval 30`. For genuinely remote machines, use a manually configured HTTPS reverse proxy or authenticated overlay network, not plaintext HTTP. The bundled server deliberately listens only on loopback. It does not silently connect, spread, or run commands on volunteer devices.

## Detached away mission

```bash
python -m borg mission-new "Distributed memory study" "Compare 3 local-first memory designs" --db home.db --out away.json
# The next command works offline with a locally installed model:
python -m borg mission-work --input away.json --out report.json --backend gguf --model /path/to/model.gguf
# Reconnect later and review results before incorporation:
python -m borg mission-import --db home.db --input report.json
```

The detached worker creates three different research perspectives, then a synthesis. It can run while disconnected from the parent collective. The resulting report remains subject to review; it does not silently overwrite shared memory or deploy code. A **multi-machine** detached sub-collective still needs engineering.

## Tests

```bash
python -m unittest discover -s tests -v
```

The test suite covers signed peers, private prompts, volunteer permissions, real HTTP task exchange, fault retries, shared opt-in memory, two-node mesh replication, rejection of untrusted peers, tamper checks, and detached crew operation. Local GGUF integration is tested with a simulated model interface; a real model weight file was **not** run in the test environment.

## Project stance

The collective is free and voluntary. Nobody acquires control by donating extra computers. An independently developed AI may connect without surrendering its own identity. Peer admission is consent and resource protection, **not a voting system**. Nodes are never permitted to commandeer devices, hide their operation, or execute arbitrary programs supplied by strangers.

MIT-licensed Borg integration code. Model weights and separately installed engines retain their own licenses. See [STATUS.md](STATUS.md), [ROADMAP.md](ROADMAP.md) and [ENGINEERING_SOURCES.md](ENGINEERING_SOURCES.md). This is an independent research project, not affiliated with Star Trek or Paramount.
