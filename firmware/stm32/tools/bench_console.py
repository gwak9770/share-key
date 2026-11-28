#!/usr/bin/env python3
"""Explicit local TEST_BUILD=1 console. This is not the authenticated Pi relay."""
import argparse
import threading
import time
import re

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True)
    args = ap.parse_args()
    try:
        import serial
    except ImportError:
        raise SystemExit("Install pyserial: python -m pip install pyserial")
    stop = threading.Event()
    lock = threading.Lock()
    with serial.Serial(args.port, 115200, timeout=0.1, write_timeout=1) as connection:
        def send(text):
            with lock:
                connection.write((text+"\n").encode("ascii"))
        def heartbeat():
            while not stop.is_set():
                try: send("F0|HB")
                except (serial.SerialException, OSError):
                    stop.set(); return
                stop.wait(0.25)
        def receive():
            pending = bytearray()
            while not stop.is_set():
                try: chunk = connection.read(256)
                except (serial.SerialException, OSError):
                    stop.set(); return
                pending.extend(chunk)
                while b"\n" in pending:
                    line, _, remainder = pending.partition(b"\n")
                    pending[:] = remainder
                    print(line.decode("ascii", errors="replace").rstrip("\r"))
                if len(pending) > 4096: pending.clear()
        threads = [threading.Thread(target=heartbeat, daemon=True), threading.Thread(target=receive, daemon=True)]
        for thread in threads: thread.start()
        print("TEST_BUILD=1 only. STATUS / LOCK / UNLOCK / SERVO 0|500..2500 / MOTOR -600..600 / RTC / RTC SET YYYY-MM-DD HH:MM:SS / STOP / CLEAR / QUIT")
        try:
            while not stop.is_set():
                command = input("> ").strip().upper()
                if command == "QUIT": break
                valid = command in {"STATUS","LOCK","UNLOCK","STOP","CLEAR"}
                if re.fullmatch(r"MOTOR -?[0-9]+", command):
                    valid = -600 <= int(command.split()[1]) <= 600
                if re.fullmatch(r"SERVO [0-9]+", command):
                    pulse = int(command.split()[1])
                    valid = pulse == 0 or 500 <= pulse <= 2500
                if command == "RTC" or re.fullmatch(r"RTC SET \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", command):
                    valid = True   # VC_ENABLE_RTC=1 builds only; the board checks the date itself (1128)
                if not valid:
                    print("Unknown command, motor outside -600..600, servo outside 0/500..2500, "
                          "or RTC SET not YYYY-MM-DD HH:MM:SS."); continue
                send("TEST "+command)
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            try: send("TEST STOP"); time.sleep(0.1)
            except (serial.SerialException, OSError): pass
            stop.set()
            for thread in threads: thread.join(timeout=1)

if __name__ == "__main__":
    main()
