import subprocess
import json

stage = "/data/local/tmp/oneios/image"

cmd = ['adb', 'shell', f'su 0 find {stage} -type f -exec stat -c "%d:%i:%s:%Y %n" {{}} +']
res = subprocess.run(cmd, capture_output=True, text=True)
lines = res.stdout.strip().splitlines()

ids_list = []
sums_list = []

cmd_man = ['adb', 'shell', f'su 0 cat {stage}/manifest.json']
man = json.loads(subprocess.run(cmd_man, capture_output=True, text=True).stdout)

file_shas = {f['path']: f['sha256'] for f in man['files']}

cmd_m_sha = ['adb', 'shell', f'su 0 sha256sum {stage}/manifest.json']
man_sha = subprocess.run(cmd_m_sha, capture_output=True, text=True).stdout.split()[0]
file_shas['manifest.json'] = man_sha

for line in lines:
    parts = line.strip().split()
    if len(parts) >= 2:
        fid = parts[0]
        full_path = parts[1]
        rel_path = full_path.replace(f'{stage}/', '')
        sha = file_shas.get(rel_path)
        if not sha:
            c = ['adb', 'shell', f'su 0 sha256sum {full_path}']
            sha = subprocess.run(c, capture_output=True, text=True).stdout.split()[0]
        ids_list.append(f"{fid}  {rel_path}")
        sums_list.append(f"{sha}  {rel_path}")

ids_list.sort(key=lambda x: x.split("  ")[1])
sums_list.sort(key=lambda x: x.split("  ")[1])

with open("image.sha256", "w", newline="\n") as f:
    f.write("\n".join(sums_list) + "\n")

with open("image.ids", "w", newline="\n") as f:
    f.write("\n".join(ids_list) + "\n")

subprocess.check_call(["adb", "push", "image.sha256", "/sdcard/image.sha256"])
subprocess.check_call(["adb", "push", "image.ids", "/sdcard/image.ids"])
subprocess.check_call(["adb", "shell", f"su 0 cp /sdcard/image.sha256 /data/local/tmp/oneios/image.sha256"])
subprocess.check_call(["adb", "shell", f"su 0 cp /sdcard/image.ids /data/local/tmp/oneios/image.ids"])

print(f"Generated and pushed {len(sums_list)} entries.")
