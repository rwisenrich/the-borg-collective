"""Portable Ed25519 peer identities and signed protocol envelopes."""
import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def encode(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def decode(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def identity_id(public):
    return "peer-" + hashlib.sha256(decode(public)).hexdigest()[:24]


def create_identity(path, name):
    path = Path(path)
    if path.exists():
        raise FileExistsError("Identity already exists")
    priv = Ed25519PrivateKey.generate()
    raw_priv = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    raw_pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    obj = {"name": name, "secret": encode(raw_priv), "public": encode(raw_pub), "id": identity_id(encode(raw_pub))}
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=2)
    return {"id": obj["id"], "name": name, "public": obj["public"]}


def load_identity(path):
    obj = json.loads(Path(path).read_text())
    priv = Ed25519PrivateKey.from_private_bytes(decode(obj["secret"]))
    real_pub = encode(priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    if real_pub != obj["public"] or identity_id(real_pub) != obj["id"]:
        raise ValueError("Identity key mismatch")
    return obj


def signed(identity, action, body):
    unsigned = {"id": identity["id"], "public": identity["public"], "action": action,
                "ts": int(time.time()), "nonce": secrets.token_hex(16), "body": body}
    priv = Ed25519PrivateKey.from_private_bytes(decode(identity["secret"]))
    return {**unsigned, "signature": encode(priv.sign(canonical(unsigned)))}


def verify(envelope, action, window=300):
    if envelope.get("action") != action:
        raise ValueError("Action mismatch")
    if abs(int(time.time()) - envelope["ts"]) > window:
        raise ValueError("Expired message")
    if not isinstance(envelope.get("nonce"), str) or len(envelope["nonce"]) != 32:
        raise ValueError("Invalid nonce")
    if identity_id(envelope["public"]) != envelope["id"]:
        raise ValueError("Identity mismatch")
    unsigned = {k: envelope[k] for k in ("id", "public", "action", "ts", "nonce", "body")}
    try:
        Ed25519PublicKey.from_public_bytes(decode(envelope["public"])).verify(
            decode(envelope["signature"]), canonical(unsigned))
    except (InvalidSignature, ValueError) as exc:
        raise PermissionError('Invalid message signature') from exc
    return envelope["id"]
