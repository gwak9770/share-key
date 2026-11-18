"""공통 규칙: 메시지 형식, HMAC 계산, 줄 단위 송수신.
모든 메시지는  RID|종류|필드...\n  형식 (RID = 2자리 16진수 요청 ID, 응답은 같은 RID를 돌려줌).
HMAC 입력은 16진수 문자열이 아니라 바이트, 정수는 빅엔디언."""
import hmac, hashlib, os, socket

VID = 0x0000CAFE
K_V = bytes(range(32))                 # 개발용 마스터키 (서버와 차량만 보유). 실제 사용 금지
SERVER_HOST, SERVER_PORT = "127.0.0.1", 9000
VEHICLE_HOST, VEHICLE_PORT = "127.0.0.1", 9100
NONCE_LIFE = 5.0                       # 챌린지 유효시간(초)

CMD_NAME = {1: "문열기", 2: "시동", 3: "반납"}
PERM_BIT = {1: 0x01, 2: 0x02}          # 반납(3)은 권한 검사 없음
REASON = {"00": "정상", "01": "인증값 불일치", "02": "nonce 만료·재사용", "03": "취소된 키",
          "04": "유효기간 만료", "05": "오프라인 횟수 초과", "06": "권한 없음",
          "07": "재검증 대기", "08": "등록되지 않은 키", "09": "반납된 키"}
RESULT = {"A": "허용", "D": "거부", "H": "재검증 대기"}
REASON["0A"] = "저장 장애·복구 필요"

u32 = lambda v: int(v).to_bytes(4, "big")
hx = lambda b: b.hex().upper()
H = lambda key, msg: hmac.new(key, msg, hashlib.sha256).digest()
eq = hmac.compare_digest


def derive(kid):                       # k_i = HMAC(K_v, "user" ‖ KID)
    return H(K_V, b"user" + u32(kid))


def auth_tag(ki, kid, cmd, nonce):     # HMAC(k_i, VID ‖ KID ‖ CMD ‖ NONCE)
    return H(ki, u32(VID) + u32(kid) + bytes([cmd]) + nonce)


def key_tag(kid, exp, limit, sit, perm):   # HMAC(K_v, "KEY" ‖ VID ‖ KID ‖ EXP ‖ LIMIT ‖ SIT ‖ PERM)
    return H(K_V, b"KEY" + u32(VID) + u32(kid) + u32(exp) + bytes([limit, sit, perm]))


def sync_tag(ver, nonce, entries):     # HMAC(K_v, "SYNC" ‖ VID ‖ VER ‖ NONCE ‖ COUNT ‖ (KID‖STATE)*)
    m = b"SYNC" + u32(VID) + u32(ver) + nonce + bytes([len(entries)])
    for kid, st in entries:
        m += u32(kid) + bytes([st])
    return H(K_V, m)


def enc_entries(entries):
    return ",".join(f"{k:08X}:{s:02X}" for k, s in entries) or "-"


def recovery_proof(kid, newkid, nonce, ki=None):
    return H(derive(kid) if ki is None else ki,
             b"RISSUE" + u32(VID) + nonce + u32(kid) + u32(newkid))


def recovery_tag(ver, nonce, kid, exp, limit, sit, perm):
    return H(K_V, b"RECOVER" + u32(VID) + nonce + u32(ver) + u32(kid)
             + u32(exp) + bytes((limit, sit, perm)))


def dec_entries(s):
    if s == "-":
        return []
    return [(int(a, 16), int(b, 16)) for a, b in (e.split(":") for e in s.split(","))]


class Conn:
    """줄 단위 송수신. Pi 중계/USB 시리얼도 같은 줄 형식을 그대로 넘기면 됨."""
    def __init__(self, sock):
        self.sock = sock
        self.f = sock.makefile("r", encoding="ascii", newline="\n")

    @classmethod
    def connect(cls, host, port, timeout=2.0):
        s = socket.create_connection((host, port), timeout=timeout)
        return cls(s)

    def send(self, rid, *fields):
        line = "|".join([rid, *map(str, fields)]) + "\n"
        self.sock.sendall(line.encode("ascii"))

    def recv(self):
        line = self.f.readline()
        if not line:
            raise ConnectionError("연결 끊김")
        p = line.rstrip("\n").split("|")
        return p[0], p[1:]

    def request(self, *fields):        # 보내고 같은 RID의 응답을 받음
        rid = os.urandom(1).hex().upper()
        self.send(rid, *fields)
        r, p = self.recv()
        if r != rid:
            raise ValueError(f"RID 불일치 {rid}≠{r}")
        return p

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
