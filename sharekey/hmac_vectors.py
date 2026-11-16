# 공유 차 키 - HMAC 테스트 벡터 (개발용)
# STM32 구현이 아래와 같은 값을 내면 통과. 모든 "‖"는 바이너리 바이트 이어붙이기, 정수는 빅엔디언.
import hmac, hashlib

H = lambda key, msg: hmac.new(key, msg, hashlib.sha256).digest()
u32 = lambda v: v.to_bytes(4, 'big')
hx = lambda b: b.hex().upper()

K_V = bytes(range(32))            # 개발용 마스터키 00 01 ... 1F (실제 사용 금지)
VID = 0x0000CAFE

def derive(kid):                  # k_i = HMAC(K_v, "user" ‖ KID)
    return H(K_V, b"user" + u32(kid))

def auth_tag(kid, cmd, nonce):    # TAG = HMAC(k_i, VID ‖ KID ‖ CMD ‖ NONCE)  (25바이트 입력)
    msg = u32(VID) + u32(kid) + bytes([cmd]) + nonce
    return H(derive(kid), msg), msg

def key_tag(kid, exp, limit, sit, perm):   # KEY: HMAC(K_v, "KEY" ‖ VID ‖ KID ‖ EXP ‖ LIMIT ‖ SIT ‖ PERM)
    msg = b"KEY" + u32(VID) + u32(kid) + u32(exp) + bytes([limit, sit, perm])
    return H(K_V, msg), msg

def sync_tag(ver, nonce, entries):         # SYNC: HMAC(K_v, "SYNC" ‖ VID ‖ VER ‖ NONCE ‖ COUNT ‖ (KID‖STATE)*)
    msg = b"SYNC" + u32(VID) + u32(ver) + nonce + bytes([len(entries)])
    for kid, st in entries:
        msg += u32(kid) + bytes([st])
    return H(K_V, msg), msg

out = []
p = out.append
p("=== 공통 값 ===")
p(f"K_V   = {hx(K_V)}")
p(f"VID   = {VID:08X}")
for kid in (0x00000007, 0x00000008):
    p(f"k_i(KID={kid:08X}) = {hx(derive(kid))}")

p("\n=== 1. 인증 응답 TAG (RESP) ===")
N0 = bytes(16)
N1 = bytes.fromhex("00112233445566778899AABBCCDDEEFF")
N2 = bytes.fromhex("A5" * 16)
cases = [("V1 문열기, nonce 0",         7, 0x01, N0),
         ("V2 문열기",                  7, 0x01, N1),
         ("V3 시동 (CMD만 다름)",       7, 0x02, N1),
         ("V4 반납",                    7, 0x03, N1),
         ("V5 다른 KID",                8, 0x01, N1),
         ("V6 다른 nonce",              7, 0x01, N2)]
for name, kid, cmd, n in cases:
    t, m = auth_tag(kid, cmd, n)
    p(f"[{name}]")
    p(f"  입력(25B) = {hx(m)}")
    p(f"  TAG       = {hx(t)}")
    p(f"  보낼 줄   = RESP|{kid:08X}|{cmd:02X}|{hx(n)}|{hx(t)}")

p("\n=== 2. 거부되어야 하는 경우 (V2 기준) ===")
t, _ = auth_tag(7, 0x01, N1)
bad = bytearray(t); bad[0] ^= 0x01
p(f"[X1 TAG 1비트 변조 → 사유 01]  RESP|00000007|01|{hx(N1)}|{hx(bad)}")
p(f"[X2 V2를 시동으로 바꿔치기 → 사유 01]  RESP|00000007|02|{hx(N1)}|{hx(t)}")
p(f"[X3 같은 줄 두 번 전송 → 두 번째는 사유 02 (nonce 재사용)]")

p("\n=== 3. 키 등록 (KEY) ===")
kt, km = key_tag(7, 1798761600, 4, 0x02, 0x03)   # 2027-01-01 00:00 UTC, N=4, 렌트, 문+시동
p("만료=1798761600(2027-01-01 00:00 UTC), 한도=4, 상황=02(렌트·카셰어링), 권한=03(문01|시동02)")
p(f"  입력 = {hx(km)}")
p(f"  TAG  = {hx(kt)}")
p(f"  보낼 줄 = KEY|00000007|{1798761600:08X}|04|02|03|{hx(kt)}")

p("\n=== 4. 동기화 (SYNC) ===")
st, sm = sync_tag(2, N2, [(7, 0x01), (8, 0x00)])
p("VER=2, nonce=A5×16, 항목: KID7=01(취소), KID8=00(유효)")
p(f"  입력 = {hx(sm)}")
p(f"  TAG  = {hx(st)}")
p(f"  보낼 줄 = SYNC|0000CAFE|00000002|{hx(N2)}|02|00000007:01,00000008:00|{hx(st)}")

text = "\n".join(out)
print(text)
open("hmac_vectors.txt", "w", encoding="utf-8").write(text + "\n")
