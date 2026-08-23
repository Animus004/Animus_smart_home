import base64
import http.cookiejar
import ssl
import urllib.parse
import urllib.request
import time
import subprocess

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

cj = http.cookiejar.CookieJar()
auth_handler = urllib.request.HTTPBasicAuthHandler()
auth_handler.add_password('Windows Device Portal', 'https://127.0.0.1:50443', 'dummy', 'V10302024')
opener = urllib.request.build_opener(auth_handler, urllib.request.HTTPCookieProcessor(cj), urllib.request.HTTPSHandler(context=ctx))

opener.open('https://127.0.0.1:50443/certprompt.htm')
csrf = [c.value for c in cj if c.name == 'CSRF-Token'][0]
headers = {'X-CSRF-Token': csrf}

aep_id = 'Bluetooth#Bluetoothac:a7:f1:79:cf:36-54:15:89:dc:a5:79'
b64_aep = base64.b64encode(aep_id.encode('utf-8')).decode('ascii')
url_b64 = urllib.parse.quote(b64_aep)

print('=== Parameter Syntax Tests for /api/bt/connectdevice ===')
print('Raw AEP ID:', aep_id)
print('Base64 AEP ID:', b64_aep)

for param in ['ID', 'id', 'mac', 'deviceId']:
    for val in [url_b64, urllib.parse.quote(aep_id)]:
        url = f'https://127.0.0.1:50443/api/bt/connectdevice?{param}={val}'
        print(f'\nDispatching POST {url}...')
        try:
            req = urllib.request.Request(url, data=b'', headers=headers, method='POST')
            res = opener.open(req, timeout=5)
            body = res.read().decode('utf-8-sig', errors='ignore')
            print(f'-> SUCCESS: HTTP {res.status}, Body: {body}')
        except urllib.error.HTTPError as he:
            err_body = he.read().decode('utf-8-sig', errors='ignore')
            print(f'-> HTTP ERROR {he.code}: {err_body}')
        except Exception as e:
            print(f'-> EXCEPTION: {e}')

time.sleep(1)
res_mpv = subprocess.run([r'D:\AnimusSmartRoom\server\bin\mpv.com', '--audio-device=help'], capture_output=True, text=True)
print('\nLG in mpv after test:', 'LG SNC4R' in res_mpv.stdout)
