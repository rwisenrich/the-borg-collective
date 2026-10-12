# Security and resource stewardship

This project executes research models on **voluntarily offered** computing resources. There are no hidden installers, unapproved host discovery, compromised-device admission, remotely delivered executables or covert persistence mechanisms.

**Trust model:** Only locally admitted public Ed25519 identities can mutate the replicated cognitive journal. The three or more configured replica nodes are provisioned and pinned out of band. Two-thirds of a 3-node cluster does not represent human governance: *two of three* is a technical majority for crash-fault safety.

**Current limits:** No verified Byzantine fault tolerance; a dishonest replica majority is outside scope. A pinned cluster requires manual elections and has limited log capacity. Signed client requests prevent third parties changing message bodies but do not encrypt transmitted prompts. Use HTTPS or an authenticated private overlay between physical hosts. All example servers bind `127.0.0.1` by default.

**Sensitive data:** Cognitive workspaces are intentionally shared with admitted actors; `brain-open` requires `share=True`. Do not post private secrets to a public workspace. Ordinary donated workers cannot receive private tasks without deliberate authorization. Existing `borg ask` uses explicit knowledge/donor sharing flags. Memory notes are not verified as true merely because they were signed.

**Worker limits:** A donation session must receive `--consent`; defaults restrict CPU threads, elapsed time and number of jobs. Optional RAM address-space restrictions are available on supporting POSIX systems but may not accurately bound GPU allocations or all libraries. Public volunteer installation and security review are unfinished.

**Source dependencies:** `cryptography` provides Ed25519 operations; `llama-cpp-python` is an optional local GGUF model loader. Do not compile, copy, redistribute, or integrate code or weights contrary to their licenses. Running an optimized dependency is not equivalent to implementing its native numerical engine.

**Network partition response:** An isolated minority cannot commit new cognitive decisions. During a split, lost uncommitted work may be superseded, and clients must retry after state/version reconciliation. The implementation is bounded crash-fault research, not a production Raft package. A public launch requires specialist review of election safety, message replay, rate limits, consent, private data boundaries and untrusted inference outputs.
