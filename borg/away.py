"""Portable, independently signed offline crew journal (file-based transport).

An away crew can operate without the parent coordinator. Crew members exchange
files while offline and later merge only cryptographically verified additions.
This is not an autonomous internet P2P overlay or general software execution.
"""
import copy
import json
from pathlib import Path

from .crypto import load_identity, signed, verify, identity_id
from .quorum import fingerprint

ALLOWED_ROLES=('explore','challenge','verify','research','compute')
MAX_REPORTS=500
YEAR=365*24*3600


def _header(bundle):
    return {k:bundle[k] for k in ('collective_id','mission_id','base','brief','crew','version')}


def validate(bundle):
    if not isinstance(bundle,dict) or bundle.get('version')!=1:
        raise ValueError('Invalid detached mission format')
    for k in ('collective_id','mission_id','brief'):
        if not isinstance(bundle.get(k),str) or not 1<=len(bundle[k])<=3000:
            raise ValueError('Invalid away-mission metadata')
    if not isinstance(bundle.get('base'),int) or bundle['base']<0:
        raise ValueError('Invalid fork revision')
    if not isinstance(bundle.get('crew'),list) or not 1<=len(bundle['crew'])<=20:
        raise ValueError('Invalid crew')
    pubs={}
    for member in bundle['crew']:
        if not isinstance(member,dict) or any(not isinstance(member.get(k),str) for k in ('id','public','name')):
            raise ValueError('Malformed crew identity')
        if identity_id(member['public'])!=member['id'] or member['id'] in pubs:
            raise ValueError('Invalid or duplicate crew key')
        pubs[member['id']]=member['public']
    if not isinstance(bundle.get('entries'),list) or len(bundle['entries'])>MAX_REPORTS:
        raise ValueError('Invalid crew journal')
    seen=set()
    for envelope in bundle['entries']:
        if not isinstance(envelope,dict):raise ValueError('Malformed crew report')
        who=verify(envelope,'away.contribute',window=YEAR)
        if who not in pubs or envelope['public']!=pubs[who]:
            raise PermissionError('Non-crew contribution')
        body=envelope['body']
        if not isinstance(body,dict) or body.get('mission_id')!=bundle['mission_id'] or body.get('header_hash')!=fingerprint(_header(bundle)):
            raise ValueError('Detached crew message for a different mission')
        if body.get('role') not in ALLOWED_ROLES:
            raise ValueError('Invalid crew role')
        if not isinstance(body.get('content'),str) or not 1<=len(body['content'])<=8000:
            raise ValueError('Bad crew note')
        marker=(who,envelope['nonce'])
        if marker in seen:raise ValueError('Duplicate crew message')
        seen.add(marker)
    return {'valid':True,'entries':len(seen),'crew':len(pubs),'digest':fingerprint(bundle)}


def create(collective_id,mission_id,base,brief,crew):
    data={'version':1,'collective_id':collective_id,'mission_id':mission_id,
          'base':base,'brief':brief,'crew':crew,'entries':[]}
    validate(data)
    return data


def contribute(bundle,identity_path,role,content):
    validate(bundle)
    ident=load_identity(identity_path)
    if role not in ALLOWED_ROLES or ident['id'] not in {x['id'] for x in bundle['crew']}:
        raise PermissionError('Only authorized crew can contribute')
    if not isinstance(content,str) or not 1<=len(content)<=8000:
        raise ValueError('Invalid report content')
    outgoing=copy.deepcopy(bundle)
    outgoing['entries'].append(signed(ident,'away.contribute',{
        'mission_id':bundle['mission_id'],'header_hash':fingerprint(_header(bundle)),
        'role':role,'content':content}))
    validate(outgoing)
    return outgoing


def merge(a,b):
    validate(a);validate(b)
    if fingerprint(_header(a))!=fingerprint(_header(b)):
        raise ValueError('Cannot merge different missions/crew rosters')
    result=copy.deepcopy(a)
    by_key={(x['id'],x['nonce']):x for x in result['entries']}
    for item in b['entries']:
        key=(item['id'],item['nonce'])
        if key in by_key and by_key[key]!=item:
            raise ValueError('Conflicting copy of signed crew report')
        by_key[key]=item
    result['entries']=sorted(by_key.values(),key=lambda e:(e['ts'],e['id'],e['nonce']))
    validate(result)
    return result


def return_payload(bundle,report):
    audit=validate(bundle)
    if not isinstance(report,str) or not 1<=len(report)<=8000:
        raise ValueError('Invalid final mission report')
    return {'id':bundle['mission_id'],'base':bundle['base'],
            'content':report,'crew_bundle':bundle,'crew_digest':audit['digest']}


def save(path,bundle):
    validate(bundle)
    target=Path(path)
    if target.exists():raise FileExistsError('Away file already exists: '+str(path))
    target.write_text(json.dumps(bundle,indent=2,ensure_ascii=False),encoding='utf-8')
    return str(target)


def load(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    validate(data)
    return data
