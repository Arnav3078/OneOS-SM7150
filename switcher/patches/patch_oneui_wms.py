#!/usr/bin/env python3
"""Patch WindowManagerService.smali in One UI 9.5 services.jar to safely handle null mPrivacyDisplayController.

When CoreRune.FW_PRIVACY_DISPLAY is false, mPrivacyDisplayController is not instantiated (null).
WindowManagerService's privacy display binder methods blindly invoke mPrivacyDisplayController.getClass()
or controller methods, throwing NullPointerException and crashing SystemUI in an infinite loop.
This patch adds null checks to return an empty ArrayList for custom app list, and safe no-ops for
reset/policy/enable calls.
"""
import sys
import re

def patch_wms(smali_path):
    with open(smali_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Patch getPrivacyDisplayCustomAppList
    pattern1 = r'''(\.method public final getPrivacyDisplayCustomAppList\(I\)Ljava/util/List;.*?iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;\s*\n)(\s*invoke-virtual \{p0\}, Ljava/lang/Object;->getClass\(\)Ljava/lang/Class;)'''
    
    replacement1 = r'''\1    if-nez p0, :cond_ctrl_null_ret_empty\n\n    goto :cond_ctrl_not_null\n\n    :cond_ctrl_null_ret_empty\n    new-instance v0, Ljava/util/ArrayList;\n\n    invoke-direct {v0}, Ljava/util/ArrayList;-><init>()V\n\n    return-object v0\n\n    :cond_ctrl_not_null\n\2'''

    if not re.search(pattern1, content, re.DOTALL):
        print("ERROR: could not find getPrivacyDisplayCustomAppList pattern", file=sys.stderr)
        return False
        
    content, count1 = re.subn(pattern1, replacement1, content, count=1, flags=re.DOTALL)
    print(f"Patched getPrivacyDisplayCustomAppList (count: {count1})")

    # 2. Patch resetAllPrivacyDisplaySettings
    pattern2 = r'''(\.method public final resetAllPrivacyDisplaySettings\(\)V.*?iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;\s*\n)(\s*invoke-virtual \{p0\}, Lcom/android/server/wm/PrivacyDisplayController;->resetAllSettings\(\)V)'''
    replacement2 = r'''\1    if-nez p0, :cond_ctrl_null_ret_void1\n\n    goto :cond_ctrl_not_null1\n\n    :cond_ctrl_null_ret_void1\n    return-void\n\n    :cond_ctrl_not_null1\n\2'''

    if re.search(pattern2, content, re.DOTALL):
        content, count2 = re.subn(pattern2, replacement2, content, count=1, flags=re.DOTALL)
        print(f"Patched resetAllPrivacyDisplaySettings (count: {count2})")

    # 3. Patch setPrivacyDisplayPolicy
    pattern3 = r'''(\.method public final setPrivacyDisplayPolicy\(ILjava/lang/String;I\)V.*?iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;\s*\n)(\s*invoke-virtual \{p0, p1, p3, p2\}, Lcom/android/server/wm/PrivacyDisplayController;->setAppPolicy\(IILjava/lang/String;\)V)'''
    replacement3 = r'''\1    if-nez p0, :cond_ctrl_null_ret_void2\n\n    goto :cond_ctrl_not_null2\n\n    :cond_ctrl_null_ret_void2\n    return-void\n\n    :cond_ctrl_not_null2\n\2'''

    if re.search(pattern3, content, re.DOTALL):
        content, count3 = re.subn(pattern3, replacement3, content, count=1, flags=re.DOTALL)
        print(f"Patched setPrivacyDisplayPolicy (count: {count3})")

    # 4. Patch requestPrivacyDisplayEnable
    pattern4 = r'''(iget-object p0, p0, Lcom/android/server/wm/WindowManagerServiceExt;->mPrivacyDisplayController:Lcom/android/server/wm/PrivacyDisplayController;\s*\n)(\s*const/4 v2, 0x0\s*\n\s*invoke-virtual \{p0, p2, p1, v2\}, Lcom/android/server/wm/PrivacyDisplayController;->requestPrivacyDisplayEnable\(Ljava/lang/String;ZZ\)V)'''
    replacement4 = r'''\1    if-nez p0, :cond_ctrl_null_ret_void3\n\n    goto :cond_ctrl_not_null3\n\n    :cond_ctrl_null_ret_void3\n    invoke-static {v0, v1}, Landroid/os/Binder;->restoreCallingIdentity(J)V\n\n    return-void\n\n    :cond_ctrl_not_null3\n\2'''

    if re.search(pattern4, content, re.DOTALL):
        content, count4 = re.subn(pattern4, replacement4, content, count=1, flags=re.DOTALL)
        print(f"Patched requestPrivacyDisplayEnable (count: {count4})")

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
