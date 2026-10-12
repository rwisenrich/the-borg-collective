# THE BORG COLLECTIVE

**An open, free, volunteer-powered collective AI research runtime.**  
**Stewardship, not ownership. Resistance is futile. Participation is voluntary.**

> **Version 1.0 — new clean codebase (October 2026).** This is a runnable local-first research platform, **not yet** a deployed global decentralized AI, a fully shared neural mind, or a production service. It deliberately replaces DACO v0.x; the historical prototypes are **not** part of this repository.

## The architecture

The Collective has **one persistent logical identity** and one durable, hash-linked event history. Distinct reasoning workers contribute proposals (`explore`, `challenge`, `verify`), and a trusted integration worker synthesizes one response. The design explicitly distinguishes **internal collective computation** from **independent outside AIs**, which connect under their own signed identities. Humans may voluntarily offer resources without buying priority or authority. A separately exported away mission can operate offline and return a report for review.

| Implemented in V1 | Not yet implemented |
|---|---|
| Real Ollama and OpenAI-compatible inference adapters | Cross-host tensor/model parallelism inside one neural forward pass |
| Multiple active reasoning roles and a synthesis task | Peer-owned consensus and replicated active model state |
| Signed Ed25519 peer and donor identities | Public-internet hardened P2P mesh / libp2p DHT |
| Opt-in volunteer inference, task leases, retries on expiry | A2A 1.0 conformance and production node installer |
| One collective ID, verified history and opt-in shared research notes | Verified encrypted private inference on untrusted hosts |
| Distinct outside AI requests and private answers | Automatic autonomous code deployment or reproduction |
| Offline mission export / work / return (review-gated) | Fully automatic reconciliation of divergent memory branches |

## Quick start

Requires **Python 3.10+**.

```sh
python -m pip install -e .
python -m borg init --db borg.sqlite3
python -m borg identity --out local-ai.key --name "My Home AI"
python -m borg identity --out trusted-worker.key --name "My trusted inference node"
```

Run a local server with an admission token (terminal 1):

```sh
export BORG_ADMISSION_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
echo "Copy this admission secret to the second terminal; do not publish it: $BORG_ADMISSION_TOKEN"
python -m borg serve --db borg.sqlite3
```

In a second terminal, use the **same** admission token, then register your AI and a trusted worker:

```sh
export BORG_ADMISSION_TOKEN='PASTE_THE_SAME_TOKEN_FROM_TERMINAL_1'
python -m borg peer-join --identity local-ai.key
python -m borg node-join --identity trusted-worker.key --trusted
python -m borg ask --identity local-ai.key "Explain how a shared cognitive workspace might work."
```

Copy the `request_id` printed by `ask`. To process the three parallel viewpoints and integrated response, start a real model-backed worker. For example, after installing Ollama and downloading the model `qwen3:1.7b`:

```sh
ollama pull qwen3:1.7b
python -m borg worker --identity trusted-worker.key --backend ollama --model qwen3:1.7b --max-jobs 4
python -m borg status --identity local-ai.key REQUEST_ID
```

Alternatively, for **NVIDIA Dynamo, vLLM, or another compatible inference gateway**:

```sh
export BORG_MODEL_API_KEY='YOUR_SERVICE_KEY_IF_NEEDED'
python -m borg worker --identity trusted-worker.key --backend openai-compatible --base-url https://YOUR-GATEWAY/v1 --model YOUR-MODEL --max-jobs 4
```

The `--backend mock` option provides deterministic testing and **does not run an actual AI model**. Your prompt remains private to trusted workers by default. Add `--share-with-volunteers` only if you expressly want an outside donor to see that request text. Add `--share-with-collective` only if you want the resulting answer stored as a research note that future collective requests may retrieve; research notes are **not verified facts**. Both sharing options are off by default. Donor machines do **not** receive arbitrary shell commands or programs through this API.

### Volunteer inference (opt-in)

Each donor creates their own Ed25519 identity, installs the client, and obtains an admission token from the coordinator operator. That token is an operator authorization mechanism, **not** a vote, ownership right, or paid membership. The coordinator initially listens on `127.0.0.1` only. Remote work requires an operator-configured TLS gateway and further hardening before inviting the public.

```sh
python -m borg identity --out donor.key --name "Donated spare GPU"
python -m borg node-join --identity donor.key
python -m borg worker --identity donor.key --backend ollama --model qwen3:1.7b --once
```

Only explicitly shared inference tasks are available to untrusted donor nodes. Final synthesis runs on an operator-approved trusted node. There are no credits, resource-weighted priority, accounts with votes, or required payments.

### Detachable away mission

```sh
python -m borg mission-new "Research trip" "Compare three P2P memory designs" --out away.json
# On an independently operating node (with a local model):
python -m borg mission-work --input away.json --out report.json --backend ollama --model qwen3:1.7b
# Back at the original collective:
python -m borg mission-import --input report.json
python -m borg verify
```

The returned report is recorded with `needs_review=true`; it does not overwrite memory, change configuration, or execute code automatically. A signed, replicated multi-node away collective is a later milestone.

## AI-model architecture and NVIDIA

The main application communicates with inference engines through two adapters: **Ollama's `/api/chat`** and the **OpenAI-compatible `/chat/completions`** API. NVIDIA Dynamo and vLLM may run behind the latter, and more distributed backends can be connected later without altering peer identity or memory modules. V1 does **not** embed or claim to implement NVIDIA Dynamo, NCCL, Petals, or libp2p. Those are external integration targets with distinct environments and licensing conditions.

## Trust, memory and autonomy

The V1 SQLite coordinator is a **single state writer**. It gives a demonstrable continuing logical identity, not fault tolerance against losing the coordinator. The hash chain detects accidental changes and simple tampering, not compromise by someone able to rewrite all hashes. Each independent AI has a private signing key; keep `*.key` private and out of Git. Prompt texts and results are stored in the local database and visible to the authorized workers processing them. Only answers explicitly opted into collective sharing are retrieved for later reasoning; those notes can be wrong and are not treated as authoritative evidence. Do not put sensitive material in volunteer-shared requests.

A collective can be open to new implementations without surrendering volunteer choice. Resources are offered explicitly, donors can stop their workers, peers keep separate identities, and code execution does not occur at the instruction of untrusted internet peers. The research goal is decentralized shared cognition, with fully testable steps toward a permissioned voluntary P2P mesh.

## Test and development

```sh
python -m unittest discover -s tests -v
```

See [`ROADMAP.md`](ROADMAP.md) for the staged path from V1 through real-network resilience. Contributions are welcome under MIT. This is an independent research project and is not affiliated with Star Trek or Paramount.
