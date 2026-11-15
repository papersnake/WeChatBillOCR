import base64
import json
import urllib.request

img = open('E:/rou/fixtures/bill_sample.png', 'rb').read()
b64 = base64.b64encode(img).decode()
req = urllib.request.Request(
    'http://127.0.0.1:1224/api/ocr',
    data=json.dumps({'base64': b64}).encode(),
    headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode('utf-8'))
for r in data['data']:
    print(f"{r['text']} | box:{r['box']}")
