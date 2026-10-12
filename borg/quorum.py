"""Experimental majority-committed cognitive journal for a fixed, opted-in Borg cluster.

This is a bounded crash-fault research implementation inspired by Raft. It is NOT
Byzantine consensus, automatic membership, production Raft, or model parallelism.
Node membership is explicit; technical quorum votes are not community governance.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .client import post
from .crypto import canonical, identity_id, load_identity, signed, verify

KINDS = frozenset(('workspace.open', 'workspace.contribute', 'workspace.decide',
                   'mission.detach', 'mission.return', 'actor.grant', 'system.noop'))
MAX_ENTRIES = 4096
MAX_VALUE = 12000
BATCH = 24


def fingerprint(data):
    return hashlib.sha256(canonical(data)).hexdigest()


def config_load(path):
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or not isinstance(obj.get('collective_id'), str):
        raise ValueError('Missing collective identity')
    if not isinstance(obj.get('nodes'), list) or not 3 <= len(obj['nodes']) <= 9 or len(obj['nodes']) % 2 != 1:
        raise ValueError('Requires odd number of 3-9 pinned replica nodes')
    ids = set()
    for node in obj['nodes']:
        if not isinstance(node, dict) or any(not isinstance(node.get(k), str) for k in ('id', 'public', 'url')):
            raise ValueError('Invalid cluster node')
        if identity_id(node['public']) != node['id'] or node['id'] in ids:
            raise ValueError('Invalid or duplicate node key')
        ids.add(node['id'])
        # validate remote URL transport *before* opening any socket
        from urllib.parse import urlparse
        p = urlparse(node['url'])
        if not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
            raise ValueError('Invalid node endpoint URL')
        if p.scheme != 'https' and not (p.scheme == 'http' and p.hostname in ('localhost','127.0.0.1','::1')):
            raise ValueError('Remote node URLs require HTTPS')
    return obj


class QuorumError(RuntimeError):
    pass


class QuorumNode:
    """Replicated append-only workspace. Membership must be preconfigured."""

    def __init__(self, database, identity_path, config_path, timeout=1.4):
        self.database = str(database)
        self.identity = load_identity(identity_path)
        self.config = config_load(config_path)
        self.members = {m['id']: m for m in self.config['nodes']}
        self.node_id = self.identity['id']
        if self.node_id not in self.members or self.members[self.node_id]['public'] != self.identity['public']:
            raise ValueError('Local node not in pinned cluster')
        self.quorum = len(self.members) // 2 + 1
        self.timeout = timeout
        self.lock = threading.RLock()
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS log(
                idx INTEGER PRIMARY KEY, term INTEGER NOT NULL,
                op_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
                payload TEXT NOT NULL, digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS nonces(peer TEXT NOT NULL, nonce TEXT NOT NULL,
                created INTEGER NOT NULL,PRIMARY KEY(peer,nonce));
            CREATE TABLE IF NOT EXISTS actors(id TEXT PRIMARY KEY,public TEXT NOT NULL,name TEXT NOT NULL);
            ''')
            defaults = {'collective_id': self.config['collective_id'],
                        'config_digest': fingerprint(self.config),
                        'term': '0', 'vote': '', 'leader': '', 'commit': '0'}
            for k, v in defaults.items():
                db.execute('INSERT OR IGNORE INTO meta(k,v) VALUES(?,?)', (k,v))
            for k in ('collective_id','config_digest'):
                if self.get(db,k) != defaults[k]:
                    raise ValueError('Node database is associated with another collective/configuration')

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get(db, key):
        r = db.execute('SELECT v FROM meta WHERE k=?', (key,)).fetchone()
        return r['v'] if r else ''

    @staticmethod
    def put(db, key, value):
        db.execute('INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v', (key,str(value)))

    @staticmethod
    def tip(db):
        r = db.execute('SELECT idx,term FROM log ORDER BY idx DESC LIMIT 1').fetchone()
        return (r['idx'],r['term']) if r else (0,0)

    @staticmethod
    def entry(db, idx):
        r = db.execute('SELECT * FROM log WHERE idx=?',(idx,)).fetchone()
        return dict(r) if r else None

    def _member(self, db, envelope, action):
        ident = verify(envelope, action)
        if ident not in self.members or self.members[ident]['public'] != envelope['public']:
            raise PermissionError('Unknown node')
        self._nonce(db,envelope)
        return ident

    @staticmethod
    def _nonce(db,envelope):
        db.execute('DELETE FROM nonces WHERE created<?',(int(time.time())-600,))
        try:
            db.execute('INSERT INTO nonces(peer,nonce,created) VALUES(?,?,?)',
                       (envelope['id'],envelope['nonce'],envelope['ts']))
        except sqlite3.IntegrityError as exc:
            raise PermissionError('Duplicate signed message') from exc

    def _actor(self,db,envelope,action):
        ident=verify(envelope,action)
        member=self.members.get(ident)
        actor=self._view(db)['actors'].get(ident)
        known=(member and member['public']==envelope['public']) or (actor and actor['public']==envelope['public'])
        if not known:
            raise PermissionError('Actor has not been admitted')
        self._nonce(db,envelope)
        return ident

    def admit_actor(self, public_identity):
        ident=public_identity
        if not isinstance(ident,dict) or not all(isinstance(ident.get(k),str) for k in ('id','public','name')):
            raise ValueError('Invalid actor identity')
        if identity_id(ident['public']) != ident['id']:
            raise ValueError('Actor key mismatch')
        self.propose('actor.grant', {'id':ident['id'], 'public':ident['public'], 'name':ident['name'][:80]})
        return ident['id']

    def _term(self, db):
        return int(self.get(db,'term'))

    def _bump(self, db, term):
        if term > self._term(db):
            self.put(db,'term',term)
            self.put(db,'vote','')
            self.put(db,'leader','')

    def vote(self,envelope):
        with self.lock, self.tx() as db:
            who=self._member(db,envelope,'q.vote')
            body=envelope['body']
            term=body.get('term')
            if not isinstance(term,int) or term < 0:
                raise ValueError('Bad term')
            if term < self._term(db):
                return {'granted':False,'term':self._term(db)}
            self._bump(db,term)
            local_last=self.tip(db)
            their_last=(body.get('last_term'),body.get('last_index'))
            current_vote=self.get(db,'vote')
            allowed=(not current_vote or current_vote==who) and their_last >= (local_last[1],local_last[0])
            if allowed:
                self.put(db,'vote',who)
                self.put(db,'leader','')
            return {'granted':bool(allowed),'term':self._term(db)}

    def append(self,envelope):
        with self.lock, self.tx() as db:
            who=self._member(db,envelope,'q.append')
            b=envelope['body']
            term=b.get('term')
            if not isinstance(term,int) or term < 0:
                raise ValueError('Bad term')
            if term < self._term(db):
                return {'ok':False,'term':self._term(db),'last_index':self.tip(db)[0]}
            self._bump(db,term)
            vote=self.get(db,'vote')
            if vote and vote!=who:
                return {'ok':False,'term':self._term(db),'last_index':self.tip(db)[0]}
            self.put(db,'vote',who)
            self.put(db,'leader',who)
            prev=b.get('prev_index')
            prev_term=b.get('prev_term')
            if not isinstance(prev,int) or not isinstance(prev_term,int) or prev < 0:
                raise ValueError('Bad append prefix')
            prev_row=self.entry(db,prev) if prev else None
            if prev and (prev_row is None or prev_row['term']!=prev_term):
                return {'ok':False,'term':self._term(db),'last_index':self.tip(db)[0]}
            entries=b.get('entries')
            if not isinstance(entries,list) or len(entries)>BATCH:
                raise ValueError('Bad batch')
            committed=int(self.get(db,'commit'))
            expected=prev+1
            for entry in entries:
                if not isinstance(entry,dict) or entry.get('idx')!=expected:
                    raise ValueError('Noncontiguous entry')
                if entry.get('kind') not in KINDS or not isinstance(entry.get('payload'),str) or len(entry['payload'])>MAX_VALUE:
                    raise ValueError('Invalid journal entry')
                if not isinstance(entry.get('term'),int) or entry['term']>term or entry['term']<1:
                    raise ValueError('Invalid entry term')
                if entry.get('digest')!=fingerprint([entry['idx'],entry['term'],entry['op_id'],entry['kind'],entry['payload']]):
                    raise ValueError('Entry digest mismatch')
                existing=self.entry(db,expected)
                if existing and existing['digest']!=entry['digest']:
                    if expected <= committed:
                        raise QuorumError('Committed prefix conflict')
                    db.execute('DELETE FROM log WHERE idx>=?',(expected,))
                if not self.entry(db,expected):
                    db.execute('INSERT INTO log VALUES(?,?,?,?,?,?)',
                               (entry['idx'],entry['term'],entry['op_id'],entry['kind'],entry['payload'],entry['digest']))
                expected+=1
            new_commit=b.get('leader_commit')
            if not isinstance(new_commit,int) or new_commit<0:
                raise ValueError('Invalid commit index')
            self.put(db,'commit', min(max(committed,new_commit),self.tip(db)[0]))
            return {'ok':True,'term':self._term(db),'last_index':self.tip(db)[0],
                    'commit':int(self.get(db,'commit'))}

    def _rpc(self, peer_id, action, data):
        peer=self.members[peer_id]
        return post(peer['url'],'/v2/quorum/'+action,
                    signed(self.identity,'q.'+action,data),timeout=self.timeout)

    def status(self):
        with self.lock,self.tx() as db:
            last,last_term=self.tip(db)
            return {'node_id':self.node_id,'collective_id':self.get(db,'collective_id'),
                    'term':self._term(db),'leader':self.get(db,'leader'),
                    'commit':int(self.get(db,'commit')),
                    'last_index':last,'last_term':last_term,'quorum':self.quorum}

    def campaign(self):
        with self.lock,self.tx() as db:
            term=self._term(db)+1
            self._bump(db,term)
            self.put(db,'vote',self.node_id)
            self.put(db,'leader','')
            last,lt=self.tip(db)
        granted=1
        for peer in self.members:
            if peer==self.node_id:continue
            try:
                r=self._rpc(peer,'vote',{'term':term,'last_index':last,'last_term':lt})
                if r['term']>term:
                    with self.lock,self.tx() as db:self._bump(db,r['term'])
                    break
                if r.get('granted'):granted+=1
            except (OSError,RuntimeError,ValueError):
                continue
        if granted < self.quorum:
            raise QuorumError(f'No majority for election ({granted}/{len(self.members)})')
        with self.lock,self.tx() as db:
            if self._term(db)!=term:
                raise QuorumError('Election superseded by higher term')
            self.put(db,'leader',self.node_id)
        # Notify followers; durable votes already establish a technical majority.
        self.heartbeat()
        if self.status()['last_index'] > self.status()['commit']:
            self.recover()
        return self.status()

    def _sync_peer(self,peer):
        # Bounded, prefix-checked catch-up. This baseline resends history in batches.
        with self.tx() as db:
            term=self._term(db)
            commit=int(self.get(db,'commit'))
            rows=[dict(x) for x in db.execute('SELECT * FROM log ORDER BY idx')]
        last=len(rows)
        if last>MAX_ENTRIES:raise QuorumError('Journal capacity reached; snapshotting required')
        for start in range(0,max(1,last),BATCH):
            batch=rows[start:start+BATCH]
            prev=rows[start-1] if start else None
            data={'term':term,'prev_index':prev['idx'] if prev else 0,
                  'prev_term':prev['term'] if prev else 0,
                  'entries':batch,'leader_commit':commit}
            reply=self._rpc(peer,'append',data)
            if reply['term']>term:
                with self.tx() as db:self._bump(db,reply['term'])
                raise QuorumError('Superseded leader term')
            if not reply.get('ok'):
                raise QuorumError('Follower rejected append (log conflict or different leader)')
        return last

    def heartbeat(self):
        with self.lock:
            s=self.status()
            if s['leader']!=self.node_id:
                raise QuorumError('This node is not leader')
            count=1
            for peer in self.members:
                if peer==self.node_id:continue
                try:
                    self._sync_peer(peer)
                    count+=1
                except (OSError,RuntimeError,ValueError):pass
            return {'reachable':count,'quorum':self.quorum}

    def audit(self):
        """Audit local journal continuity, entry digests and committed prefix.

        Detects accidental corruption; it is not a cryptographic proof against
        malicious host administrators rewriting their entire local database.
        """
        with self.lock,self.tx() as db:
            previous=0
            rows=db.execute('SELECT * FROM log ORDER BY idx').fetchall()
            for row in rows:
                if row['idx'] != previous+1:
                    return {'valid':False,'reason':'Non-contiguous log'}
                if row['digest'] != fingerprint([row['idx'],row['term'],row['op_id'],
                                                  row['kind'],row['payload']]):
                    return {'valid':False,'reason':'Tampered entry at '+str(row['idx'])}
                previous=row['idx']
            committed=int(self.get(db,'commit'))
            if not 0<=committed<=previous:
                return {'valid':False,'reason':'Impossible commit index'}
            return {'valid':True,'last_index':previous,'commit':committed,
                    'collective_id':self.get(db,'collective_id')}

    def _view(self,db):
        idx=int(self.get(db,'commit'))
        state={'collective_id':self.get(db,'collective_id'),
               'commit':idx,'workspaces':{},'missions':{},'actors':{}}
        for row in db.execute('SELECT * FROM log WHERE idx<=? ORDER BY idx',(idx,)):
            p=json.loads(row['payload'])
            kind=row['kind']
            if kind=='actor.grant':
                state['actors'][p['id']] = p
            elif kind=='workspace.open':
                state['workspaces'][p['id']]={'question':p['question'],'goal':p['goal'],'owner':p.get('actor',''),
                    'contributions':[],'decision':None,'revision':1}
            elif kind=='workspace.contribute':
                w=state['workspaces'][p['id']]
                w['contributions'].append({'role':p['role'],'actor':p['actor'],
                                            'content':p['content'],'op_id':row['op_id']})
                w['revision']+=1
            elif kind=='workspace.decide':
                w=state['workspaces'][p['id']]
                w['decision']={'content':p['content'],'actor':p['actor']}
                w['revision']+=1
            elif kind=='mission.detach':
                state['missions'][p['id']]={'brief':p['brief'],'base':p['base'],
                    'members':p['members'],'status':'away','reports':[]}
            elif kind=='mission.return':
                m=state['missions'][p['id']]
                m['reports'].append({'actor':p['actor'],'content':p['content'],
                                    'crew_digest':p.get('crew_digest')})
                m['status']='returned-unreviewed'
        return state

    def view(self):
        with self.lock,self.tx() as db:return self._view(db)

    def _validate(self,db,kind,p):
        if kind not in KINDS or not isinstance(p,dict):
            raise ValueError('Unknown cognitive event')
        state=self._view(db)
        if kind=='actor.grant':
            if not all(isinstance(p.get(k),str) for k in ('id','public','name')) or identity_id(p['public'])!=p['id']:
                raise ValueError('Invalid actor grant')
            if p['id'] in state['actors']:
                raise ValueError('Actor already granted')
        elif kind=='system.noop':
            if p != {}: raise ValueError('No-op must have empty body')
        elif kind=='workspace.open':
            if not isinstance(p.get('id'),str) or p['id'] in state['workspaces']:
                raise ValueError('Duplicate/invalid workspace')
            if not isinstance(p.get('question'),str) or not 1<=len(p['question'])<=4000:
                raise ValueError('Invalid question')
            if not isinstance(p.get('goal'),str) or not 1<=len(p['goal'])<=1000:
                raise ValueError('Invalid goal')
            if not isinstance(p.get('actor'),str):raise ValueError('Opening actor required')
            active=sum(1 for w in state['workspaces'].values()
                       if w['owner']==p['actor'] and w['decision'] is None)
            if active>=2:raise ValueError('Per-AI active-workspace limit reached')
            if len(state['workspaces'])>=256:raise ValueError('Shared workspace capacity reached')
            if p.get('share') is not True:
                raise PermissionError('Replicated workspace requires explicit opt-in')
        elif kind in ('workspace.contribute','workspace.decide'):
            w=state['workspaces'].get(p.get('id'))
            if not w:raise ValueError('Unknown workspace')
            if not isinstance(p.get('expected_revision'),int) or w['revision'] != p['expected_revision']:
                raise QuorumError('Workspace revision conflict: refresh and retry')
            if w['decision'] is not None:raise ValueError('Workspace already decided')
            if kind=='workspace.decide' and p.get('actor') != w['owner'] and p.get('actor') not in self.members:
                raise PermissionError('Only opening actor or a replica can finalize')
            if not isinstance(p.get('content'),str) or not 1<=len(p['content'])<=8000:
                raise ValueError('Invalid contribution')
            if kind=='workspace.contribute':
                if p.get('role') not in ('explore','challenge','verify','research','compute'):
                    raise ValueError('Invalid cognitive role')
            elif not w['contributions']:
                raise ValueError('Decision requires at least one contribution')
        elif kind=='mission.detach':
            if not isinstance(p.get('id'),str) or p['id'] in state['missions']:
                raise ValueError('Invalid mission ID')
            if not isinstance(p.get('brief'),str) or not 1<=len(p['brief'])<=3000:
                raise ValueError('Invalid mission objective')
            if p.get('base') != int(self.get(db,'commit')):
                raise QuorumError('Mission must fork from latest committed state')
            if not isinstance(p.get('members'),list) or not 1<=len(p['members'])<=20 or not all(isinstance(x,str) for x in p['members']):
                raise ValueError('Invalid mission crew')
        elif kind=='mission.return':
            if p.get('id') not in state['missions']:
                raise ValueError('Unknown mission')
            if not isinstance(p.get('content'),str) or not 1<=len(p['content'])<=8000:
                raise ValueError('Invalid mission return')
            mission=state['missions'][p['id']]
            if p.get('actor') not in mission['members']:
                raise PermissionError('Returning actor not assigned to crew')
            if p.get('base')!=mission['base']:
                raise ValueError('Wrong mission origin revision')
            bundle=p.get('crew_bundle')
            from .away import validate
            if bundle is None:
                raise ValueError('Cryptographically signed away crew journal required')
            audit=validate(bundle)
            if audit['digest']!=p.get('crew_digest') or bundle['mission_id']!=p['id']:
                raise ValueError('Mismatched away crew journal digest')
            if bundle['collective_id']!=self.get(db,'collective_id') or bundle['base']!=mission['base']:
                raise ValueError('Away crew returned to wrong collective')
            if {x['id'] for x in bundle['crew']} != set(mission['members']):
                raise ValueError('Away mission roster changed')
            if p['crew_digest'] in {r.get('crew_digest') for r in mission['reports']}:
                raise ValueError('Away crew report already imported')
        if len(canonical(p))>MAX_VALUE:
            raise ValueError('Oversized cognitive event')
        return state

    def propose(self,kind,payload,op_id=None):
        with self.lock:
            with self.tx() as db:
                if self.get(db,'leader')!=self.node_id:
                    raise QuorumError('Not leader')
                if self.tip(db)[0]!=int(self.get(db,'commit')):
                    # No new entries until an earlier proposal has been resolved.
                    raise QuorumError('Unresolved uncommitted entry; elect/recover before new proposal')
                self._validate(db,kind,payload)
                idx=self.tip(db)[0]+1
                term=self._term(db)
                op_id=op_id or uuid.uuid4().hex
                p=json.dumps(payload,sort_keys=True,separators=(',',':'))
                d=fingerprint([idx,term,op_id,kind,p])
                db.execute('INSERT INTO log VALUES(?,?,?,?,?,?)',(idx,term,op_id,kind,p,d))
            count=1
            for peer in self.members:
                if peer==self.node_id:continue
                try:
                    if self._sync_peer(peer)>=idx:count+=1
                except (OSError,RuntimeError,ValueError):pass
            if count<self.quorum:
                raise QuorumError(f'Proposal uncommitted: only {count}/{len(self.members)} durable replicas')
            with self.tx() as db:
                if self.get(db,'leader')!=self.node_id or self._term(db)!=term:
                    raise QuorumError('Term superseded; cannot commit')
                self.put(db,'commit',idx)
            # Commit notification, best effort; safe minority must not commit itself.
            for peer in self.members:
                if peer!=self.node_id:
                    try:self._sync_peer(peer)
                    except (OSError,RuntimeError,ValueError):pass
            return {'index':idx,'term':term,'committed':True,'op_id':op_id}

    def recover(self):
        """Commit an elected leader's outstanding tail using a current-term no-op.

        The election log freshness restriction prevents candidates missing a
        committed prefix from winning a majority. An uncommitted tail can be
        discarded only when overwritten by a newly elected, fresher leader.
        """
        with self.lock:
            with self.tx() as db:
                if self.get(db,'leader')!=self.node_id:
                    raise QuorumError('Only the leader can recover')
                last,_=self.tip(db)
                old_commit=int(self.get(db,'commit'))
                if last==old_commit:
                    return {'recovered':False,'commit':old_commit}
                idx=last+1
                term=self._term(db)
                op_id=uuid.uuid4().hex
                kind='system.noop'
                payload='{}'
                d=fingerprint([idx,term,op_id,kind,payload])
                db.execute('INSERT INTO log VALUES(?,?,?,?,?,?)',(idx,term,op_id,kind,payload,d))
            acks=1
            for peer in self.members:
                if peer==self.node_id:continue
                try:
                    if self._sync_peer(peer)>=idx:acks+=1
                except (OSError,RuntimeError,ValueError):pass
            if acks<self.quorum:
                raise QuorumError('Recovery no-op has not reached a quorum')
            with self.tx() as db:
                if self.get(db,'leader')!=self.node_id or self._term(db)!=term:
                    raise QuorumError('Recovery term superseded')
                self.put(db,'commit',idx)
            self.heartbeat()
            return {'recovered':True,'commit':idx}

    def accept_actor(self,envelope,kind):
        with self.lock,self.tx() as db:
            who=self._actor(db,envelope,'brain.propose')
            payload=envelope.get('body',{})
            if not isinstance(payload,dict) or payload.get('kind')!=kind:
                raise ValueError('Invalid brain request')
            p=payload.get('payload')
            if not isinstance(p,dict):raise ValueError('Invalid event payload')
            if kind in ('workspace.open','workspace.contribute','workspace.decide','mission.return'):
                if p.get('actor')!=who:raise PermissionError('Wrong actor identity')
        return self.propose(kind,p)
