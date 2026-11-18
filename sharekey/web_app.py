"""시연용 웹 화면 (권기백). 차량 앱 느낌의 화면, 서비스 이름 SHAREKEY 는 가상 이름. app.py 를 그대로 불러 쓰는 화면만 씌운 것.
메시지 형식·판단·HMAC 은 app.py / common.py 그대로이며 이 파일은 아무것도 바꾸지 않는다.
파이썬 기본 기능만 사용 (설치할 것 없음). sharekey 폴더 안에서 실행.

  python3 web_app.py                                   노트북 브라우저에서 http://127.0.0.1:8080
  python3 web_app.py --vehicle 172.20.10.11:9100       Pi 경유 (app.py 의 --vehicle 과 같음)
  python3 web_app.py --lan --vehicle ...               같은 Wi-Fi 휴대폰에서도 접속 (주의: 같은 망 누구나 명령 가능)
"""
import argparse, contextlib, io, json, os, re, socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)                      # app.py 가 keys/ 를 현재 폴더 기준으로 씀
sys.path.insert(0, HERE)
import app                          # noqa: E402  (판단·메시지 코드는 app.py / common.py 그대로)
from common import REASON, RESULT   # noqa: E402
import common                       # noqa: E402

# ---- 화면용 통신 기록: 앱이 실제로 주고받은 줄을 옆에서 적기만 한다 (내용은 바꾸지 않음) ----
CAP = None                          # 기록 중이면 list
NONCE_USED = {}                     # 정상 응답에 쓴 nonce -> 시각 (재전송 표시용)
REGISTERED = set()                  # 이번 서버 기록 동안 차에 등록 성공한 키 (8자리)
SYNC_MAX, BOARD_MAX = 16, 8         # 실물 보드 sharekey.h: SK_MAX_SYNC_ENTRIES, SK_MAX_KEYS


