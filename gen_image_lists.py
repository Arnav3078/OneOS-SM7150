import subprocess
import json

# Get all files and their stat from device
cmd = ['adb', 'shell', 'su 0 find /data/local/tmp/test_set -type f -exec stat -c "%d:%i:%s:%Y %n" {} +']
res = subprocess.run(cmd, capture_output=True, text=True)
lines = res.stdout.strip().splitlines()

ids_list = []
sums_list = []

# Get manifest
cmd_man = ['adb', 'shell', 'su 0 cat /data/local/tmp/test_set/manifest.json']
man = json.loads(subprocess.run(cmd_man, capture_output=True, text=True).stdout)

file_shas = {f['path']: f['sha256'] for f in man['files']}

# Also sha256 of manifest.json
cmd_m_sha = ['adb', 'shell', 'su 0 sha256sum /data/local/tmp/test_set/manifest.json']
man_sha = subprocess.run(cmd_m_sha, capture_output=True, text=True).stdout.split()[0]
file_shas['manifest.json'] = man_sha

for line in lines:
    parts = line.strip().split()
    if len(parts) >= 2:
        fid = parts[0]
        full_path = parts[1]
        rel_path = full_path.replace('/data/local/tmp/test_set/', '')
        sha = file_shas.get(rel_path)
        if not sha:
            # compute sha
            c = ['adb', 'shell', f'su 0 sha256sum {full_path}']
            sha = subprocess.run(c, capture_output=True, text=True).stdout.split()[0]
        ids_list.append(f"{fid}  {rel_path}")
        sums_list.append(f"{sha}  {rel_path}")

ids_list.sort(key=lambda x: x.split("  ")[1])
sums_list.sort(key=lambda x: x.split("  ")[1])

# Write locally first
with open("image.new.sha256", "w", newline="\n") as f:
    f.write("\n".join(sums_list) + "\n")

with open("image.new.ids", "w", newline="\n") as f:
    f.write("\n".join(ids_list) + "\n")

print(f"Generated {len(sums_list)} entries.")
for s in sums_list:
    print(" ", s)
