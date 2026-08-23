import subprocess
import time
import json

pipe_name = r"\\.\pipe\mpv-test"
print(f"Starting mpv with IPC: {pipe_name}")
p = subprocess.Popen([r"D:\AnimusSmartRoom\server\bin\mpv.com", "--idle=yes", "--no-video", f"--input-ipc-server={pipe_name}"])
time.sleep(1.0)

try:
    with open(pipe_name, "r+b", buffering=0) as f:
        cmd = json.dumps({"command": ["get_property", "idle-active"]}) + "\n"
        f.write(cmd.encode("utf-8"))
        f.flush()
        response = f.readline()
        print("Received IPC response:", response.decode("utf-8"))
finally:
    p.kill()
