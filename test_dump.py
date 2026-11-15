#!/usr/bin/env python3
import subprocess
import xml.etree.ElementTree as ET
import os

ADB_PATH = r"E:\rou\scrcpy\scrcpy-win64-v3.2\adb.exe"
DEVICE = "192.168.8.237:40943"

def run_adb(args):
    cmd = [ADB_PATH, "-s", DEVICE] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0:
        print(f"adb stderr: {result.stderr.strip()}")
    return result.stdout.strip(), result.returncode

import time
print("Dumping UI...")
time.sleep(2)
_, code = run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
print(f"dump return code: {code}")

_, code = run_adb(["pull", "/sdcard/window_dump.xml", "output/window_dump.xml"])
print(f"pull return code: {code}")

if os.path.exists("output/window_dump.xml"):
    tree = ET.parse("output/window_dump.xml")
    root = tree.getroot()
    texts = [node.get("text", "").strip() for node in root.iter() if node.get("text", "").strip()]
    print(f"Found {len(texts)} text nodes")
    for t in texts[:80]:
        print(t)
else:
    print("window_dump.xml not found")
