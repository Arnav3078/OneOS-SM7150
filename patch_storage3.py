import struct, shutil

shutil.copyfile("xnu_arm64_test.macho", "xnu_arm64_disk_test.macho")

with open("xnu_arm64_disk_test.macho", "rb") as f:
    buf = bytearray(f.read())

# 1. Patch _native_source_storage_parent (0xc0dba8) -> return IOService::gMetaClass (0xfffffff007d855b0)
# PC = 0xfffffff007c11ba8
# adrp x0, 0xfffffff007d85000:
# page diff = (0xfffffff007d85000 - 0xfffffff007c11000) >> 12 = 0x174 pages
# immlo = 0x174 & 3 = 0
# immhi = (0x174 >> 2) & 0x7ffff = 0x5d
# insn = 0x90000000 | (immlo << 29) | (immhi << 5) = 0x90000ba0
ADRP_IOSERVICE = 0x90000ba0
ADD_5B0 = 0x9116c000 # add x0, x0, #0x5b0
RET = 0xd65f03c0

struct.pack_into("<I", buf, 0xc0dba8, ADRP_IOSERVICE)
struct.pack_into("<I", buf, 0xc0dbac, ADD_5B0)
struct.pack_into("<I", buf, 0xc0dbb0, RET)
print("Patched _native_source_storage_parent -> return IOService::gMetaClass")

# 2. In _native_source_storage_start (0xc0dc0c), jump directly to class registration at 0xc0dcc8
# offset from 0xc0dc0c to 0xc0dcc8 = 0xbc = 47 instructions
B_DCC8 = 0x14000000 | 47
struct.pack_into("<I", buf, 0xc0dc0c, B_DCC8)
print("Patched 0xc0dc0c -> b 0xc0dcc8")

with open("xnu_arm64_disk_test.macho", "wb") as f:
    f.write(buf)

print("Saved xnu_arm64_disk_test.macho")
