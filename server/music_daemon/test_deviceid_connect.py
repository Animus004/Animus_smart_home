import base64
import http.cookiejar
import json
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

url = f'https://127.0.0.1:50443/api/bt/connectdevice?deviceId={url_b64}'
print(f'T0: Dispatching POST {url}...')

t0 = time.time()
req = urllib.request.Request(url, data=b'', headers=headers, method='POST')
res = opener.open(req, timeout=5)
print(f'-> HTTP Status: {res.status} in {time.time() - t0:.2f}s')

print('\nPolling Windows Bluetooth state and WASAPI endpoint for 15 seconds...')
for i in range(15):
    time.sleep(1)
    # Check paired state via Device Portal
    req_paired = urllib.request.Request('https://127.0.0.1:50443/api/bt/getpaired', headers=headers)
    paired_data = json.loads(opener.open(req_paired).read().decode('utf-8-sig'))
    lg_audio_status = 'Unknown'
    for d in paired_data.get('PairedDevices', []):
        if '54:15:89:dc:a5:79' in d.get('ID', '').lower():
            lg_audio_status = d.get('AudioConnectionStatus')

    res_mpv = subprocess.run([r'D:\AnimusSmartRoom\server\bin\mpv.com', '--audio-device=help'], capture_output=True, text=True)
    lg_in_mpv = 'LG SNC4R' in res_mpv.stdout
    print(f'  T+{i+1}s: DevicePortal AudioStatus = {lg_audio_status} | mpv WASAPI = {lg_in_mpv}')
    if lg_in_mpv:
        print(f'\n>>> [CAUSALITY CONFIRMED] LG SNC4R WASAPI Endpoint appeared at T+{i+1}s!')
        break
