import subprocess
import os

print("=== Step 1: Pushing xnu_arm64_bdev_final.macho to device ===")
subprocess.check_call(["adb", "push", "xnu_arm64_bdev_final.macho", "/sdcard/kernel.kc"])
subprocess.check_call(["adb", "shell", "su 0 cp /sdcard/kernel.kc /data/local/tmp/oneios/image/kernel.kc"])
subprocess.check_call(["adb", "shell", "su 0 cp /sdcard/kernel.kc /data/local/tmp/test_kernel.kc"])
subprocess.check_call(["adb", "shell", "su 0 chmod 644 /data/local/tmp/oneios/image/kernel.kc /data/local/tmp/test_kernel.kc"])
print("Pushed and copied to /data/local/tmp/oneios/image/kernel.kc and /data/local/tmp/test_kernel.kc")

print("\n=== Step 2: Updating kernel hashes and manifest ===")
subprocess.check_call(["python", "update_kc_meta.py"])

print("\n=== Step 3: Generating and pushing image.sha256 and image.ids ===")
subprocess.check_call(["python", "gen_image_lists.py"])

print("\n=== Step 4: Running oneios_switch.sh --check ===")
res = subprocess.run(["adb", "shell", "su 0 /data/local/tmp/oneios/oneios_switch.sh --check"], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)
assert res.returncode == 0, f"Preflight check failed with exit code {res.returncode}"
print("=== DEPLOYMENT AND PREFLIGHT VERIFICATION SUCCESSFUL! ===")

