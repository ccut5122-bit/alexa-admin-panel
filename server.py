import http.server, json, os, time, threading
from urllib.parse import urlparse, parse_qs

_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_DIR, 'bot_db.json')
lock = threading.Lock()

def rd_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE) as f: return json.load(f)
        except: pass
    return {"passwords": {}, "logins": []}

def wr_db(d):
    with open(DB_FILE, 'w') as f: json.dump(d, f, indent=2)

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
            with lock:
                db = rd_db()
            self.wfile.write(json_resp(self, 200, db.get('logins', [])))
            return
        if path == '/api/check':
            p = qs.get('pass', [None])[0]
            with lock:
                pwds = rd_db().get('passwords', {})
            self.wfile.write(json_resp(self, 200, {'valid': (p or '') in pwds}))
            return
        if path == '/api/passwords':
            with lock:
                pwds = rd_db().get('passwords', {})
            self.wfile.write(json_resp(self, 200, pwds))
            return
        if path.startswith('/api/'):
            self.wfile.write(json_resp(self, 404, {'error':'not found'}))
            return
        if path == '/':
            self.path = '/admin.html'
        super().do_GET()

    def do_POST(self):
        if self.path in ['/api/auth', '/api/login', '/api/setpass', '/api/delpass']:
            body = read_body(self)
            try: data = json.loads(body)
            except:
                self.wfile.write(json_resp(self, 400, {'error':'bad json'}))
                return

            with lock:
                db = rd_db()

                if self.path == '/api/auth':
                    p = data.get('pass', '')
                    pwds = db.get('passwords', {})
                    if p in pwds:
                        pwds[p]['last_login'] = int(time.time()*1000)
                        pwds[p]['device'] = data.get('ua', '')[:60]
                        wr_db(db)
                        self.wfile.write(json_resp(self, 200, {'ok': True}))
                    else:
                        self.wfile.write(json_resp(self, 200, {'ok': False}))
                    return

                if self.path == '/api/login':
                    logs = db.get('logins', [])
                    data['ts'] = int(time.time()*1000)
                    logs.append(data)
                    logs = logs[-200:]
                    db['logins'] = logs
                    wr_db(db)
                    self.wfile.write(json_resp(self, 200, {'ok': True}))
                    return

                if self.path == '/api/setpass':
                    p = data.get('pass', '')
                    pwds = db.get('passwords', {})
                    if not p or len(p) < 3:
                        self.wfile.write(json_resp(self, 200, {'ok': False, 'error': 'min 3 chars'}))
                        return
                    if p in pwds:
                        self.wfile.write(json_resp(self, 200, {'ok': False, 'error': 'already exists'}))
                        return
                    pwds[p] = {'created': int(time.time()*1000), 'last_login': None, 'device': ''}
                    db['passwords'] = pwds
                    wr_db(db)
                    self.wfile.write(json_resp(self, 200, {'ok': True}))
                    return

                if self.path == '/api/delpass':
                    p = data.get('pass', '')
                    pwds = db.get('passwords', {})
                    if p in pwds:
                        del pwds[p]
                        db['passwords'] = pwds
                        wr_db(db)
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
    os.chdir(_DIR)
    try:
        import threading, importlib.util, sys
        spec = importlib.util.spec_from_file_location('bot_module', os.path.join(_DIR, 'bot.py'))
        mod = importlib.util.module_from_spec(spec)
        def run_bot():
            os.environ.setdefault('PANEL_URL', f'http://localhost:{port}')
            sys.modules['bot_module'] = mod
            spec.loader.exec_module(mod)
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
    except Exception as e:
        print(f'Bot thread failed: {e}')
    server = http.server.HTTPServer(('', port), Handler)
    print(f'Server on :{port}')
    server.serve_forever()
