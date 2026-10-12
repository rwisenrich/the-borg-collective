"""Minimal signed REST gateway, loopback-only by default; no arbitrary-code endpoint."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .store import Store
from .crypto import load_identity


def make_server(host, port, db_path, admission_token, trusted_token=None, identity_path=None):
    store = Store(db_path)
    node_identity = load_identity(identity_path) if identity_path else None

    class Handler(BaseHTTPRequestHandler):
        server_version = "BorgCollective/1.0"

        def _reply(self, code, data):
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(payload)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/health":
                self._reply(200,{"ok":True,"version":"1.0","history_valid":store.history()})
            elif self.path == "/.well-known/borg.json":
                self._reply(200,{"name":"The Borg Collective","version":"1.0",
                                 "collective_id":store.collective_id(),
                                 "peer_interface":"signed-json-v1",
                                 "a2a_compliant":False,"public_p2p_consensus":False})
            else:
                self._reply(404,{"error":"Not found"})

        def do_POST(self):
            routes={
                "/v1/peers/register":store.register_peer,
                "/v1/peers/ask":store.ask,
                "/v1/peers/status":store.status,
                "/v1/nodes/claim":store.claim,
                "/v1/nodes/complete":store.complete,
            }
            if self.path not in routes and self.path not in ("/v1/nodes/register","/v1/mesh/pull","/v1/mesh/push"):
                return self._reply(404,{"error":"Unknown endpoint"})
            try:
                size = int(self.headers.get("Content-Length","0"))
                if size < 1 or size > 65536:
                    return self._reply(413,{"error":"Request size exceeded"})
                envelope = json.loads(self.rfile.read(size))
                if not isinstance(envelope,dict):
                    raise ValueError("Expected a JSON object")
                if self.path == "/v1/nodes/register":
                    granted = bool(admission_token) and self.headers.get("X-Admission-Token") == admission_token
                    wants_trust = bool(envelope.get('body',{}).get('trusted',False))
                    if wants_trust and (not trusted_token or self.headers.get('X-Trusted-Token') != trusted_token):
                        raise PermissionError('Trusted worker needs separate trusted-worker admission')
                    out = store.register_node(envelope, admitted=granted)
                elif self.path == '/v1/mesh/pull':
                    if not node_identity:
                        raise PermissionError('Mesh disabled on this server')
                    out = store.mesh_export(envelope,node_identity)
                elif self.path == '/v1/mesh/push':
                    if not node_identity:
                        raise PermissionError('Mesh disabled on this server')
                    out = store.mesh_import(envelope)
                else:
                    out = routes[self.path](envelope)
                self._reply(200,out)
            except (ValueError,KeyError,TypeError,IndexError) as e:
                self._reply(400,{"error":str(e)[:180]})
            except PermissionError as e:
                self._reply(403,{"error":str(e)[:180]})
            except Exception as e:
                # Do not leak internal paths/keys into the public error message.
                self.log_error("Request error: %s",type(e).__name__)
                self._reply(500,{"error":"Internal server error"})

        def log_message(self,fmt,*args):
            # Avoid logging sensitive prompts or authentication headers.
            print("[borg] " + fmt%args)

    return ThreadingHTTPServer((host,port),Handler)