def key_state():
    """서버가 남긴 server_state.json 을 읽어 키 현황을 돌려준다 (읽기만 함)."""
    try:
        st = json.load(open(os.path.join(HERE, "server_state.json"), encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    keys = st.get("keys", {}) or {}
    if not keys:
        REGISTERED.clear()                      # 서버 기록이 지워졌으면 새로 시작한 것
    items = [{"kid": k.lstrip("0") or "0", "revoked": v.get("state") == 1, "reg": k in REGISTERED}
             for k, v in sorted(keys.items())]
    return {"ok": True, "keys": items, "issued": len(keys), "registered": len(REGISTERED),
            "sync_max": SYNC_MAX, "board_max": BOARD_MAX}
_orig_send, _orig_recv = common.Conn.send, common.Conn.recv


def _peer(conn):
    try:
        port = conn.sock.getpeername()[1]
    except OSError:
        return "?"
    if str(port) == OPT.vehicle.rsplit(":", 1)[-1]:
        return "차"
    if str(port) == OPT.server.rsplit(":", 1)[-1]:
        return "서버"
    return "?"


def _send(self, rid, *fields):
    if CAP is not None:
        CAP.append({"from": "앱", "to": _peer(self), "f": [str(x) for x in fields]})
    return _orig_send(self, rid, *fields)


def _recv(self):
    r, p = _orig_recv(self)
    if CAP is not None:
        CAP.append({"from": _peer(self), "to": "앱", "f": list(p)})
    return r, p


common.Conn.send, common.Conn.recv = _send, _recv


def annotate(cmd, wire):
    """RESP 줄에 '정상 서명이면 무엇이었나', '이 nonce를 언제 썼나'를 붙인다 (화면 설명용)."""
    now = time.strftime("%H:%M:%S")
    for e in wire:
        f = e["f"]
        if e["from"] != "앱" or not f or f[0] != "RESP" or len(f) != 5:
            continue
        try:
            kid, c, nonce, tag = int(f[1], 16), int(f[2], 16), bytes.fromhex(f[3]), f[4]
            ki = bytes.fromhex(json.load(open(app.kpath(kid)))["ki"])
            good = common.hx(common.auth_tag(ki, kid, c, nonce))
        except (ValueError, OSError, KeyError):
            continue
        e["good_tag"] = good
        e["diff"] = [i for i, (a, b) in enumerate(zip(good, tag)) if a != b]
        if cmd == "replay":
            e["reused_at"] = NONCE_USED.get(f[3])
        elif cmd in ("open", "start", "return", "reauth", "stop"):
            NONCE_USED[f[3]] = now

LOCK = threading.Lock()
CMDS = {"issue", "register", "open", "start", "return", "reauth", "stop", "tamper", "replay", "revoke", "net"}
OPT = argparse.Namespace()
AUTO_LOCK = threading.Lock()
AUTO_STOP = None


def stop_auto_reauth():
    global AUTO_STOP
    with AUTO_LOCK:
        if AUTO_STOP is not None:
            AUTO_STOP.set()
        AUTO_STOP = None


def start_auto_reauth(kid):
    global AUTO_STOP
    stop_auto_reauth()
    event = threading.Event()
    with AUTO_LOCK:
        AUTO_STOP = event
    def renew():
        while not event.wait(getattr(OPT, "reauth_period", 60)):
            result = run("reauth", kid, 4, None)
            if not result.get("res") or result["res"]["code"] != "A":
                return
    threading.Thread(target=renew, daemon=True).start()


def run(cmd, kid, limit, net):
    """app.main() 을 그대로 호출하고 출력과 결과를 돌려준다."""
    if cmd == "state":
        return key_state()
    if cmd == "driving-status":
        try:
            with LOCK:
                return app.driving_status(OPT)
        except (OSError, ValueError, ConnectionError):
            return {"ok": False}
    if cmd == "nextkid":                        # 화면용: 이 폴더에서 아직 발급 안 한 다음 번호
        start = int(kid, 16) + 1 if re.fullmatch(r"[0-9A-Fa-f]{1,8}", kid or "") else 1
        used = set()
        if os.path.isdir(app.KEYDIR):
            used = {f[:-5].upper() for f in os.listdir(app.KEYDIR) if f.endswith(".json")}
        n = max(start, 1)
        while f"{n:08X}" in used and n < 0xFFFFFFFF:
            n += 1
        return {"ok": True, "kid": format(n, "X")}
    if cmd == "door":                           # 1106 시연 화면용: Pi 중계가 STM32 '#' 로그에서 읽은 문 상태 (읽기만)
        host, port = OPT.vehicle.rsplit(":", 1)
        dhost, dport = (OPT.door.rsplit(":", 1) if OPT.door else (host, str(int(port) + 1)))
        try:
            with socket.create_connection((dhost, int(dport)), timeout=0.4) as s:
                f = s.makefile("r", encoding="ascii").readline().strip().split("|")
            if len(f) == 4 and f[0] == "DOOR":
                return {"ok": True, "door": f[1], "seq": int(f[2]), "lock": f[3]}
        except (OSError, ValueError):
            pass
        return {"ok": False}
    if cmd not in CMDS:
        return {"ok": False, "error": "알 수 없는 명령"}
    argv = [cmd]
    if cmd == "net":
        if net not in ("on", "off"):
            return {"ok": False, "error": "net 은 on/off"}
        argv.append(net)
    else:
        if not re.fullmatch(r"[0-9A-Fa-f]{1,8}", kid or ""):
            return {"ok": False, "error": "KID 는 16진수 1~8자리"}
        argv.append(kid)
        if cmd == "issue":
            if not (isinstance(limit, int) and 1 <= limit <= 254):
                return {"ok": False, "error": "한도는 1~254"}
            argv += ["--limit", str(limit)]
    argv += ["--server", OPT.server, "--vehicle", OPT.vehicle]
    global CAP
    out = io.StringIO()
    with LOCK:
        CAP = []
        try:
            with contextlib.redirect_stdout(out):
                r = app.main(argv)
            wire = CAP
            annotate(cmd, wire)
        except SystemExit:
            return {"ok": False, "error": "명령 형식 오류", "output": out.getvalue(), "wire": CAP}
        except FileNotFoundError:
            return {"ok": False, "error": f"{kid}번 키가 아직 없음 — 먼저 '공유 키 만들기'", "output": out.getvalue(), "wire": CAP}
        except (ConnectionError, socket.timeout, OSError) as e:
            where = "서버" if cmd in ("issue", "revoke", "net") else "차량(Pi 중계)"
            return {"ok": False, "error": f"{where} 연결 실패: {e}", "output": out.getvalue(), "wire": CAP}
        except Exception as e:                      # 화면이 멈추지 않도록 그대로 보여 줌
            return {"ok": False, "error": f"{type(e).__name__}: {e}", "output": out.getvalue(), "wire": CAP}
        finally:
            CAP = None
    text = out.getvalue().strip()
    res = None
    if isinstance(r, tuple) and len(r) == 3:
        code, why, rem = r
        res = {"code": code, "result": RESULT.get(code, code), "why": why,
               "reason": REASON.get(why, why), "left": None if rem == "FF" else int(rem, 16)}
    ok = "실패" not in text and "없음" not in text
    if cmd == "register" and "성공" in text:
        REGISTERED.add(f"{int(kid, 16):08X}")
    if res and res["code"] == "A":
        if cmd == "start":
            start_auto_reauth(kid)
        elif cmd == "stop":
            stop_auto_reauth()
    return {"ok": ok, "output": text, "res": res, "wire": wire}


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        if getattr(self, "_quiet", False):        # 문 상태 조회(0.4초마다)는 터미널에 찍지 않음
            return
        sys.stderr.write("[웹] " + (fmt % a) + "\n")

    def _send(self, code, body, ctype):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            page = PAGE.replace("__VEHICLE__", OPT.vehicle).replace("__SERVER__", OPT.server)
            self._send(200, page, "text/html; charset=utf-8")
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/api" or "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._send(400, json.dumps({"ok": False, "error": "bad request"}), "application/json")
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 1024:
            return self._send(400, json.dumps({"ok": False, "error": "bad length"}), "application/json")
        try:
            q = json.loads(self.rfile.read(n))
            self._quiet = q.get("cmd") in ("door", "driving-status")
            r = run(str(q.get("cmd")), str(q.get("kid", "")), q.get("limit"), q.get("net"))
        except (ValueError, AttributeError):
            r = {"ok": False, "error": "bad json"}
        self._send(200, json.dumps(r, ensure_ascii=False), "application/json; charset=utf-8")


PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SHAREKEY · 내 차</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{--ink:#0a0e15;--ink2:#111826;--ink3:#1b2433;--sil:#d9dee6;--bg:#f3f4f6;--card:#fff;--line:#e3e6eb;--tx:#11161f;--mu:#6b7280;--navy:#0b2545;--sky:#2fb4e0;--ok:#11875d;--okbg:#e3f5ec;--okhi:#3ddc97;--no:#c8372d;--nobg:#fdeceb;--nohi:#ff8a7e;--wa:#a86400;--wabg:#fff3dc;--acc:#1d6fe0;--accbg:#e9f1ff}
*{box-sizing:border-box}html{-webkit-font-smoothing:antialiased}
body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.55 Pretendard,-apple-system,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif;letter-spacing:-.01em}
.wrap{max-width:1200px;margin:0 auto;padding:0 24px}
.top{background:var(--ink);color:#fff;border-bottom:1px solid rgba(255,255,255,.06)}
.top .wrap{display:flex;align-items:center;gap:36px;height:64px}
.logo{font-weight:300;letter-spacing:.42em;font-size:17px;white-space:nowrap}.logo b{font-weight:700}
.nav{display:flex;gap:26px;font-size:14px;color:rgba(255,255,255,.62)}.nav a{color:inherit;text-decoration:none}.nav a:hover,.nav a.on{color:#fff}
.nav a.on{box-shadow:inset 0 -2px 0 var(--sky);padding-bottom:20px;margin-bottom:-20px}
.team{margin-left:auto;font-size:12px;color:rgba(255,255,255,.5);text-align:right;line-height:1.35}
.hero{background:var(--ink);color:#fff;padding:26px 0 40px}
.hgrid{display:grid;grid-template-columns:1.25fr .9fr;gap:32px;align-items:stretch}
.eyebrow{font-size:12px;letter-spacing:.24em;color:var(--sky);font-weight:600}
h1.vn{font-size:32px;font-weight:700;margin:6px 0 2px;letter-spacing:-.02em}.vsub{font-size:14px;color:rgba(255,255,255,.55)}
.plate{display:inline-block;margin-top:10px;font-size:13px;padding:3px 10px;border:1px solid rgba(255,255,255,.25);border-radius:6px;color:rgba(255,255,255,.8);letter-spacing:.06em}
.car{position:relative;margin:14px 0 6px;max-width:640px}.car svg{width:100%;display:block}
.dhole{position:absolute;left:31.07%;top:49.5%;width:25.7%;height:20%;background:#0b0f16;border-radius:2px 2px 2px 14%;display:none;box-shadow:inset 0 0 18px #000}
.d3{position:absolute;left:31.07%;top:49.5%;width:25.7%;height:20%;display:none;transform-origin:100% 50%;transition:transform .7s cubic-bezier(.3,.7,.2,1);transform:perspective(700px) rotateY(0deg);
 background:linear-gradient(180deg,#d6dbe3,#c3c9d3);border:1.5px solid #8f99a8;border-radius:2px 2px 2px 14%;box-shadow:0 0 0 rgba(0,0,0,0)}
.d3::after{content:"";position:absolute;right:9%;top:18%;width:17%;height:12%;border-radius:3px;background:#7e8898}
.car.live .dhole,.car.live .d3{display:block}.car.live #cardoor{opacity:0}
.car.dopen .d3{transform:perspective(700px) rotateY(68deg);box-shadow:-14px 6px 18px rgba(0,0,0,.45)}
.car.unl .d3{border-color:var(--okhi);border-width:2.5px}.car.den .d3{border-color:var(--nohi);border-width:2.5px}
@media (prefers-reduced-motion:reduce){.d3{transition:none}}
#cardoor{transition:stroke .3s,stroke-width .3s}.car.unl #cardoor{stroke:var(--okhi);stroke-width:3}.car.den #cardoor{stroke:var(--nohi);stroke-width:3}
.lockpin{transition:fill .3s}
#glowF,#glowR{opacity:0}#beam{opacity:0;transition:opacity .4s}
.car.hz #glowF,.car.hz #glowR{animation:hz .45s ease-in-out 2}
@keyframes hz{0%,100%{opacity:0}50%{opacity:.85}}
.car.on #beam{opacity:.6}.car.on #headL{fill:#fffbe8}
.car.dn #tailL{animation:dn .3s ease-in-out 2}@keyframes dn{50%{fill:#ff2d1f}}
@media (prefers-reduced-motion:reduce){.car.hz #glowF,.car.hz #glowR,.car.dn #tailL{animation:none}}
.snd{margin-left:16px;font:inherit;font-size:12px;padding:5px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.25);background:transparent;color:rgba(255,255,255,.75);cursor:pointer}.car.unl .lockpin{fill:var(--okhi)}.car.den .lockpin{fill:var(--nohi)}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:6px}
.tile{background:var(--ink2);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:12px 14px;min-height:78px}
.tile .tl{font-size:12px;color:rgba(255,255,255,.5)}.tile .ts{font-size:12px;font-weight:400;color:rgba(255,255,255,.55);margin-top:2px}.tile .tv{font-size:15px;font-weight:600;margin-top:4px;line-height:1.35}
.chip{display:inline-block;font-weight:600}.chip.on{color:var(--okhi)}.chip.off{color:var(--nohi)}.chip.mode{color:#fff}
.chip .ts{font-weight:400}.chip.on::before,.chip.off::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:1px;background:currentColor}
.panel{background:var(--ink2);border:1px solid rgba(255,255,255,.08);border-radius:22px;padding:22px;display:flex;flex-direction:column}
.ph{display:flex;justify-content:space-between;align-items:baseline}.ph b{font-size:17px}.ph span{font-size:12px;color:rgba(255,255,255,.5)}
.resbox{margin:16px 0 18px;padding:16px 18px;border-radius:16px;background:var(--ink3);min-height:116px}
.resbox .lbl{font-size:12px;color:rgba(255,255,255,.5)}.resbox .big{font-size:34px;font-weight:800;line-height:1.2;margin-top:4px;letter-spacing:-.02em}
.resbox.A{background:rgba(61,220,151,.1);box-shadow:inset 0 0 0 1px rgba(61,220,151,.35)}.resbox.A .big{color:var(--okhi)}
.resbox.D,.resbox.H{background:rgba(255,138,126,.09);box-shadow:inset 0 0 0 1px rgba(255,138,126,.35)}.resbox.D .big,.resbox.H .big{color:var(--nohi)}
.resbox .why{font-size:15px;color:rgba(255,255,255,.8);margin-top:2px}
.open{display:flex;align-items:center;justify-content:center;gap:12px;width:100%;height:72px;border:0;border-radius:18px;background:#fff;color:var(--ink);font:inherit;font-size:20px;font-weight:700;cursor:pointer;transition:transform .1s}
.open:hover{background:#eef6fb}.open:active{transform:scale(.98)}.open:disabled{opacity:.55;cursor:wait}.open svg{width:26px;height:26px}
.dots{display:flex;gap:6px;margin-top:16px;align-items:center;flex-wrap:wrap}.dot{width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,.15)}.dot.f{background:var(--okhi)}
.dots .t{font-size:13px;color:rgba(255,255,255,.6);margin-right:4px}
.after{margin-top:14px;display:flex;align-items:center;gap:14px;padding:12px 14px;border-radius:14px;background:rgba(255,193,77,.08);box-shadow:inset 0 0 0 1px rgba(255,193,77,.3)}
.after .n{font-size:36px;font-weight:800;color:#ffc14d;line-height:1}.after.hide{display:none}.after div{font-size:13px;color:rgba(255,255,255,.75)}
.after.rv{background:rgba(255,138,126,.09);box-shadow:inset 0 0 0 1px rgba(255,138,126,.35)}.after.rv .n{color:var(--nohi)}.after .lb b{display:block;font-size:14px;color:#fff;margin-bottom:2px}
main{padding:28px 0 48px}
.sec{display:flex;align-items:baseline;gap:12px;margin:34px 0 14px}.sec h2{font-size:21px;margin:0;letter-spacing:-.02em}.sec .d{margin:0}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:22px}
.ch{display:flex;align-items:center;gap:12px;margin-bottom:12px}.ic{width:40px;height:40px;border-radius:12px;background:var(--accbg);color:var(--acc);display:grid;place-items:center;flex:none}.ic svg{width:22px;height:22px}
.ic.red{background:var(--nobg);color:var(--no)}.ic.gr{background:#eef0f3;color:#3b4250}
.card h3{margin:0;font-size:17px}.d{color:var(--mu);font-size:13px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end}
button.b{font:inherit;font-size:15px;font-weight:600;padding:11px 16px;border-radius:12px;border:1px solid var(--line);background:#fff;color:var(--tx);cursor:pointer}
button.b:hover{border-color:#a9b1bd;background:#fafbfc}button.b:disabled{opacity:.5;cursor:wait}button.b.red{color:var(--no)}button.b.pri{background:var(--navy);color:#fff;border-color:var(--navy)}button.b.pri:hover{background:#12325c}
.qb{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.qb button{display:flex;flex-direction:column;align-items:center;gap:8px;padding:16px 6px;border-radius:16px;border:1px solid var(--line);background:#fff;font:inherit;font-size:14px;font-weight:600;color:var(--tx);cursor:pointer}
.qb button:hover{border-color:#a9b1bd;background:#fafbfc}.qb button:disabled{opacity:.5;cursor:wait}.qb svg{width:26px;height:26px;color:var(--navy)}
label.f{font-size:12px;color:var(--mu);display:flex;flex-direction:column;gap:5px}
input{font:inherit;width:130px;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:#f7f8fa;color:var(--tx)}input:focus{outline:2px solid var(--acc);outline-offset:-1px;background:#fff}
.err{color:var(--no);font-size:14px;min-height:20px;margin-top:10px}
.kc{font-size:13px;padding:5px 11px;border-radius:999px;background:#f1f3f6;color:#3b4250;font-weight:600}.kc.v{background:var(--okbg);color:var(--ok)}.kc.r{background:var(--nobg);color:var(--no)}
.kw{font-size:13px;margin-top:10px;padding:10px 12px;border-radius:10px;line-height:1.55}.kw.a{background:var(--wabg);color:var(--wa)}.kw.d{background:var(--nobg);color:var(--no)}
.hr{height:1px;background:var(--line);margin:16px 0}
.w{display:grid;grid-template-columns:110px 1fr;gap:4px 14px;padding:12px 0;border-bottom:1px solid var(--line);font-size:14px}.w:last-child{border-bottom:0}
.w .dir{color:var(--mu);font-size:13px}.w .dir b{color:var(--tx)}.w .k{font-weight:700}.w .k small{font-weight:500;color:var(--mu);margin-left:6px}
.hx{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;word-break:break-all;background:#f3f5f8;border-radius:6px;padding:1px 6px}
.hx i{font-style:normal;background:#ffd5d0;color:var(--no);font-weight:700}.hx em{font-style:normal;background:#d5f2e3;color:var(--ok);font-weight:700}
.note2{font-size:13px;margin-top:6px;padding:7px 11px;border-radius:9px}.note2.bad{background:var(--nobg);color:var(--no)}.note2.ok{background:var(--okbg);color:var(--ok)}.note2.mu{background:#f1f3f6;color:var(--mu)}
.modes{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.m{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;position:relative;cursor:pointer;transition:border-color .15s}
.m:hover{border-color:#a9b1bd}.m.dim{opacity:.55}.m.cur{border:2px solid var(--acc);background:var(--accbg);padding:17px}.m.pick{outline:2px dashed var(--acc);outline-offset:3px}
.m .k{display:inline-grid;place-items:center;min-width:34px;height:34px;padding:0 6px;border-radius:10px;background:var(--navy);color:#fff;font-weight:800;font-size:16px}.m .n{font-weight:700;margin-left:10px;font-size:16px}
.m p{margin:10px 0 12px;font-size:14px;color:#3b4250;line-height:1.6}
.m .now{position:absolute;top:16px;right:16px;font-size:12px;color:var(--acc);font-weight:700;display:none}.m.cur .now{display:block}
.tag{font-size:12px;font-weight:600;padding:4px 10px;border-radius:999px}.tag.ok{background:var(--okbg);color:var(--ok)}.tag.code{background:var(--wabg);color:var(--wa)}.tag.plan{background:#f1f3f6;color:var(--mu)}.tag.sel{background:var(--accbg);color:var(--acc)}
.how{background:#fff;border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:0;padding:16px 18px;margin-bottom:12px}.how.hide{display:none}
.howt{font-weight:700;margin-bottom:6px}.how ol{margin:0 0 8px;padding-left:22px;font-size:15px;line-height:1.85}.hown{font-size:13px;color:var(--mu)}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:11px 8px;border-bottom:1px solid var(--line)}th{color:var(--mu);font-weight:500;font-size:13px}
td.A{color:var(--ok);font-weight:700}td.D,td.H{color:var(--no);font-weight:700}
.note{color:var(--mu);font-size:13px;margin-top:14px;line-height:1.65}
.foot{color:var(--mu);font-size:12px;margin-top:22px;text-align:center}
@media (max-width:980px){.hgrid{grid-template-columns:1fr}.tiles{grid-template-columns:repeat(2,1fr)}.nav{display:none}}
@media (max-width:720px){.grid{grid-template-columns:1fr}.qb{grid-template-columns:repeat(2,1fr)}.team{display:none}.wrap{padding:0 16px}h1.vn{font-size:26px}.resbox .big{font-size:28px}}
</style></head><body>
<header class="top"><div class="wrap"><div class="logo"><b>SHARE</b>KEY</div>
<nav class="nav"><a href="#" class="on">내 차</a><a href="#keys">공유 키</a><a href="#wirebox">메시지</a><a href="#modesec">비교 방식</a><a href="#logsec">기록</a></nav>
<button class="snd" id="snd" onclick="toggleSnd()">소리 켜짐</button><div class="team">영남대 소프트웨어프로젝트 4조 졸업작품<br>시연용 가상 서비스</div></div></header>

<section class="hero"><div class="wrap hgrid">
<div>
<div class="eyebrow">MY CAR</div>
<h1 class="vn">시연 차량</h1>
<div class="vsub">휴대폰 앱 → Raspberry Pi(중계) → 차량 제어기 STM32(최종 판단)</div>
<span class="plate">4조 · NUCLEO-F429ZI</span>
<div class="car" id="car"><svg viewBox="0 0 560 210" aria-hidden="true"><defs><linearGradient id="beamg" x1="0" x2="1"><stop offset="0" stop-color="#fff8dc" stop-opacity=".9"/><stop offset="1" stop-color="#fff8dc" stop-opacity="0"/></linearGradient></defs>
<ellipse cx="282" cy="186" rx="250" ry="10" fill="rgba(0,0,0,.55)"/>
<path d="M28 150 C26 126 46 116 80 111 L158 100 C188 70 226 56 276 54 L344 54 C388 56 420 74 448 100 L496 108 C522 113 532 126 532 146 L532 160 C532 166 528 170 522 170 L36 170 C30 170 28 166 28 160 Z" fill="#cfd5de"/>
<path d="M28 150 C40 146 70 144 92 144 L470 144 C496 144 520 146 532 150 L532 160 C532 166 528 170 522 170 L36 170 C30 170 28 166 28 160 Z" fill="#aeb6c2"/>
<path d="M176 100 C202 76 236 64 278 63 L318 63 L318 100 Z" fill="#253247"/><path d="M328 63 L346 63 C382 64 410 79 432 100 L328 100 Z" fill="#253247"/>
<path d="M184 98 C204 80 232 70 268 68 L238 98 Z" fill="rgba(255,255,255,.12)"/>
<path id="cardoor" d="M174 104 L318 104 L318 146 L182 146 Q174 132 174 104 Z" fill="none" stroke="#8f99a8" stroke-width="1.5"/>
<rect x="282" y="112" width="24" height="5" rx="2.5" fill="#7e8898"/>
<circle class="lockpin" cx="246" cy="125" r="6" fill="#7e8898"/>
<polygon id="beam" points="528,118 560,96 560,160 528,132" fill="url(#beamg)"/>
<path id="headL" d="M500 116 L528 122 L526 132 L496 128 Z" fill="#fff4cf"/><path id="tailL" d="M30 124 L54 118 L56 128 L30 132 Z" fill="#d34b42"/>
<ellipse id="glowF" cx="514" cy="124" rx="22" ry="14" fill="#ffb020"/><ellipse id="glowR" cx="42" cy="125" rx="22" ry="14" fill="#ffb020"/>
<circle cx="128" cy="166" r="30" fill="#0d1118"/><circle cx="128" cy="166" r="17" fill="#3a4352"/><circle cx="128" cy="166" r="6" fill="#9aa3b0"/>
<circle cx="440" cy="166" r="30" fill="#0d1118"/><circle cx="440" cy="166" r="17" fill="#3a4352"/><circle cx="440" cy="166" r="6" fill="#9aa3b0"/>
</svg><div class="dhole"></div><div class="d3" id="d3"></div></div>
<div class="tiles">
<div class="tile"><div class="tl">도어 <span id="dsw"></span></div><div class="tv" id="door">잠김</div></div>
<div class="tile"><div class="tl">차량 통신</div><div class="tv"><span id="net" class="chip on">온라인<div class="ts">서버 연결됨</div></span></div></div>
<div class="tile"><div class="tl">비교 방식</div><div class="tv"><span id="mode" class="chip mode">확인 전</span></div></div>
<div class="tile"><div class="tl">시동</div><div class="tv" id="eng">꺼짐<div class="ts">판단만 (모터 끔)</div></div></div>
<div class="tile"><div class="tl">공유 키</div><div class="tv" id="kidt">7번 키</div></div>
</div>
</div>
<div class="panel">
<div class="ph"><b>원격 제어</b><span>공유 키 · 근거리 연결</span></div>
<div id="res" class="resbox N"><div class="lbl">차량 응답</div><div class="big" id="big">대기 중</div><div class="why" id="why">공유 키를 받은 뒤 문 열기를 눌러 보세요</div></div>
<button class="open" id="openbtn" onclick="go('open')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.8-1.2"/></svg>문 열기</button>
<div class="dots" id="dots"><span class="t">남은 오프라인 사용</span></div>
<div id="after" class="after hide"><div class="lb" id="afterl"><b>오프라인에서 허용된 횟수</b>정상 키 · 결제한 이용자도 똑같이 막힘</div><div class="n" id="aftern">0</div><div id="aftert">/ 0회 시도</div></div>
</div>
</div></section>

<main class="wrap">
<div class="sec" id="keys"><h2>공유 키</h2><span class="d">차 주인이 만들고, 받은 사람이 씁니다</span></div>
<div class="grid">
<div class="card"><div class="ch"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="15" r="4"/><path d="M10.8 12.2 20 3M17 6l3 3M14 9l2 2"/></svg></div><div><h3>차 주인 (카셰어링 업체)</h3><div class="d">공유 키를 만들어 주고, 반납 후 취소합니다</div></div></div>
<div class="row"><label class="f">공유 키 번호 (0~9, A~F)<input id="kid" value="7" maxlength="8" style="text-transform:uppercase"></label><label class="f">오프라인 사용 한도(회)<input id="lim" type="number" min="1" max="254" value="4"></label></div>
<div class="row" style="margin-top:12px"><button class="b pri" onclick="go('issue')">공유 키 만들기</button><button class="b red" onclick="go('revoke')">공유 키 취소</button><button class="b" onclick="newDemo()">새 시연 (다음 키 번호로)</button></div>
<div class="hr"></div><div class="d" style="margin-bottom:8px">키 현황 (서버 기록)</div><div id="kchips" class="row"></div><div id="kcount" class="d" style="margin-top:10px"></div><div id="kwarn"></div></div>
<div class="card"><div class="ch"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg></div><div><h3>키를 받은 사람 (이용자)</h3><div class="d">받은 키를 차에 등록하고 차를 씁니다</div></div></div>
<div class="qb">
<button onclick="go('register')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 21h16"/></svg>차에 키 등록</button>
<button onclick="go('open')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.8-1.2"/></svg>문 열기</button>
<button onclick="go('start')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v8"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/></svg>시동 걸기</button>
<button onclick="go('return')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/></svg>반납하기</button>
</div>
<div class="row" style="margin-top:10px"><button onclick="go('reauth')">지금 재인증</button><button onclick="go('stop')">시동 끄기</button></div>
<div id="drivestatus" class="d" style="margin-top:10px">차량 운행 상태 확인 중</div>
<div class="d" style="margin-top:12px;line-height:1.6">시동 허용 후 앱이 주기적으로 재인증합니다. 실패하면 경고하고, 주행 중에는 강제로 끄지 않습니다. 정차 상태는 차량 USER 버튼의 시연 가정이며 앱에서 바꾸지 않습니다. 기본 빌드는 모터가 꺼져 있어 논리적 운행 상태만 표시합니다.</div></div>
<div class="card"><div class="ch"><div class="ic red"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="M12 8v5M12 16h.01"/></svg></div><div><h3>공격 시험</h3><div class="d">취소된 사용자·공격자가 해 볼 만한 시도</div></div></div>
<div class="row"><button class="b" onclick="go('tamper')">위조된 요청 보내기</button><button class="b" onclick="go('replay')">가로챈 요청 다시 보내기</button></div>
<div class="d" style="margin-top:10px">결과는 차가 직접 판단합니다. 아래 "실제로 오간 메시지"에서 무엇이 달랐는지 볼 수 있습니다.</div></div>
<div class="card"><div class="ch"><div class="ic gr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8.5a15 15 0 0 1 20 0M5 12a10 10 0 0 1 14 0M8.5 15.5a5 5 0 0 1 7 0M12 19h.01"/><path d="M3 3l18 18"/></svg></div><div><h3>상황 연출 — 차량 통신</h3><div class="d">차가 서버와 통신할 수 없는 상태</div></div></div>
<div class="row"><button class="b red" onclick="go('net','off')">차량 오프라인</button><button class="b" onclick="go('net','on')">차량 온라인</button></div>
<div class="d" style="margin-top:10px;line-height:1.6">예: 지하주차장, 오래 시동을 걸지 않아 차의 통신이 멈춘 경우(현대 블루링크는 시동을 끈 뒤 48~336시간이 지나면 원격 서비스 중단). 휴대폰↔차 근거리 연결은 유지됩니다.</div>
<div class="err" id="err"></div></div>
</div>

<div class="sec"><h2>실제로 오간 메시지</h2><span class="d">마지막 요청</span></div>
<div class="card" id="wirebox"><div class="d" id="wirecap">버튼을 누르면 앱과 차(STM32)가 실제로 주고받은 메시지가 여기에 나옵니다. 판단은 차가 하고, 이 화면은 받은 응답을 보여 줄 뿐입니다.</div><div id="wire"></div></div>

<div class="sec" id="modesec"><h2>비교 방식</h2><span class="d">차가 언제 키를 막는가 · 카드를 누르면 바꾸는 법이 나옵니다. 지금 차량의 방식은 파란 테두리(첫 허용 응답 뒤)</span></div>
<div class="how hide" id="how"><div class="howt" id="howt"></div><div id="howb"></div>
<div class="hown">방식은 앱으로 바꿀 수 없습니다. 원격으로 바꿀 수 있으면 취소된 키를 가진 사람이 차를 A(제한 없음)로 바꿀 수 있기 때문에, 차에 손을 대야만 바꿀 수 있게 했습니다(시연용 기능).</div></div>
<div class="modes">
<div class="m" id="mA" onclick="howTo('A')"><span class="now">지금 차량</span><span class="k">A</span><span class="n">서버 취소만</span><p>서버가 "이 키 취소"라고 알려 줄 때만 막는다. 서버와 끊기면 취소된 키도 계속 열린다. 비교 기준선.</p><span class="tag ok">실물 시연</span> <span class="tag sel">USER 누른 채 RESET</span></div>
<div class="m" id="mB" onclick="howTo('B')"><span class="now">지금 차량</span><span class="k">B</span><span class="n">A + 대여 기간</span><p>공유할 때 정한 대여 기간(예: 24시간)이 끝나면 서버 없이도 막는다. 기간 안의 오프라인은 정상으로 둔다. 차에 믿을 수 있는 시계가 필요하다.</p><span class="tag code">판단 코드만 · 11/16~</span></div>
<div class="m" id="mC" onclick="howTo('C')"><span class="now">지금 차량</span><span class="k">C</span><span class="n">A + 오프라인 횟수</span><p>서버와 끊긴 동안은 정한 횟수(시연 4회)까지만 연다. 취소를 알아내는 게 아니라 피해에 상한을 두는 것. 정상 이용자도 같이 막히는 비용이 있다.</p><span class="tag ok">실물 시연</span> <span class="tag sel">그냥 RESET (기본)</span></div>
<div class="m" id="mT" onclick="howTo('T')"><span class="k">C-T</span><span class="n">A + 오프라인 시간</span><p>차가 오프라인을 판정한 때부터 정한 시간(T)이 지나면 막는다. 시작점은 차의 오프라인 판정(2초마다 서명된 응답 확인).</p><span class="tag plan">11/5 추가 · 계획</span></div>
<div class="m" id="mD" onclick="howTo('D')"><span class="now">지금 차량</span><span class="k">D</span><span class="n">A + 기간 + 횟수</span><p>B와 C를 함께 적용. 최종에는 대여 기간 안의 정상 이용자는 막지 않고, 취소·반납·기간 종료 뒤에만 제한하는 현실 알고리즘(D-현실)으로 발전시킨다.</p><span class="tag code">판단 코드만 · 11/16~</span></div>
<div class="m" id="mE" onclick="howTo('E')"><span class="k">E</span><span class="n">상황별 기간·횟수</span><p>가족, 대리·발레, 렌트·카셰어링, 엄격 같은 공유 상황마다 한도를 다르게 둔다.</p><span class="tag plan">계획 · 11/16 이후</span></div>
<div class="m dim" id="mF" onclick="howTo('F')"><span class="k">F</span><span class="n">E + AI 보류</span><p>Pi의 AI가 평소와 다른 사용을 보면 "재검증 대기"로 잠시 막는다. AI가 차의 제한을 풀 수는 없다.</p><span class="tag plan">확장 · 최종 범위 밖 (11/5)</span></div>
<div class="m dim" id="mG" onclick="howTo('G')"><span class="k">E+</span><span class="n">E + 단순 규칙</span><p>F와 비교하려는 대조군. AI 대신 "새벽 사용이면 보류" 같은 단순 규칙을 쓴다.</p><span class="tag plan">확장 · F와 함께</span></div>
</div>

<div class="sec" id="logsec"><h2>요청 기록</h2></div>
<div class="card"><table><thead><tr><th>#</th><th>시각</th><th>누가 · 무엇을</th><th>차량 응답</th><th>이유</th><th>남은 오프라인 사용</th></tr></thead><tbody id="log"></tbody></table>
<div class="note">차량 응답·이유·남은 횟수는 차량 제어기(STM32)가 보낸 결과 그대로입니다. 차량 오프라인(서버와 통신 불가) 상태에서 "오프라인 사용 한도 초과"로 막히는 것은 공유 때 정한 한도가 끝났기 때문이며, 차가 취소 사실을 알아낸 것은 아닙니다. 취소는 차량이 다시 온라인이 되어 서버와 연결된 뒤 인증된 동기화로 차에 전달되고, 그때부터 "취소된 키"로 막힙니다.</div></div>
<div class="foot">SHAREKEY는 시연용으로 지은 가상의 서비스 이름입니다 · 차량 __VEHICLE__ · 서버 __SERVER__</div>
</main>
<script>
const REASON={'00':'정상','01':'위조된 요청 (인증값 불일치)','02':'다시 보낸 요청 (일회용 값 재사용)','03':'취소된 키','04':'유효기간 만료','05':'오프라인 사용 한도 초과','06':'권한 없음','07':'재검증 대기','08':'등록되지 않은 키','09':'반납된 키'};
const WHAT={issue:'주인 · 공유 키 만들기',register:'이용자 · 차에 키 등록',open:'이용자 · 문 열기',start:'이용자 · 시동 걸기',return:'이용자 · 반납하기',reauth:'이용자 · 운행 재인증',stop:'이용자 · 시동 끄기',tamper:'공격 · 위조된 요청',replay:'공격 · 가로챈 요청 재전송',revoke:'주인 · 공유 키 취소'};
let n=0,revoked=false,afterOk=0,afterTry=0,netOn=true,limit=4,cur='',pick='';
const $=i=>document.getElementById(i);
function kidTile(){$('kidt').textContent=($('kid').value.trim().toUpperCase().replace(/^0+(?=.)/,'')||'-')+'번 키';}
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function setNet(on){netOn=on;$('net').className='chip '+(on?'on':'off');$('net').innerHTML=on?'온라인<div class="ts">서버 연결됨</div>':'오프라인<div class="ts">서버와 통신 불가</div>';}
function dots(left){let h='<span class="t">남은 오프라인 사용</span>';
 if(left===null){$('dots').innerHTML=h+'<span class="t">제한 없음</span>';return;}
 if(netOn){$('dots').innerHTML='<span class="t">서버 연결 중 · 쓰는 대로 곧 다시 채워짐 (오프라인 한도 '+limit+'회는 차량 오프라인일 때만 적용)</span>';return;}
 const tot=Math.max(limit,left);for(let i=0;i<tot;i++)h+='<span class="dot'+(i<left?' f':'')+'"></span>';
 $('dots').innerHTML=h+'<span class="t">'+left+' / '+tot+'회</span>';}
function mode(m){cur=m;['A','B','C','D'].forEach(k=>$('m'+k).classList.toggle('cur',k===m));
 $('mode').innerHTML=m+' 방식<div class="ts">'+(m==='A'?'서버 취소만':'횟수 제한')+'</div>';}
const KIND={REQ:'요청',CHAL:'도전값',RESP:'응답 (서명)',RES:'결과',KEY:'키 등록',KEYOK:'등록 성공',KEYNG:'등록 실패',ERR:'오류'};
const CMDN={'01':'문 열기','02':'시동','03':'반납','04':'재인증','05':'시동 끄기'};
function hx(s,diff,cls){if(!diff||!diff.length)return '<span class="hx">'+esc(s)+'</span>';let o='';for(let i=0;i<s.length;i++)o+=diff.includes(i)?'<'+cls+'>'+esc(s[i])+'</'+cls+'>':esc(s[i]);return '<span class="hx">'+o+'</span>';}
function keyno(h){return String(h).toUpperCase().replace(/^0+(?=.)/,'')+'번 키';}   /* 16진수 그대로: 0000000B -> B */
function wireRow(e,cmd){const f=e.f,k=f[0];let b='';
 if(k==='REQ')b=keyno(f[1])+' · '+(CMDN[f[2]]||f[2]);
 else if(k==='CHAL')b=keyno(f[1])+' · 일회용 숫자(nonce) '+hx(f[2])+'<div class="note2 mu">차가 방금 만든 무작위 숫자. 5초 안에 한 번만 쓸 수 있음</div>';
 else if(k==='RESP'){b=keyno(f[1])+' · '+(CMDN[f[2]]||f[2])+'<br>nonce '+hx(f[3])+'<br>서명 '+hx(f[4],e.diff,'i');
  if(e.good_tag!==undefined){if(e.diff&&e.diff.length)b+='<br>정상 서명 '+hx(e.good_tag,e.diff,'em')+'<div class="note2 bad">비밀키 없이 만든 요청: 정상 서명에서 '+e.diff.length+'글자(1비트)가 다름 → 차가 직접 계산한 서명과 맞지 않음</div>';
   else if(cmd==='replay')b+='<div class="note2 bad">'+(e.reused_at?'이 nonce는 '+e.reused_at+' 요청에서 이미 쓴 값':'예전 요청의 nonce')+'. 차에 새 도전값을 받지 않고 예전 응답을 그대로 다시 보냄</div>';
   else b+='<div class="note2 ok">정상 서명: '+keyno(f[1])+' 비밀값으로 계산</div>';}}
 else if(k==='RES')b=keyno(f[1])+' · <b>'+(f[2]==='A'?'허용':f[2]==='H'?'보류':'거부')+'</b> · '+(REASON[f[3]]||f[3])+' ('+f[3]+') · 남은 '+(f[4]==='FF'?'제한 없음':parseInt(f[4],16));
 else if(k==='KEY')b=keyno(f[1])+' · 한도 '+parseInt(f[3],16)+'회 · 발급 서명 '+hx(f[6].slice(0,16)+'…');
 else if(k==='KEYOK'||k==='KEYNG')b=keyno(f[1])+(f[2]?' · 이유 '+f[2]:'');
 else b=f.map(esc).join(' | ');
 return '<div class="w"><div class="dir"><b>'+e.from+'</b> → '+e.to+'</div><div><span class="k">'+k+'<small>'+(KIND[k]||'')+'</small></span><div>'+b+'</div></div></div>';}
function showWire(cmd,o){if(!o.wire||!o.wire.length)return;const v=o.wire.filter(e=>e.from==='차'||e.to==='차');if(!v.length)return;
 $('wirecap').textContent=(WHAT[cmd]||cmd)+' — 앱과 차가 실제로 주고받은 메시지 (판단은 차가 함)';$('wire').innerHTML=v.map(e=>wireRow(e,cmd)).join('');}
const OKTXT={open:'문 열림 허용',start:'시동 허용',return:'반납 완료',reauth:'재인증 허용',stop:'시동 끄기 허용',tamper:'허용',replay:'허용'};
const NOTXT={open:'거부 · 잠김 유지',start:'거부 · 시동 안 걸림',return:'반납 거부',reauth:'재인증 거부 · 차량 상태 확인',stop:'시동 끄기 거부',tamper:'거부 · 잠김 유지',replay:'거부 · 잠김 유지'};
const OKWHY={start:'정상 · 실물 모터는 아직 꺼져 있음(판단만)',return:'이 키는 차 안에서 바로 무효가 됩니다'};
function door(st){const c=$('car');c.classList.remove('unl','den');if(st)c.classList.add(st);$('door').innerHTML=st==='unl'?'<span style="color:var(--okhi)">잠금 해제</span><div class="ts">문 닫으면 다시 잠김</div>':st==='den'?'<span style="color:var(--nohi)">잠김 유지</span><div class="ts">거부됨</div>':'잠김';}
let sndOn=true;try{sndOn=localStorage.getItem('sk_snd')!=='0';}catch(e){}
let AC=null;
function tone(f,ms,at){if(!sndOn)return;try{AC=AC||new (window.AudioContext||window.webkitAudioContext)();const o=AC.createOscillator(),g=AC.createGain(),t=AC.currentTime+(at||0)/1000;
 o.type='square';o.frequency.value=f;g.gain.setValueAtTime(0.0001,t);g.gain.exponentialRampToValueAtTime(0.12,t+0.01);g.gain.exponentialRampToValueAtTime(0.0001,t+ms/1000);o.connect(g).connect(AC.destination);o.start(t);o.stop(t+ms/1000+0.02);}catch(e){}}
function toggleSnd(){sndOn=!sndOn;try{localStorage.setItem('sk_snd',sndOn?'1':'0');}catch(e){}$('snd').textContent=sndOn?'소리 켜짐':'소리 꺼짐';}
function eng(on){const c=$('car');c.classList.toggle('on',on);$('eng').innerHTML=(on?'<span style="color:var(--okhi)">켜짐</span>':'꺼짐')+'<div class="ts">판단만 (모터 끔)</div>';}
async function pollDriving(){if(document.hidden)return;try{const o=await(await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:'driving-status'})})).json();if(!o.ok){$('drivestatus').textContent='차량 운행 상태 연결 확인 필요';return;}eng(o.running);$('drivestatus').textContent=o.running?('운행 중 · '+(o.stopped?'정차 가정':'주행 가정')+' · '+(o.warning?'재인증 필요':('재검증 대기까지 '+o.left+'초'))):'운행 세션 꺼짐';}catch(e){$('drivestatus').textContent='차량 운행 상태 연결 확인 필요';}}
setInterval(pollDriving,1000);
function fx(k){const c=$('car');
 if(k==='unlock'){tone(1760,70,0);tone(1760,70,140);c.classList.remove('hz');void c.offsetWidth;c.classList.add('hz');}
 else if(k==='start'){tone(220,180,0);tone(330,220,160);eng(true);}
 else if(k==='deny'){tone(330,380,0);c.classList.remove('dn');void c.offsetWidth;c.classList.add('dn');}
 else if(k==='off'){eng(false);c.classList.remove('hz','dn');}}
function show(r,cmd){const c=$('res');c.className='resbox '+r.code;$('big').textContent=r.code==='A'?(OKTXT[cmd]||'허용'):r.code==='H'?'재검증 대기':(NOTXT[cmd]||'거부');
 $('why').textContent=(r.code==='A'&&OKWHY[cmd])?OKWHY[cmd]:(REASON[r.why]||r.reason);if(cmd!=='return')dots(r.left);if(r.code==='A'&&cmd!=='return')mode(r.left===null?'A':'C');
 if(cmd==='open'||cmd==='tamper'||cmd==='replay')door(r.code==='A'?'unl':'den');
 if(r.code==='A'&&cmd==='open')fx('unlock');else if(r.code==='A'&&cmd==='start')fx('start');else if(r.code==='A'&&cmd==='return')fx('off');
 else if(r.code!=='A'&&['open','start','tamper','replay'].includes(cmd))fx('deny');}
function afterBox(){const b=$('after');if(afterTry===0&&!revoked){b.className='after hide';return;}
 b.className='after'+(revoked?' rv':'');
 $('afterl').innerHTML=revoked?'<b>키 취소 뒤 오프라인에서 허용된 횟수</b>차는 취소를 모름 · 한도까지 열림':'<b>오프라인에서 허용된 횟수</b>정상 키 · 결제한 이용자도 똑같이 막힘 (제한의 비용)';
 $('aftern').textContent=afterOk;$('aftert').textContent='/ '+afterTry+'회 시도';}
function info(big,why){$('res').className='resbox N';$('big').textContent=big;$('why').textContent=why;}
function row(cmd,net,o){n++;const t=new Date().toLocaleTimeString('en-GB',{hour12:false});const tr=document.createElement('tr');const r=o.res;
 const w=cmd==='net'?(net==='on'?'상황 · 차량 온라인':'상황 · 차량 오프라인'):WHAT[cmd]+(cmd==='net'?'':' ('+esc($('kid').value)+'번 키)');
 tr.innerHTML=`<td>${n}</td><td>${t}</td><td>${w}</td>`+(r?`<td class="${r.code}">${r.code==='A'?'허용':r.code==='H'?'보류':'거부'}</td><td>${REASON[r.why]||esc(r.reason)}</td><td>${cmd==='return'?'—':r.left===null?'제한 없음':r.left+(netOn?' (연결 중 · 곧 채워짐)':'')}</td>`:
 `<td>${o.ok?'완료':'실패'}</td><td colspan="2">${esc(o.error||'')}</td>`);$('log').prepend(tr);}
async function go(cmd,net){$('err').textContent='';$('err').style.color='';document.querySelectorAll('button').forEach(b=>b.disabled=true);
 try{const q={cmd,kid:$('kid').value.trim(),limit:parseInt($('lim').value,10),net};
  const o=await (await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(q)})).json();
  row(cmd,net,o);showWire(cmd,o);if(!o.ok&&!o.res){$('err').textContent=o.error||'실패';return;}
  if(cmd==='issue'){cur='';['A','B','C','D'].forEach(k=>$('m'+k).classList.remove('cur'));$('mode').textContent='확인 전';limit=q.limit;revoked=false;afterOk=afterTry=0;$('after').className='after hide';$('aftern').textContent='0';$('aftert').textContent='/ 0회 시도';door('');fx('off');info('공유 키 발급됨',q.kid+'번 키 · 오프라인 한도 '+q.limit+'회');dots(q.limit);}
  if(cmd==='register')info(o.ok?'차에 키 등록됨':'등록 실패',o.ok?'이제 문을 열 수 있습니다':'차량 연결을 확인하세요');
  if(cmd==='revoke'){revoked=true;afterBox();info('키 취소 요청됨',netOn?'서버에 기록됨':'서버에는 기록됨 · 차는 오프라인이라 아직 모름');}
  if(cmd==='net'){if(net==='off'){afterOk=afterTry=0;afterBox();}setNet(net==='on');dots(limit);info(net==='on'?'차량 온라인':'차량 오프라인',net==='on'?'몇 초 뒤 서버와 동기화됩니다':'몇 초 뒤 차가 오프라인으로 전환됩니다');}
  if(o.res){show(o.res,cmd);if((cmd==='open'||cmd==='start')&&!netOn){afterTry++;if(o.res.code==='A')afterOk++;afterBox();}}
 }catch(e){$('err').textContent='웹 서버 연결 실패: '+e;}
 finally{document.querySelectorAll('button').forEach(b=>b.disabled=false);save();refreshState();}}
const NAMES={A:'A · 서버 취소만',B:'B · A + 대여 기간',C:'C · A + 오프라인 횟수',T:'C-T · A + 오프라인 시간',D:'D · A + 기간 + 횟수',E:'E · 상황별 기간·횟수',F:'F · E + AI 보류',G:'E+ · E + 단순 규칙'};
const LATER='<p>판단 코드는 있지만 차의 시계(RTC)가 아직 연결되지 않아 <b>지금은 고를 수 없습니다</b>. 11/16 이후 시계를 붙이면 같은 방법(USER 버튼)으로 고를 수 있게 됩니다.</p>';
const EXT='<p>지도교수 면담(11/5)에서 <b>확장 과제로 내렸습니다</b>. 먼저 A~D를 같은 조건에서 정량 비교한 뒤 시간이 남으면 다룹니다.</p>';
const PLAN='<p>계획 단계라 <b>아직 고를 수 없습니다</b>(11/16 이후 구현). 구현되면 같은 방법(USER 버튼)으로 고르게 됩니다.</p>';
const HOW={A:'<ol><li>차의 <b>파란 USER 버튼</b>을 누른 채로</li><li><b>검은 RESET 버튼</b>을 눌렀다 뗀다</li><li>차 화면(OLED) 첫 줄이 <b>A</b>가 되면 USER 버튼에서 손을 뗀다</li><li>차 안의 키가 지워지므로 <b>새 시연 → 공유 키 만들기 → 차에 키 등록</b></li></ol>',
 C:'<ol><li>차의 <b>검은 RESET 버튼</b>만 눌렀다 뗀다 (USER 버튼은 누르지 않음)</li><li>차 화면(OLED) 첫 줄이 <b>C</b>인지 확인 (기본 방식)</li><li>차 안의 키가 지워지므로 <b>새 시연 → 공유 키 만들기 → 차에 키 등록</b></li></ol>',
 B:LATER,D:LATER,E:PLAN,T:PLAN,F:EXT,G:EXT};
function howTo(k){if(pick===k){pick='';$('how').classList.add('hide');}else{pick=k;$('howt').textContent='방식 '+NAMES[k]+' — 바꾸는 법 (차에서 직접)';$('howb').innerHTML=HOW[k];$('how').classList.remove('hide');}
 ['A','B','C','T','D','E','F','G'].forEach(x=>$('m'+x).classList.toggle('pick',x===pick));}
async function newDemo(){$('err').textContent='';
 try{const o=await (await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:'nextkid',kid:$('kid').value.trim()})})).json();if(o.ok)$('kid').value=o.kid;}catch(e){}
 n=0;revoked=false;afterOk=afterTry=0;cur='';$('log').innerHTML='';$('wire').innerHTML='';$('after').className='after hide';$('aftern').textContent='0';$('aftert').textContent='/ 0회 시도';
 ['A','B','C','D'].forEach(k=>$('m'+k).classList.remove('cur'));$('mode').textContent='확인 전';limit=parseInt($('lim').value,10)||4;dots(limit);
 kidTile();door('');fx('off');info('새 시연 준비',$('kid').value+'번 키로 "공유 키 만들기"부터 시작하세요');
 $('err').textContent='예전 키는 서버와 차에 기록이 남아 있습니다(취소된 키는 되살아나지 않음). 아래 키 현황에서 경고가 뜨면 '+RESET_HOW;
 $('err').style.color='var(--mu)';save();refreshState();}
const RESET_HOW='전체 초기화: 서버 끄기 → keys 폴더·server_state.json 삭제 → 서버 켜기 → 차 RESET';
async function refreshState(){let o;try{o=await (await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:'state'})})).json();}catch(e){return;}
 if(!o||!o.ok)return;
 $('kchips').innerHTML=o.keys.length?o.keys.map(k=>'<span class="kc '+(k.revoked?'r':'v')+'">'+esc(k.kid)+'번 '+(k.revoked?'취소':'유효')+(k.reg?' · 차 등록':'')+'</span>').join(''):'<span class="d">아직 발급한 키 없음</span>';
 const rv=o.keys.filter(k=>k.revoked).length;
 $('kcount').textContent='발급 '+o.issued+' / '+o.sync_max+' (동기화 한도) · 취소 '+rv+' · 차에 등록 '+o.registered+' / '+o.board_max+' (차 한도)';
 let w='';
 if(o.issued>o.sync_max||o.registered>=o.board_max)w='<div class="kw d"><b>지금 전체 초기화가 필요합니다.</b> 실물 차는 키를 '+o.board_max+'개까지 등록하고, 동기화 목록은 '+o.sync_max+'개까지만 받습니다. 넘으면 등록이 실패하거나 동기화가 안 되어 취소가 반영되지 않습니다.<br>'+RESET_HOW+'</div>';
 else if(o.issued>=o.sync_max-4||o.registered>=o.board_max-2)w='<div class="kw a"><b>곧 전체 초기화가 필요합니다.</b> (차 등록 '+o.registered+'/'+o.board_max+', 발급 '+o.issued+'/'+o.sync_max+')<br>'+RESET_HOW+'</div>';
 $('kwarn').innerHTML=w;}
const SK='sharekey_demo_v1';
function save(){try{sessionStorage.setItem(SK,JSON.stringify({n,revoked,afterOk,afterTry,netOn,limit,cur,kid:$('kid').value,lim:$('lim').value,
 log:$('log').innerHTML,wire:$('wire').innerHTML,wirecap:$('wirecap').textContent,res:$('res').className,big:$('big').textContent,why:$('why').textContent,dots:$('dots').innerHTML,after:$('after').className,afterl:$('afterl').innerHTML,aftern:$('aftern').textContent,aftert:$('aftert').textContent,door:$('car').classList.contains('unl')?'unl':$('car').classList.contains('den')?'den':'',eng:$('car').classList.contains('on')}));}catch(e){}}
function restore(){let st=null;try{st=JSON.parse(sessionStorage.getItem(SK)||'null');}catch(e){}
 if(!st){dots(4);return;}
 ({n,revoked,afterOk,afterTry,netOn,limit}=st);$('kid').value=st.kid;$('lim').value=st.lim;$('log').innerHTML=st.log;if(st.wire){$('wire').innerHTML=st.wire;$('wirecap').textContent=st.wirecap;}$('res').className=st.res;$('big').textContent=st.big;$('why').textContent=st.why;
 $('dots').innerHTML=st.dots;$('after').className=st.after;if(st.afterl)$('afterl').innerHTML=st.afterl;$('aftern').textContent=st.aftern;$('aftert').textContent=st.aftert;setNet(netOn);if(st.cur)mode(st.cur);if(st.door)door(st.door);if(st.eng)eng(true);}
let dLast=null,dSeq=null,dFail=0;
async function pollDoor(){if(document.hidden)return;let o;try{o=await (await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:'door'})})).json();}catch(e){o={ok:false};}
 const c=$('car');
 if(!o.ok||o.door==='UNKNOWN'){if(++dFail>=3){c.classList.remove('live','dopen');$('dsw').textContent='';dLast=null;}return;}
 dFail=0;c.classList.add('live');
 if(o.door!==dLast){c.classList.toggle('dopen',o.door==='OPEN');$('dsw').innerHTML=o.door==='OPEN'?'· <span style="color:#ffc14d">열림</span>':'· 닫힘';
  if(dLast!==null&&o.door==='OPEN')tone(880,40,0);dLast=o.door;}
 if(dSeq!==null&&o.seq>dSeq){if(o.lock==='OK'){tone(1760,60,0);door('');$('door').innerHTML='잠김<div class="ts">문 닫힘 → 자동 잠금</div>';}
  else{$('door').innerHTML='<span style="color:var(--nohi)">잠금 안 됨</span><div class="ts">'+esc(o.lock)+'</div>';}}
 dSeq=o.seq;}
setInterval(pollDoor,400);
$('snd').textContent=sndOn?'소리 켜짐':'소리 꺼짐';restore();kidTile();$('kid').addEventListener('input',kidTile);refreshState();
</script></body></html>"""


def main():
    p = argparse.ArgumentParser(description="공유 차 키 시연 웹 화면 (app.py 를 그대로 호출)")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--lan", action="store_true", help="같은 망의 다른 기기(휴대폰)에서도 접속 허용")
    p.add_argument("--server", default=f"{app.SERVER_HOST}:{app.SERVER_PORT}")
    p.add_argument("--vehicle", default=f"{app.VEHICLE_HOST}:{app.VEHICLE_PORT}")
    p.add_argument("--door", default="", help="문 상태 알림 주소 (기본: 차량 주소의 포트+1, Pi 중계 9101)")
    p.add_argument("--reauth-period", type=float, default=60, help="웹 앱의 재인증 전송 간격(초)")
    a = p.parse_args()
    if a.reauth_period <= 0:
        p.error("재인증 전송 간격은 양수여야 합니다")
    OPT.server, OPT.vehicle, OPT.door = a.server, a.vehicle, a.door
    OPT.reauth_period = a.reauth_period
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    srv = ThreadingHTTPServer((host, a.port), H)
    print(f"[웹] http://127.0.0.1:{a.port}  (차량 {a.vehicle}, 서버 {a.server})")
    if a.lan:
        print("[웹] --lan: 같은 Wi-Fi 의 누구나 이 화면으로 명령을 보낼 수 있음. 시연 때만 사용")
        print("[웹] 휴대폰에서는 http://<이 노트북 IP>:%d  (IP: 맥 ipconfig getifaddr en0 / Windows ipconfig)" % a.port)
    print("[웹] 끄기: Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_auto_reauth()


if __name__ == "__main__":
    main()
