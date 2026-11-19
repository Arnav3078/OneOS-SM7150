#!/usr/bin/env python3
"""One UI 9.5: Disable VaultKeeper, DmcService VaultKeeper calls, and RTTS client.

On Samsung devices without hardware Knox Vault (e.g. Galaxy M51 SM7150),
VaultKeeperService.nativeWrite and RealTimeTokenService (librtts_client.so)
block indefinitely in AServiceManager_waitForService waiting for HALs
that never exist on non-Vault hardware.

This blocks DmcService$LifeCycle.onBootPhase(1000), which freezes SystemServer
and android.display thread in FutureTask.get(), preventing User 0 from
completing boot (stuck at 'Phone is starting...') and causing Watchdog to
kill system_server after 277 seconds.

This patch:
1. Sets VaultKeeperService.mServiceSupport = 0 in <init>, making all
   VaultKeeper AIDL calls return ERROR_NOT_SUPPORTED (-0x68) immediately
   without calling native methods.
2. Makes DmcService$LifeCycle.onBootPhase(I)V an immediate return-void.
3. Sets TokenJniBridge.jniLoaded = false in <clinit>, preventing RTTS
   native calls.
"""
import os
import re
import sys

VK_REL = os.path.join("com", "android", "server", "VaultKeeperService.smali")
DMC_REL = os.path.join("com", "android", "server", "DmcService$LifeCycle.smali")
TOKEN_REL = os.path.join("com", "android", "server", "TokenJniBridge.smali")

MARK_VK = "# OneOS: VaultKeeper off (oneui_no_vaultkeeper.py)"
MARK_DMC = "# OneOS: DmcService onBootPhase no-op (oneui_no_vaultkeeper.py)"
MARK_TOKEN = "# OneOS: RTTS off (oneui_no_vaultkeeper.py)"


def patch_vk(root):
    hits = [d for d in sorted(os.listdir(root))
            if d.startswith("smali") and os.path.isfile(os.path.join(root, d, VK_REL))]
    if not hits:
        print("VaultKeeperService not present", file=sys.stderr)
        return None
    p = os.path.join(root, hits[0], VK_REL)
    t = open(p).read()
    if MARK_VK in t:
        return hits[0]
    
    pattern = re.compile(
        r"([ \t]*invoke-direct \{p0\}, Lcom/android/server/VaultKeeperService;->nativeGetSystemSolution\(\)I\s+"
        r"[ \t]*move-result ([vp]\d+)\s+"
        r"[ \t]*iput \2, p0, Lcom/android/server/VaultKeeperService;->mServiceSupport:I)"
    )
    m = pattern.search(t)
    if not m:
        sys.exit("oneui_no_vaultkeeper: target pattern not found in VaultKeeperService.<init>")
    
    reg = m.group(2)
    repl = (f"    {MARK_VK}\n"
            f"    const/4 {reg}, 0x0\n\n"
            f"    iput {reg}, p0, Lcom/android/server/VaultKeeperService;->mServiceSupport:I")
    t = t[:m.start(1)] + repl + t[m.end(1):]
    with open(p, "w") as f:
        f.write(t)
    return hits[0]


def patch_dmc(root):
    hits = [d for d in sorted(os.listdir(root))
            if d.startswith("smali") and os.path.isfile(os.path.join(root, d, DMC_REL))]
    if not hits:
        print("DmcService$LifeCycle not present", file=sys.stderr)
        return None
    p = os.path.join(root, hits[0], DMC_REL)
    t = open(p).read()
    if MARK_DMC in t:
        return hits[0]
    m = re.search(r"^\.method public (?:final )?onBootPhase\(I\)V\n(.*?)\n\.end method", t, re.M | re.S)
    if not m:
        sys.exit("oneui_no_vaultkeeper: onBootPhase not found in DmcService$LifeCycle")
    repl = (f".method public final onBootPhase(I)V\n"
            f"    .registers 2\n\n"
            f"    {MARK_DMC}\n"
            f"    return-void\n"
            f".end method")
    t = t[:m.start(0)] + repl + t[m.end(0):]
    with open(p, "w") as f:
        f.write(t)
    return hits[0]


def patch_token(root):
    hits = [d for d in sorted(os.listdir(root))
            if d.startswith("smali") and os.path.isfile(os.path.join(root, d, TOKEN_REL))]
    if not hits:
        print("TokenJniBridge not present", file=sys.stderr)
        return None
    p = os.path.join(root, hits[0], TOKEN_REL)
    t = open(p).read()
    if MARK_TOKEN in t:
        return hits[0]
    m = re.search(r"^\.method [^\n]*<clinit>\(\)V\n(.*?)\n\.end method", t, re.M | re.S)
    if not m:
        sys.exit("oneui_no_vaultkeeper: <clinit> not found in TokenJniBridge")
    repl = (f".method public static constructor <clinit>()V\n"
            f"    .registers 1\n\n"
            f"    {MARK_TOKEN}\n"
            f"    const/4 v0, 0x0\n\n"
            f"    sput-boolean v0, Lcom/android/server/TokenJniBridge;->jniLoaded:Z\n\n"
            f"    return-void\n"
            f".end method")
    t = t[:m.start(0)] + repl + t[m.end(0):]
    with open(p, "w") as f:
        f.write(t)
    return hits[0]


def main(root):
    changed = set()
    for fn in [patch_vk, patch_dmc, patch_token]:
        d = fn(root)
        if d:
            changed.add(d)
    print(" ".join(sorted(changed)))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: oneui_no_vaultkeeper.py <apktool or smali root dir>")
    main(sys.argv[1])
