# Version 1.1 operating guide

Start with the runnable [README](README.md) demos. These are repeatable on one development machine and do not require downloading model weights or renting cloud infrastructure.

## Reproducible demos

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m examples.three_node_demo
python -m examples.neural_pipeline_demo
```

The first runs three **independent operating-system processes** with separate SQLite files. The second runs a separate signed numeric model-layer service on each process and can fail over a stage.

## Connect independent AIs

Create an Ed25519 identity with `python -m borg identity`, export its public JSON, and have a replica admit it using `cluster-grant` while its leader has a quorum. The admission itself is journaled, so the independent AI can contact the replacement coordinator after a crash. Interoperability is the Borg signed JSON interface, not A2A 1.0.

To contribute live model-generated reasoning after `brain-open`:

```bash
python -m borg brain-contribute --url http://127.0.0.1:9011 --identity independent.key \
  WORKSPACE_ID --role verify --backend gguf --model /path/to/model.gguf
python -m borg brain-decide --url http://127.0.0.1:9011 --identity independent.key \
  WORKSPACE_ID --backend gguf --model /path/to/model.gguf
```

These two commands each independently read committed shared context before inferring and then propose a version-checked update. If another contributor commits between the read and submit, refresh and recompute; the stale update is rejected instead of silently overwriting a thought.

## Truly disconnected signed away mission

After `brain-mission`, use the returned mission ID. Members who hold authorized private keys can prepare an offline mission file (a public roster is included, never private keys):

```bash
python -m borg away-create --url http://127.0.0.1:9011 --identity independent.key \
  --mission-id MISSION_ID --crew-public crew-a.json --crew-public crew-b.json --out mission.json
```

Copy `mission.json` to two disconnected computers; each writes its own signed observation:

```bash
python -m borg away-add --input mission.json --identity crew-a.key --role explore \
  --content 'First independent finding' --out crew-a.json
python -m borg away-add --input mission.json --identity crew-b.key --role verify \
  --content 'Independent verification' --out crew-b.json
```

Later exchange these files through a medium the users choose (no always-on connection to the parent is required):

```bash
python -m borg away-merge --input crew-a.json --input crew-b.json --out reunited.json
python -m borg away-verify --input reunited.json
python -m borg brain-mission-return --url http://127.0.0.1:9011 --identity crew-a.key \
  --bundle reunited.json --report 'Reviewed synthesis of the evidence'
```

Every crew public identity must be in the mission roster and each returning member must be admitted to the collective. Successful return retains status **returned-unreviewed**, not automatically promoted to established facts. The bundled journal must fit the bounded request size for the prototype.

## Donate a computer voluntarily

Your machine needs a compatible **local** GGUF model and an admission token provided by the operator. A bounded session:

```bash
export BORG_ADMISSION_TOKEN='individual-admission-capability'
python -m borg volunteer --url https://example-authorized-borg-endpoint.invalid \
  --identity donor.key --model /path/to/your/model.gguf \
  --threads 2 --minutes 30 --max-jobs 10 --consent
```

This is a *template*, not a deployed Borg public endpoint. Operators must replace the placeholder with their own authenticated URL; free hosting is not provisioned by this repository. The current token enrollment method is suitable only for a small trusted test; public onboarding needs unique revocable donor credentials.

## Distributed neural layer demonstration

Workers first load locally configured numeric weights. Example `layer.json`:

```json
{"weights": [[0.2, 0.5], [-0.3, 0.1]], "bias": [0.1, 0.0], "activation": "relu"}
```

Start a numeric layer service with a requester allowlist:

```bash
python -m borg tensor-serve --weights layer.json --allow-client requester-public.json --port 9111
```

Start a **different** layer on another machine and call:

```bash
python -m borg tensor-run --identity requester.key \
  --stage http://127.0.0.1:9111 --stage http://127.0.0.1:9112 --input '[1.2,0.5]'
```

A stage can have comma-separated backup URLs; use `--verify-replicas` only with at least three instances per stage to require two numerically matching results. These are real numerical neural layers, **not** an open-weight language model running sharded transformer attention.

## Remote operation boundary

The software binds only to localhost. For three distant machines, install an authenticated private mesh/overlay or TLS reverse proxy operated with explicit permission, expose only the required endpoints, and update the fixed node URL roster consistently across all three copies. Do not publicly expose the experimental HTTP servers. No internet-wide DHT/NAT traversal is bundled yet.
