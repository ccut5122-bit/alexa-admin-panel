import http.server, json, os, time, threading
from urllib.parse import urlparse, parse_qs

_DIR = os.path.dirname(os.path.abspath(__file__))
PASS_FILE = os.path.join(_DIR, 'passwords.json')
LOG_FILE = os.path.join(_DIR, 'logins.json')
lock = threading.Lock()

def rd_pass():
    if not os.path.exists(PASS_FILE): return {}
    with lock:
        with open(PASS_FILE) as f:
            try: return json.load(f)
            except: return {}

def wr_pass(d):
    with lock:
        with open(PASS_FILE, 'w') as f:
            json.dump(d, f)

def rd_logs():
    if not os.path.exists(LOG_FILE): return []
    with lock:
        with open(LOG_FILE) as f:
            try: return json.load(f)
            except: return []

def wr_log(e):
    logs = rd_logs()
    logs.append(e)
    logs = logs[-200:]
    with lock:
        with open(LOG_FILE, 'w') as f:
            json.dump(logs, f)

def json_resp(h, code, data):
    h.send_response(code)
    h.send_header('Content-Type', 'application/json')
    h.send_header('Access-Control-Allow-Origin', '*')
    h.end_headers()
    return json.dumps(data).encode()

def read_body(h):
    length = int(h.headers.get('Content-Length', 0))
    return h.rfile.read(length)

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == '/api/logins':
            self.wfile.write(json_resp(self, 200, rd_logs()))
            return
        if path == '/api/check':
            p = qs.get('pass', [None])[0]
            pwds = rd_pass()
            valid = (p or '') in pwds
            self.wfile.write(json_resp(self, 200, {'valid': valid}))
            return
        if path == '/api/passwords':
            pwds = rd_pass()
            self.wfile.write(json_resp(self, 200, pwds))
            return
        if path.startswith('/api/'):
            self.wfile.write(json_resp(self, 404, {'error':'not found'}))
            return
        super().do_GET()

    def do_POST(self):
        if self.path in ['/api/auth', '/api/login', '/api/setpass', '/api/delpass']:
            body = read_body(self)
            try: data = json.loads(body)
            except:
                self.wfile.write(json_resp(self, 400, {'error':'bad json'}))
                return
            pwds = rd_pass()

            if self.path == '/api/auth':
                p = data.get('pass', '')
                if p in pwds:
                    pwds[p]['last_login'] = int(time.time()*1000)
                    pwds[p]['device'] = data.get('ua', '')[:60]
                    wr_pass(pwds)
                    self.wfile.write(json_resp(self, 200, {'ok': True}))
                else:
                    self.wfile.write(json_resp(self, 200, {'ok': False}))
                return

            if self.path == '/api/login':
                p = data.get('pass', '')
                data['ts'] = int(time.time()*1000)
                wr_log(data)
                self.wfile.write(json_resp(self, 200, {'ok': True}))
                return

            if self.path == '/api/setpass':
                p = data.get('pass', '')
                if not p or len(p) < 3:
                    self.wfile.write(json_resp(self, 200, {'ok': False, 'error': 'min 3 chars'}))
                    return
                if p in pwds:
                    self.wfile.write(json_resp(self, 200, {'ok': False, 'error': 'already exists'}))
                    return
                pwds[p] = {'created': int(time.time()*1000), 'last_login': None, 'device': ''}
                wr_pass(pwds)
                self.wfile.write(json_resp(self, 200, {'ok': True}))
                return

            if self.path == '/api/delpass':
                p = data.get('pass', '')
                if p in pwds:
                    del pwds[p]
                    wr_pass(pwds)
                    self.wfile.write(json_resp(self, 200, {'ok': True}))
                else:
                    self.wfile.write(json_resp(self, 200, {'ok': False, 'error': 'not found'}))
                return

        self.wfile.write(json_resp(self, 404, {'error':'not found'}))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = http.server.HTTPServer(('', port), Handler)
    print(f'Server on :{port}')
    server.serve_forever()
