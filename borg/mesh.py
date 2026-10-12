"""Borg's first native peer-to-peer knowledge exchange.

Only explicitly shared research notes are exchanged. This is replicated
append-only *knowledge*, not consensus for tasks, funds, or authoritative
collective decisions. Peers must opt in and exchange public keys.
"""

import hashlib
import json
import time
from .crypto import canonical, identity_id, signed, verify

PAGE = 8
MAX_NOTE = 4000
MAX_PAGES = 256


def digest(note):
    return hashlib.sha256(note.encode('utf-8')).hexdigest()


def public_identity(identity):
    return {key: identity[key] for key in ('id', 'public', 'name')}


def check_public(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get('name'), str):
        raise ValueError('Invalid public identity')
    if not isinstance(obj.get('public'), str) or not isinstance(obj.get('id'), str):
        raise ValueError('Invalid public identity')
    if identity_id(obj['public']) != obj['id']:
        raise ValueError('Public identity does not match fingerprint')
    return obj


def sync(store, identity, remote_url):
    """Bidirectional, authenticated, bounded sync of opt-in research notes.

    All remote calls use HTTPS except for local loopback development.
    Each direction uses separately signed envelopes and per-message nonces.
    """
    from .client import post
    imported = exported = 0
    cursor = ''
    for _ in range(MAX_PAGES):
        packet = post(remote_url, '/v1/mesh/pull', signed(identity, 'mesh.pull', {
            'collective_id': store.collective_id(), 'after': cursor,
        }))
        merged = store.mesh_import(packet)
        imported += merged['imported']
        body = packet['body']
        next_cursor = body['next_after']
        if not body['has_more']:
            break
        if next_cursor <= cursor:
            raise ValueError('Non-progressing mesh pagination')
        cursor = next_cursor
    else:
        raise ValueError('Mesh pull exceeded page limit')

    cursor = ''
    for _ in range(MAX_PAGES):
        page = store.notes_page(after=cursor)
        packet = signed(identity, 'mesh.notes', {
            'collective_id': store.collective_id(), **page,
        })
        response = post(remote_url, '/v1/mesh/push', packet)
        exported += response['imported']
        if not page['has_more']:
            break
        if page['next_after'] <= cursor:
            raise ValueError('Non-progressing local pagination')
        cursor = page['next_after']
    else:
        raise ValueError('Mesh push exceeded page limit')
    return {'imported_here': imported, 'imported_there': exported,
            'collective_id': store.collective_id()}
