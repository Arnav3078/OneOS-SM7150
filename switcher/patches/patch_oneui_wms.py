#!/usr/bin/env python3
"""Patch WindowManagerService.smali in One UI 9.5 services.jar to safely handle null mPrivacyDisplayController.

When CoreRune.FW_PRIVACY_DISPLAY is false, mPrivacyDisplayController is null.
WindowManagerService's privacy display binder methods invoke mPrivacyDisplayController without checking for null,
throwing NullPointerException and crashing SystemUIBg in a 5-second infinite loop.
This patch adds null checks:
- if-nez jumps to not-null label when non-null.
- when null (p0 == 0), if-nez falls through to return an empty ArrayList or return-void.
"""
import sys

def patch_wms(smali_path):
    with open(smali_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Patch getPrivacyDisplayCustomAppList
    target1 = """    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;

    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;"""

    replacement1 = """    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;

    if-nez p0, :cond_app_list_not_null

    new-instance v0, Ljava/util/ArrayList;

    invoke-direct {v0}, Ljava/util/ArrayList;-><init>()V

    return-object v0

    :cond_app_list_not_null
    invoke-virtual {p0}, Ljava/lang/Object;->getClass()Ljava/lang/Class;"""

    if target1 not in content:
        print("ERROR: could not find target1 in WindowManagerService.smali", file=sys.stderr)
        return False
    content = content.replace(target1, replacement1, 1)
    print("Patched getPrivacyDisplayCustomAppList")

    # 2. Patch resetAllPrivacyDisplaySettings
    target2 = """    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;

    invoke-virtual {p0}, Lcom/android/server/wm/PrivacyDisplayController;->resetAllSettings()V"""

    replacement2 = """    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;

    if-nez p0, :cond_reset_not_null

    return-void

    :cond_reset_not_null
    invoke-virtual {p0}, Lcom/android/server/wm/PrivacyDisplayController;->resetAllSettings()V"""

    if target2 in content:
        content = content.replace(target2, replacement2, 1)
        print("Patched resetAllPrivacyDisplaySettings")

    # 3. Patch setPrivacyDisplayPolicy
    target3 = """    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;

    invoke-virtual {p0, p1, p3, p2}, Lcom/android/server/wm/PrivacyDisplayController;->setAppPolicy(IILjava/lang/String;)V"""

    replacement3 = """    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;

    if-nez p0, :cond_policy_not_null

    return-void

    :cond_policy_not_null
    invoke-virtual {p0, p1, p3, p2}, Lcom/android/server/wm/PrivacyDisplayController;->setAppPolicy(IILjava/lang/String;)V"""

    if target3 in content:
        content = content.replace(target3, replacement3, 1)
        print("Patched setPrivacyDisplayPolicy")

    # 4. Patch requestPrivacyDisplayEnable
    target4 = """    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;

    const/4 v2, 0x0

    invoke-virtual {p0, p2, p1, v2}, Lcom/android/server/wm/PrivacyDisplayController;->requestPrivacyDisplayEnable(Ljava/lang/String;ZZ)V"""

    replacement4 = """    iget-object p0, p0, Lcom/android/server/wm/WindowManagerService;->mExt:Lcom/android/server/wm/WindowManagerServiceExt;

    iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;

    if-nez p0, :cond_enable_not_null

    invoke-static {v0, v1}, Landroid/os/Binder;->restoreCallingIdentity(J)V

    return-void

    :cond_enable_not_null
    const/4 v2, 0x0

    invoke-virtual {p0, p2, p1, v2}, Lcom/android/server/wm/PrivacyDisplayController;->requestPrivacyDisplayEnable(Ljava/lang/String;ZZ)V"""

    if target4 in content:
        content = content.replace(target4, replacement4, 1)
        print("Patched requestPrivacyDisplayEnable")

    with open(smali_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("Successfully patched WindowManagerService.smali")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: patch_oneui_wms.py <WindowManagerService.smali>")
        sys.exit(1)
    if not patch_wms(sys.argv[1]):
        sys.exit(1)
