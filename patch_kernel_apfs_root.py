import struct
import build_bdev_driver as bld

print("=== Assembling bdev driver, custom vnodeops, launchd, and dyld ===")

# =====================================================================
# Base executable padding in __TEXT_EXEC and routine layout
# =====================================================================
fo_base = 0x0054b000
va_base = 0xfffffff00754f000

# Routine layout (strictly non-overlapping):
fo_strat     = fo_base + 0x210  # 0x54b210, len 340 [0x210 .. 0x364]
va_strat     = va_base + 0x210  # 0xfffffff00754f210

fo_open      = fo_base + 0x380  # 0x54b380, len 8
va_open      = va_base + 0x380  # 0xfffffff00754f380

fo_close     = fo_base + 0x388  # 0x54b388, len 8
va_close     = va_base + 0x388  # 0xfffffff00754f388

fo_psize     = fo_base + 0x390  # 0x54b390, len 16
va_psize     = va_base + 0x390  # 0xfffffff00754f390

fo_ioctl     = fo_base + 0x3a0  # 0x54b3a0, len 76 [0x3a0 .. 0x3ec]
va_ioctl     = va_base + 0x3a0  # 0xfffffff00754f3a0

fo_ret0      = fo_base + 0x3f0  # 0x54b3f0, len 8
va_ret0      = va_base + 0x3f0  # 0xfffffff00754f3f0

fo_mountroot = fo_base + 0x400  # 0x54b400, len 624 [0x400 .. 0x670]
va_mountroot = va_base + 0x400  # 0xfffffff00754f400

fo_lookup    = fo_base + 0x6c0  # 0x54b6c0, len 348 [0x6c0 .. 0x81c]
va_lookup    = va_base + 0x6c0  # 0xfffffff00754f6c0

fo_getattr   = fo_base + 0x830  # 0x54b830, len 180 [0x830 .. 0x8e4]
va_getattr   = va_base + 0x830  # 0xfffffff00754f830

fo_read      = fo_base + 0x900  # 0x54b900, len 164 [0x900 .. 0x9a4]
va_read      = va_base + 0x900  # 0xfffffff00754f900

fo_pagein    = fo_base + 0x9c0  # 0x54b9c0, len 228 [0x9c0 .. 0xaa4]
va_pagein    = va_base + 0x9c0  # 0xfffffff00754f9c0

fo_root      = fo_base + 0xac0  # 0x54bac0, len 88  [0xac0 .. 0xb18]
va_root      = va_base + 0xac0  # 0xfffffff00754fac0

# =====================================================================
# 1. bdev_strategy @ va_strat
# =====================================================================
asm_strat = bld.Assembler(va_strat)
asm_strat.emit(bld.sub_sp_sp, 0x80)
asm_strat.emit(bld.stp, 27, 28, 31, 0x10)
asm_strat.emit(bld.stp, 25, 26, 31, 0x20)
asm_strat.emit(bld.stp, 23, 24, 31, 0x30)
asm_strat.emit(bld.stp, 21, 22, 31, 0x40)
asm_strat.emit(bld.stp, 19, 20, 31, 0x50)
asm_strat.emit(bld.stp, 29, 30, 31, 0x60)
asm_strat.emit(bld.add_reg_sp, 29, 0x60)
asm_strat.emit(bld.mov_reg, 19, 0) # x19 = bp

# Step A: Query buf fields
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad3d0)) # buf_flags
asm_strat.emit(bld.mov_reg, 23, 0) # x23 = flags

asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad350)) # buf_blkno
asm_strat.emit(bld.mov_reg, 21, 0) # x21 = blkno

asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad340)) # buf_count
asm_strat.emit(bld.mov_reg, 22, 0) # x22 = count

# Step B: Get disk object from OneiOSHostedDisk::disks[0]
asm_strat.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d8b000))
asm_strat.emit(bld.ldr_reg, 10, 8, 0x598) # x10 = OneiOSHostedDisk::disks[0]
asm_strat.emit(lambda pc, tgt: bld.cbz(10, pc, tgt), 'err_nodev')

# Step C: buf_map(bp, &vaddr)
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(bld.add_reg_sp, 1, 0x78)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ae0c4)) # buf_map
asm_strat.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'err_map')
asm_strat.emit(bld.ldr_reg, 24, 31, 0x78) # x24 = vaddr

# Step D: Bounce buffer from [disk + 0x98] -> [desc + 0xb8]
asm_strat.emit(bld.ldr_reg, 25, 10, 0x98) # x25 = desc
asm_strat.emit(lambda pc, tgt: bld.cbz(25, pc, tgt), 'err_nodev')
asm_strat.emit(bld.ldr_reg, 25, 25, 0xb8) # x25 = bounce buffer vaddr
asm_strat.emit(lambda pc, tgt: bld.cbz(25, pc, tgt), 'err_nodev')
asm_strat.emit(bld.mov_wimm, 28, 0x1000) # max_chunk = 4096 (0x1000)
asm_strat.emit(bld.mov_reg, 26, 31)     # transferred = 0

# Step E: Transfer loop
asm_strat.label('xfer_loop')
asm_strat.emit(bld.sub_reg_reg, 8, 22, 26) # remaining = count - transferred
asm_strat.emit(lambda pc, tgt: bld.cbz(8, pc, tgt), 'xfer_done')

# chunk = min(remaining, 4096)
asm_strat.emit(bld.cmp_reg, 8, 28)
asm_strat.emit(bld.csel_lo, 27, 8, 28) # x27 = chunk

# block = blkno + (transferred >> 9)
asm_strat.emit(bld.lsr_reg_imm, 8, 26, 9)
asm_strat.emit(bld.add_reg_reg, 2, 21, 8) # x2 = block

asm_strat.emit(lambda pc, tgt: bld.tbz(23, 0, pc, tgt), 'do_write')

# READ: OneiOSHostedDisk::transfer(disk, 0, block, chunk)
asm_strat.emit(bld.mov_reg, 0, 10)
asm_strat.emit(bld.mov_wimm, 1, 0) # type = 0
asm_strat.emit(bld.mov_wreg, 3, 27) # nbytes = chunk
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff007c0f3f4))
asm_strat.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'err_xfer')

# memcpy(vaddr + transferred, bounce, chunk)
asm_strat.emit(bld.add_reg_reg_uxtw, 0, 24, 26) # dst = vaddr + transferred
asm_strat.emit(bld.mov_reg, 1, 25) # src = bounce
asm_strat.emit(bld.mov_wreg, 2, 27) # len = chunk
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff007c6c970))
asm_strat.emit(lambda pc, tgt: bld.b(pc, tgt), 'xfer_next')

# WRITE: memcpy(bounce, vaddr + transferred, chunk)
asm_strat.label('do_write')
asm_strat.emit(bld.mov_reg, 0, 25) # dst = bounce
asm_strat.emit(bld.add_reg_reg_uxtw, 1, 24, 26) # src = vaddr + transferred
asm_strat.emit(bld.mov_wreg, 2, 27) # len = chunk
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff007c6c970))

# OneiOSHostedDisk::transfer(disk, 1, block, chunk)
asm_strat.emit(bld.mov_reg, 0, 10)
asm_strat.emit(bld.mov_wimm, 1, 1) # type = 1
asm_strat.emit(bld.mov_wreg, 3, 27) # nbytes = chunk
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff007c0f3f4))
asm_strat.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'err_xfer')

asm_strat.label('xfer_next')
asm_strat.emit(bld.add_reg_reg, 26, 26, 27)
asm_strat.emit(lambda pc, tgt: bld.b(pc, tgt), 'xfer_loop')

# Error handlers
asm_strat.label('err_map')
asm_strat.emit(bld.mov_wreg, 1, 0) # err from buf_map
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad390)) # buf_seterror
asm_strat.emit(lambda pc, tgt: bld.b(pc, tgt), 'finish')

asm_strat.label('err_nodev')
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(bld.mov_wimm, 1, 19) # ENODEV
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad390))
asm_strat.emit(lambda pc, tgt: bld.b(pc, tgt), 'finish')

asm_strat.label('err_eio')
asm_strat.label('err_xfer')
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(bld.mov_wimm, 1, 5) # EIO
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad390))
asm_strat.emit(lambda pc, tgt: bld.b(pc, tgt), 'finish')

# Finish
asm_strat.label('xfer_done')
asm_strat.label('finish')
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ae0d4)) # buf_unmap

asm_strat.emit(bld.sub_reg_reg, 1, 22, 26) # resid = count - transferred
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad448)) # buf_setresid

asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ae4f0)) # buf_biodone

# Epilogue
asm_strat.emit(bld.ldp, 29, 30, 31, 0x60)
asm_strat.emit(bld.ldp, 19, 20, 31, 0x50)
asm_strat.emit(bld.ldp, 21, 22, 31, 0x40)
asm_strat.emit(bld.ldp, 23, 24, 31, 0x30)
asm_strat.emit(bld.ldp, 25, 26, 31, 0x20)
asm_strat.emit(bld.ldp, 27, 28, 31, 0x10)
asm_strat.emit(bld.add_sp_sp, 0x80)
asm_strat.emit(bld.ret)

opcodes_strat = asm_strat.assemble()
raw_strategy = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_strat)
print(f"bdev_strategy: {len(raw_strategy)} bytes (from 0x{va_strat:x})")

# 2. bdev_open @ va_open
raw_open = struct.pack('<II', 0x52800000, 0xd65f03c0)

# 3. bdev_close @ va_close
raw_close = struct.pack('<II', 0x52800000, 0xd65f03c0)

# 4. bdev_psize @ va_psize
raw_psize = struct.pack('<IIII',
    0xd2858000, # mov x0, #0x2c00
    0xf2a01400, # movk x0, #0xa0, lsl #16 -> 0xa02c00 = 10,496,000 sectors
    0xd65f03c0, # ret
    0xd503201f  # nop
)

# 5. bdev_ioctl @ va_ioctl
asm_ioctl = bld.Assembler(va_ioctl)
asm_ioctl.emit(bld.mov_ximm, 8, 0x6418)
asm_ioctl.emit(bld.movk_ximm, 8, 0x4004, 16)
asm_ioctl.emit(bld.cmp_reg, 1, 8)
asm_ioctl.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'check_blkcount')
asm_ioctl.emit(bld.mov_wimm, 8, 512)
asm_ioctl.emit(bld.str_wreg, 8, 2, 0)
asm_ioctl.emit(bld.mov_wimm, 0, 0)
asm_ioctl.emit(bld.ret)

asm_ioctl.label('check_blkcount')
asm_ioctl.emit(bld.mov_ximm, 8, 0x6421)
asm_ioctl.emit(bld.movk_ximm, 8, 0x4008, 16)
asm_ioctl.emit(bld.cmp_reg, 1, 8)
asm_ioctl.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'default_ret0')
asm_ioctl.emit(bld.mov_ximm, 8, 0x2c00)
asm_ioctl.emit(bld.movk_ximm, 8, 0x00a0, 16)
asm_ioctl.emit(bld.str_reg, 8, 2, 0)
asm_ioctl.emit(bld.mov_wimm, 0, 0)
asm_ioctl.emit(bld.ret)

asm_ioctl.label('default_ret0')
asm_ioctl.emit(bld.mov_wimm, 0, 0)
asm_ioctl.emit(bld.ret)

opcodes_ioctl = asm_ioctl.assemble()
raw_ioctl = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_ioctl)
print(f"bdev_ioctl: {len(raw_ioctl)} bytes")

# 6. ret0_stub @ va_ret0
raw_ret0 = struct.pack('<II', 0x52800000, 0xd65f03c0)

# =====================================================================
# 7. apfs_mountroot @ va_mountroot
# =====================================================================
asm_mountroot = bld.Assembler(va_mountroot)
asm_mountroot.emit(bld.sub_sp_sp, 0xa0)
asm_mountroot.emit(bld.stp, 29, 30, 31, 0x90)
asm_mountroot.emit(bld.stp, 19, 20, 31, 0x80)
asm_mountroot.emit(bld.stp, 21, 22, 31, 0x70)
asm_mountroot.emit(bld.stp, 23, 24, 31, 0x60)
asm_mountroot.emit(bld.add_reg_sp, 29, 0x90)
asm_mountroot.emit(bld.mov_reg, 19, 0) # x19 = mp
asm_mountroot.emit(bld.mov_reg, 20, 1) # x20 = devvp
asm_mountroot.emit(bld.mov_reg, 21, 2) # x21 = ctx

# Step 1: Allocate custom_vnodeops (512 bytes) using kalloc_data(512, 0)
asm_mountroot.emit(bld.mov_ximm, 0, 512)
asm_mountroot.emit(bld.mov_ximm, 1, 0) # Z_WAITOK = 0
asm_mountroot.emit(lambda pc: bld.bl(pc, 0xfffffff00732d8b4)) # kalloc_data(512, 0)
asm_mountroot.emit(lambda pc, tgt: bld.cbz(0, pc, tgt), 'mount_fail')
asm_mountroot.emit(bld.mov_reg, 23, 0) # x23 = custom_vnodeops
asm_mountroot.emit(bld.mov_reg, 10, 0) # x10 = custom_vnodeops

# Save to g_custom_vnodeops at 0xfffffff007d5da28
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d5d000))
asm_mountroot.emit(bld.str_reg, 23, 8, 0xa28)

# Copy 64 entries from *devfs_vnodeop_p to custom_vnodeops
asm_mountroot.emit(bld.mov_reg, 0, 23)           # dst = custom_vnodeops
asm_mountroot.emit(lambda pc: bld.adrp(1, pc, 0xfffffff007d50000))
asm_mountroot.emit(bld.ldr_reg, 1, 1, 0x380)     # src = *devfs_vnodeop_p
asm_mountroot.emit(bld.mov_ximm, 2, 64)          # count = 64

asm_mountroot.label('copy_ops_loop')
asm_mountroot.emit(bld.ldr_reg, 3, 1, 0)
asm_mountroot.emit(bld.str_reg, 3, 0, 0)
asm_mountroot.emit(bld.add_reg_imm, 0, 0, 8)
asm_mountroot.emit(bld.add_reg_imm, 1, 1, 8)
asm_mountroot.emit(bld.subs_reg_imm, 2, 2, 1)
asm_mountroot.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'copy_ops_loop')

# Overwrite slots in custom_vnodeops (plain slid pointers, no PAC on ARMv8.2-A / Kryo 470):
# ret0_stub @ va_ret0
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, va_ret0 & ~0xfff))
asm_mountroot.emit(bld.add_reg_imm, 8, 8, va_ret0 & 0xfff)

asm_mountroot.emit(bld.str_reg, 8, 10, 7*8)  # vnop_open
asm_mountroot.emit(bld.str_reg, 8, 10, 9*8)  # vnop_close
asm_mountroot.emit(bld.str_reg, 8, 10, 10*8) # vnop_access
asm_mountroot.emit(bld.str_reg, 8, 10, 22*8) # vnop_mmap_check
asm_mountroot.emit(bld.str_reg, 8, 10, 23*8) # vnop_mmap
asm_mountroot.emit(bld.str_reg, 8, 10, 24*8) # vnop_mnomap
asm_mountroot.emit(bld.str_reg, 8, 10, 32*8) # vnop_mkdir
asm_mountroot.emit(bld.str_reg, 8, 10, 33*8) # vnop_compound_mkdir

# Slot 3 (vnop_lookup) = custom_lookup @ va_lookup
asm_mountroot.emit(lambda pc: bld.adrp(9, pc, va_lookup & ~0xfff))
asm_mountroot.emit(bld.add_reg_imm, 9, 9, va_lookup & 0xfff)
asm_mountroot.emit(bld.str_reg, 9, 10, 3*8)

# Slot 11 (vnop_getattr) = custom_getattr @ va_getattr
asm_mountroot.emit(lambda pc: bld.adrp(9, pc, va_getattr & ~0xfff))
asm_mountroot.emit(bld.add_reg_imm, 9, 9, va_getattr & 0xfff)
asm_mountroot.emit(bld.str_reg, 9, 10, 11*8)

# Slot 13 (vnop_read) = custom_read @ va_read
asm_mountroot.emit(lambda pc: bld.adrp(9, pc, va_read & ~0xfff))
asm_mountroot.emit(bld.add_reg_imm, 9, 9, va_read & 0xfff)
asm_mountroot.emit(bld.str_reg, 9, 10, 13*8)

# Slot 46 (vnop_pagein) = custom_pagein @ va_pagein
asm_mountroot.emit(lambda pc: bld.adrp(9, pc, va_pagein & ~0xfff))
asm_mountroot.emit(bld.add_reg_imm, 9, 9, va_pagein & 0xfff)
asm_mountroot.emit(bld.str_reg, 9, 10, 46*8)

# Step 1.5: Allocate custom_vfsops (96 bytes) and setup vfs_root
asm_mountroot.emit(bld.mov_ximm, 0, 96)
asm_mountroot.emit(bld.mov_ximm, 1, 0)
asm_mountroot.emit(lambda pc: bld.bl(pc, 0xfffffff00732d8b4)) # kalloc_data(96, 0)
asm_mountroot.emit(lambda pc, tgt: bld.cbz(0, pc, tgt), 'mount_fail')
asm_mountroot.emit(bld.mov_reg, 24, 0) # x24 = custom_vfsops

# Copy 12 entries from mp->mnt_op (at [mp, #0x28])
asm_mountroot.emit(bld.mov_reg, 0, 24)
asm_mountroot.emit(bld.ldr_reg, 1, 19, 0x28) # src = mp->mnt_op (routefs_vfsops)
asm_mountroot.emit(bld.mov_ximm, 2, 12)

asm_mountroot.label('copy_vfsops_loop')
asm_mountroot.emit(bld.ldr_reg, 3, 1, 0)
asm_mountroot.emit(bld.str_reg, 3, 0, 0)
asm_mountroot.emit(bld.add_reg_imm, 0, 0, 8)
asm_mountroot.emit(bld.add_reg_imm, 1, 1, 8)
asm_mountroot.emit(bld.subs_reg_imm, 2, 2, 1)
asm_mountroot.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'copy_vfsops_loop')

# Overwrite slot 3 (vfs_root) with apfs_root
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, va_root & ~0xfff))
asm_mountroot.emit(bld.add_reg_imm, 8, 8, va_root & 0xfff) # apfs_root @ va_root
asm_mountroot.emit(bld.str_reg, 8, 24, 3*8)                # custom_vfsops[3] = apfs_root

# Update mp->mnt_op = custom_vfsops
asm_mountroot.emit(bld.str_reg, 24, 19, 0x28)

# Step 2: Create rootvp (VDIR)
for off in range(0, 0x60, 0x10):
    asm_mountroot.emit(bld.stp, 31, 31, 31, off)

asm_mountroot.emit(bld.str_reg, 19, 31, 0x00) # params.vnfs_mp = mp
asm_mountroot.emit(bld.mov_wimm, 8, 2)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x08)  # params.vnfs_vtype = 2 (VDIR)
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff0070a6000))
asm_mountroot.emit(bld.add_reg_imm, 8, 8, 0xa8f) # params.vnfs_str = '/'
asm_mountroot.emit(bld.str_reg, 8, 31, 0x10)
asm_mountroot.emit(bld.mov_wimm, 8, 1)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x20)  # params.vnfs_fsnode = 1
asm_mountroot.emit(bld.str_reg, 23, 31, 0x28) # params.vnfs_vops = custom_vnodeops (x23)
asm_mountroot.emit(bld.mov_wimm, 8, 1)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x30)  # params.vnfs_markroot = 1
asm_mountroot.emit(bld.mov_ximm, 8, 4096)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x40)  # params.vnfs_filesize = 4096

asm_mountroot.emit(bld.mov_wimm, 0, 0)
asm_mountroot.emit(bld.mov_wimm, 1, 0x58)
asm_mountroot.emit(bld.add_reg_sp, 2, 0x00)
asm_mountroot.emit(bld.add_reg_sp, 3, 0x58)
asm_mountroot.emit(bld.mov_wimm, 4, 2)
asm_mountroot.emit(lambda pc: bld.bl(pc, 0xfffffff0075d44e0)) # vnode_create_internal
asm_mountroot.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'mount_fail')

asm_mountroot.emit(bld.ldr_reg, 22, 31, 0x58) # x22 = rootvp
asm_mountroot.emit(bld.str_reg, 22, 19, 0x8f8) # mp->mnt_data = rootvp

# Save rootdir_vp to g_rootdir_vp at 0xfffffff007d5da30
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d5d000))
asm_mountroot.emit(bld.str_reg, 22, 8, 0xa30) # g_rootdir_vp = rootvp

# Store rootvp to _rootvnode at 0xfffffff007d454f0
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d45000))
asm_mountroot.emit(bld.str_reg, 22, 8, 0x4f0) # _rootvnode = rootvp!

# Disable CS enforcement (cs_enforcement_flags & cs_enforcement_panic = 0)
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff0071e2000))
asm_mountroot.emit(bld.str_wreg, 31, 8, 0xbb8)
asm_mountroot.emit(bld.str_wreg, 31, 8, 0xbbc)

# Step 3: Create launchd_vp (VREG)
for off in range(0, 0x60, 0x10):
    asm_mountroot.emit(bld.stp, 31, 31, 31, off)
asm_mountroot.emit(bld.str_reg, 19, 31, 0x00) # params.vnfs_mp = mp
asm_mountroot.emit(bld.mov_wimm, 8, 1)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x08) # params.vnfs_vtype = 1 (VREG)
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff0070e4000))
asm_mountroot.emit(bld.add_reg_imm, 8, 8, 0x815) # params.vnfs_str = 'launchd'
asm_mountroot.emit(bld.str_reg, 8, 31, 0x10)
asm_mountroot.emit(bld.str_reg, 22, 31, 0x18) # params.vnfs_dvp = rootvp
asm_mountroot.emit(bld.mov_wimm, 8, 2)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x20) # params.vnfs_fsnode = 2
asm_mountroot.emit(bld.str_reg, 23, 31, 0x28) # params.vnfs_vops = custom_vnodeops
asm_mountroot.emit(bld.mov_ximm, 8, 0x43a0)
asm_mountroot.emit(bld.movk_ximm, 8, 0x0008, 16)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x40) # params.vnfs_filesize = 541600 (ubc_info_init)

asm_mountroot.emit(bld.mov_wimm, 0, 0)
asm_mountroot.emit(bld.mov_wimm, 1, 0x58)
asm_mountroot.emit(bld.add_reg_sp, 2, 0x00)
asm_mountroot.emit(bld.add_reg_sp, 3, 0x58)
asm_mountroot.emit(bld.mov_wimm, 4, 2)
asm_mountroot.emit(lambda pc: bld.bl(pc, 0xfffffff0075d44e0)) # vnode_create_internal
asm_mountroot.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'mount_fail')

asm_mountroot.emit(bld.ldr_reg, 8, 31, 0x58) # x8 = launchd_vp
asm_mountroot.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007d5d000))
asm_mountroot.emit(bld.str_reg, 8, 9, 0xa08) # g_launchd_vp = vp

# Step 4: Create dyld_vp (VREG)
for off in range(0, 0x60, 0x10):
    asm_mountroot.emit(bld.stp, 31, 31, 31, off)
asm_mountroot.emit(bld.str_reg, 19, 31, 0x00) # params.vnfs_mp = mp
asm_mountroot.emit(bld.mov_wimm, 8, 1)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x08) # params.vnfs_vtype = 1 (VREG)
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007088000))
asm_mountroot.emit(bld.add_reg_imm, 8, 8, 0xb90) # params.vnfs_str = 'dyld'
asm_mountroot.emit(bld.str_reg, 8, 31, 0x10)
asm_mountroot.emit(bld.str_reg, 22, 31, 0x18) # params.vnfs_dvp = rootvp
asm_mountroot.emit(bld.mov_wimm, 8, 3)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x20) # params.vnfs_fsnode = 3
asm_mountroot.emit(bld.str_reg, 23, 31, 0x28) # params.vnfs_vops = custom_vnodeops
asm_mountroot.emit(bld.mov_ximm, 8, 0x1520)
asm_mountroot.emit(bld.movk_ximm, 8, 0x000e, 16)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x40) # params.vnfs_filesize = 922912

asm_mountroot.emit(bld.mov_wimm, 0, 0)
asm_mountroot.emit(bld.mov_wimm, 1, 0x58)
asm_mountroot.emit(bld.add_reg_sp, 2, 0x00)
asm_mountroot.emit(bld.add_reg_sp, 3, 0x58)
asm_mountroot.emit(bld.mov_wimm, 4, 2)
asm_mountroot.emit(lambda pc: bld.bl(pc, 0xfffffff0075d44e0)) # vnode_create_internal
asm_mountroot.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'mount_fail')

asm_mountroot.emit(bld.ldr_reg, 8, 31, 0x58) # x8 = dyld_vp
asm_mountroot.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007d5d000))
asm_mountroot.emit(bld.str_reg, 8, 9, 0xa38) # g_dyld_vp = vp

# Success: return 0
asm_mountroot.emit(bld.mov_wimm, 0, 0)
asm_mountroot.emit(lambda pc, tgt: bld.b(pc, tgt), 'mount_ret')

asm_mountroot.label('mount_fail')
asm_mountroot.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'mount_ret')
asm_mountroot.emit(bld.mov_wimm, 0, 19) # ENODEV if w0 was 0

asm_mountroot.label('mount_ret')
asm_mountroot.emit(bld.ldp, 23, 24, 31, 0x60)
asm_mountroot.emit(bld.ldp, 21, 22, 31, 0x70)
asm_mountroot.emit(bld.ldp, 19, 20, 31, 0x80)
asm_mountroot.emit(bld.ldp, 29, 30, 31, 0x90)
asm_mountroot.emit(bld.add_sp_sp, 0xa0)
asm_mountroot.emit(bld.ret)

opcodes_mountroot = asm_mountroot.assemble()
raw_mountroot = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_mountroot)
print(f"apfs_mountroot: {len(raw_mountroot)} bytes (ends at 0x{va_mountroot + len(raw_mountroot):x})")

# =====================================================================
# 8. apfs_root @ va_root
# =====================================================================
asm_root = bld.Assembler(va_root)
asm_root.emit(bld.ldr_reg, 8, 0, 0x8f8) # mp->mnt_data
asm_root.emit(lambda pc, tgt: bld.cbnz(8, pc, tgt), 'has_vp')
asm_root.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007d5d000))
asm_root.emit(bld.ldr_reg, 8, 9, 0xa30) # g_rootdir_vp

asm_root.label('has_vp')
asm_root.emit(lambda pc, tgt: bld.cbz(8, pc, tgt), 'no_vp')
asm_root.emit(bld.sub_sp_sp, 0x20)
asm_root.emit(bld.stp, 29, 30, 31, 0)
asm_root.emit(bld.stp, 19, 20, 31, 0x10)
asm_root.emit(bld.add_reg_sp, 29, 0)
asm_root.emit(bld.mov_reg, 19, 1) # x19 = vpp
asm_root.emit(bld.mov_reg, 20, 8) # x20 = rootvp
asm_root.emit(bld.mov_reg, 0, 8)
asm_root.emit(lambda pc: bld.bl(pc, 0xfffffff0075d3c70)) # vnode_get
asm_root.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'out_root')
asm_root.emit(bld.str_reg, 20, 19, 0) # *vpp = rootvp
asm_root.emit(bld.mov_wimm, 0, 0)

asm_root.label('out_root')
asm_root.emit(bld.ldp, 19, 20, 31, 0x10)
asm_root.emit(bld.ldp, 29, 30, 31, 0)
asm_root.emit(bld.add_sp_sp, 0x20)
asm_root.emit(bld.ret)

asm_root.label('no_vp')
asm_root.emit(bld.mov_wimm, 0, 19) # ENODEV
asm_root.emit(bld.ret)

opcodes_root = asm_root.assemble()
raw_root = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_root)
print(f"apfs_root: {len(raw_root)} bytes (ends at 0x{va_root + len(raw_root):x})")

# =====================================================================
# 9. custom_lookup @ va_lookup
# =====================================================================
asm_lookup = bld.Assembler(va_lookup)
asm_lookup.emit(bld.sub_sp_sp, 0x50)
asm_lookup.emit(bld.stp, 29, 30, 31, 0x40)
asm_lookup.emit(bld.stp, 19, 20, 31, 0x30)
asm_lookup.emit(bld.stp, 21, 22, 31, 0x20)
asm_lookup.emit(bld.stp, 23, 24, 31, 0x10)
asm_lookup.emit(bld.add_reg_sp, 29, 0x40)

asm_lookup.emit(bld.mov_reg, 19, 0)       # x19 = ap
asm_lookup.emit(bld.ldr_reg, 20, 19, 0x10) # x20 = vpp
asm_lookup.emit(bld.str_reg, 31, 20, 0)    # *vpp = NULL
asm_lookup.emit(bld.ldr_reg, 21, 19, 0x18) # x21 = cnp
asm_lookup.emit(bld.ldrsw_reg, 22, 21, 0x30) # x22 = cnp->cn_namelen
asm_lookup.emit(bld.ldr_reg, 23, 21, 0x28)   # x23 = cnp->cn_nameptr

# Check exact name "launchd" (len == 7)
asm_lookup.emit(bld.cmp_ximm, 22, 7)
asm_lookup.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'check_dyld')

asm_lookup.emit(bld.ldr_reg, 8, 23, 0)
asm_lookup.emit(bld.mov_ximm, 9, 0xffff)
asm_lookup.emit(bld.movk_ximm, 9, 0xffff, 16)
asm_lookup.emit(bld.movk_ximm, 9, 0xffff, 32)
asm_lookup.emit(bld.movk_ximm, 9, 0x00ff, 48)
asm_lookup.emit(bld.and_reg_reg, 8, 8, 9)

# Little-endian "launchd": 0x006468636e75616c
asm_lookup.emit(bld.mov_ximm, 10, 0x616c)
asm_lookup.emit(bld.movk_ximm, 10, 0x6e75, 16)
asm_lookup.emit(bld.movk_ximm, 10, 0x6863, 32)
asm_lookup.emit(bld.movk_ximm, 10, 0x0064, 48)
asm_lookup.emit(bld.cmp_xreg, 8, 10)
asm_lookup.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'check_create')

# Match! Return launchd_vp
asm_lookup.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d5d000))
asm_lookup.emit(bld.ldr_reg, 0, 8, 0xa08) # x0 = launchd_vp
asm_lookup.emit(bld.mov_reg, 24, 0)       # x24 = launchd_vp
asm_lookup.emit(lambda pc: bld.bl(pc, 0xfffffff0075d3c70)) # vnode_get
asm_lookup.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'out_err')
asm_lookup.emit(bld.str_reg, 24, 20, 0)   # *vpp = launchd_vp
asm_lookup.emit(bld.mov_wimm, 0, 0)
asm_lookup.emit(lambda pc, tgt: bld.b(pc, tgt), 'out_lookup')

# Check exact name "dyld" (len == 4)
asm_lookup.label('check_dyld')
asm_lookup.emit(bld.cmp_ximm, 22, 4)
asm_lookup.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'check_dev_launchd')

asm_lookup.emit(bld.ldr_wreg, 8, 23, 0)
asm_lookup.emit(bld.mov_wimm, 9, 0x7964)
asm_lookup.emit(bld.movk_wimm, 9, 0x646c, 16) # 0x646c7964
asm_lookup.emit(bld.cmp_reg, 8, 9)
asm_lookup.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'check_create')

# Match! Return dyld_vp
asm_lookup.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d5d000))
asm_lookup.emit(bld.ldr_reg, 0, 8, 0xa38) # x0 = dyld_vp
asm_lookup.emit(bld.mov_reg, 24, 0)       # x24 = dyld_vp
asm_lookup.emit(lambda pc: bld.bl(pc, 0xfffffff0075d3c70)) # vnode_get
asm_lookup.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'out_err')
asm_lookup.emit(bld.str_reg, 24, 20, 0)   # *vpp = dyld_vp
asm_lookup.emit(bld.mov_wimm, 0, 0)
asm_lookup.emit(lambda pc, tgt: bld.b(pc, tgt), 'out_lookup')

# Check prefix "launchd" with len > 7 (e.g. launchd.development)
asm_lookup.label('check_dev_launchd')
asm_lookup.emit(bld.cmp_ximm, 22, 7)
asm_lookup.emit(lambda pc, tgt: bld.b_le(pc, tgt), 'check_create')
asm_lookup.emit(bld.ldr_reg, 8, 23, 0)
asm_lookup.emit(bld.mov_ximm, 9, 0xffff)
asm_lookup.emit(bld.movk_ximm, 9, 0xffff, 16)
asm_lookup.emit(bld.movk_ximm, 9, 0xffff, 32)
asm_lookup.emit(bld.movk_ximm, 9, 0x00ff, 48)
asm_lookup.emit(bld.and_reg_reg, 8, 8, 9)
asm_lookup.emit(bld.mov_ximm, 10, 0x616c)
asm_lookup.emit(bld.movk_ximm, 10, 0x6e75, 16)
asm_lookup.emit(bld.movk_ximm, 10, 0x6863, 32)
asm_lookup.emit(bld.movk_ximm, 10, 0x0064, 48)
asm_lookup.emit(bld.cmp_xreg, 8, 10)
asm_lookup.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'check_create')
# It is launchd.development -> return ENOENT (2)
asm_lookup.emit(bld.mov_wimm, 0, 2)
asm_lookup.emit(lambda pc, tgt: bld.b(pc, tgt), 'out_lookup')

# Check CREATE:
asm_lookup.label('check_create')
asm_lookup.emit(bld.ldr_wreg, 8, 21, 0x00) # cnp->cn_nameiop
asm_lookup.emit(bld.cmp_wimm, 8, 1)        # CREATE
asm_lookup.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'return_rootvp')
asm_lookup.emit(bld.ldr_wreg, 8, 21, 0x04) # cnp->cn_flags
asm_lookup.emit(lambda pc, tgt: bld.tbnz(8, 15, pc, tgt), 'return_null') # ISLASTCN

asm_lookup.label('return_rootvp')
asm_lookup.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d5d000))
asm_lookup.emit(bld.ldr_reg, 0, 8, 0xa30) # x0 = rootvp (g_rootdir_vp)
asm_lookup.emit(bld.mov_reg, 24, 0)       # x24 = rootvp
asm_lookup.emit(lambda pc: bld.bl(pc, 0xfffffff0075d3c70)) # vnode_get
asm_lookup.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'out_err')
asm_lookup.emit(bld.str_reg, 24, 20, 0)   # *vpp = rootvp
asm_lookup.emit(bld.mov_wimm, 0, 0)
asm_lookup.emit(lambda pc, tgt: bld.b(pc, tgt), 'out_lookup')

asm_lookup.label('return_null')
asm_lookup.emit(bld.str_reg, 31, 20, 0)   # *vpp = NULL
asm_lookup.emit(bld.mov_wimm, 0, 0)
asm_lookup.emit(lambda pc, tgt: bld.b(pc, tgt), 'out_lookup')

asm_lookup.label('out_err')
# w0 contains error code from vnode_get

asm_lookup.label('out_lookup')
asm_lookup.emit(bld.ldp, 23, 24, 31, 0x10)
asm_lookup.emit(bld.ldp, 21, 22, 31, 0x20)
asm_lookup.emit(bld.ldp, 19, 20, 31, 0x30)
asm_lookup.emit(bld.ldp, 29, 30, 31, 0x40)
asm_lookup.emit(bld.add_sp_sp, 0x50)
asm_lookup.emit(bld.ret)

opcodes_lookup = asm_lookup.assemble()
raw_lookup = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_lookup)
print(f"custom_lookup: {len(raw_lookup)} bytes (ends at 0x{va_lookup + len(raw_lookup):x})")

# =====================================================================
# 10. custom_getattr @ va_getattr
# =====================================================================
asm_getattr = bld.Assembler(va_getattr)
asm_getattr.emit(bld.ldr_reg, 1, 0, 0x10) # x1 = vap
asm_getattr.emit(bld.ldr_reg, 2, 0, 0x08) # x2 = vp

# va_supported = -1
asm_getattr.emit(bld.mov_ximm, 8, 0xffff)
asm_getattr.emit(bld.movk_ximm, 8, 0xffff, 16)
asm_getattr.emit(bld.movk_ximm, 8, 0xffff, 32)
asm_getattr.emit(bld.movk_ximm, 8, 0xffff, 48)
asm_getattr.emit(bld.str_reg, 8, 1, 0x00)

# va_nlink = 1
asm_getattr.emit(bld.mov_wimm, 8, 1)
asm_getattr.emit(bld.str_reg, 8, 1, 0x18)

# uid = 0, gid = 0
asm_getattr.emit(bld.str_wreg, 31, 1, 0x44)
asm_getattr.emit(bld.str_wreg, 31, 1, 0x48)

# Check if vp == launchd_vp
asm_getattr.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007d5d000))
asm_getattr.emit(bld.ldr_reg, 9, 9, 0xa08) # x9 = launchd_vp
asm_getattr.emit(bld.cmp_xreg, 2, 9)
asm_getattr.emit(lambda pc, tgt: bld.b_eq(pc, tgt), 'is_launchd')

# Check if vp == dyld_vp
asm_getattr.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007d5d000))
asm_getattr.emit(bld.ldr_reg, 9, 9, 0xa38) # x9 = dyld_vp
asm_getattr.emit(bld.cmp_xreg, 2, 9)
asm_getattr.emit(lambda pc, tgt: bld.b_eq(pc, tgt), 'is_dyld')

# Directory (rootvp):
asm_getattr.emit(bld.mov_wimm, 8, 2)       # va_type = 2 (VDIR)
asm_getattr.emit(bld.str_wreg, 8, 1, 0xe0)
asm_getattr.emit(bld.mov_wimm, 8, 0x1ed)   # va_mode = 0755
asm_getattr.emit(bld.strh_wreg, 8, 1, 0x4c)
asm_getattr.emit(bld.mov_ximm, 8, 4096)    # va_data_size = 4096
asm_getattr.emit(bld.str_reg, 8, 1, 0x30)
asm_getattr.emit(bld.mov_wimm, 0, 0)
asm_getattr.emit(bld.ret)

# File (launchd_vp):
asm_getattr.label('is_launchd')
asm_getattr.emit(bld.mov_wimm, 8, 1)       # va_type = 1 (VREG)
asm_getattr.emit(bld.str_wreg, 8, 1, 0xe0)
asm_getattr.emit(bld.mov_wimm, 8, 0x1ed)   # va_mode = 0755
asm_getattr.emit(bld.strh_wreg, 8, 1, 0x4c)
# va_data_size = 541600 (0x843a0)
asm_getattr.emit(bld.mov_ximm, 8, 0x43a0)
asm_getattr.emit(bld.movk_ximm, 8, 0x0008, 16)
asm_getattr.emit(bld.str_reg, 8, 1, 0x30)
asm_getattr.emit(bld.mov_wimm, 0, 0)
asm_getattr.emit(bld.ret)

# File (dyld_vp):
asm_getattr.label('is_dyld')
asm_getattr.emit(bld.mov_wimm, 8, 1)       # va_type = 1 (VREG)
asm_getattr.emit(bld.str_wreg, 8, 1, 0xe0)
asm_getattr.emit(bld.mov_wimm, 8, 0x1ed)   # va_mode = 0755
asm_getattr.emit(bld.strh_wreg, 8, 1, 0x4c)
# va_data_size = 922912 (0xe1520)
asm_getattr.emit(bld.mov_ximm, 8, 0x1520)
asm_getattr.emit(bld.movk_ximm, 8, 0x000e, 16)
asm_getattr.emit(bld.str_reg, 8, 1, 0x30)
asm_getattr.emit(bld.mov_wimm, 0, 0)
asm_getattr.emit(bld.ret)

opcodes_getattr = asm_getattr.assemble()
raw_getattr = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_getattr)
print(f"custom_getattr: {len(raw_getattr)} bytes (ends at 0x{va_getattr + len(raw_getattr):x})")

# =====================================================================
# 11. custom_read @ va_read
# =====================================================================
asm_read = bld.Assembler(va_read)
asm_read.emit(bld.sub_sp_sp, 0x40)
asm_read.emit(bld.stp, 29, 30, 31, 0x30)
asm_read.emit(bld.stp, 19, 20, 31, 0x20)
asm_read.emit(bld.stp, 21, 22, 31, 0x10)
asm_read.emit(bld.add_reg_sp, 29, 0x30)

asm_read.emit(bld.ldr_reg, 19, 0, 0x10) # x19 = uio
asm_read.emit(bld.ldr_reg, 22, 0, 0x08) # x22 = vp (callee-saved, preserved across bl)

asm_read.emit(bld.mov_reg, 0, 19)
asm_read.emit(lambda pc: bld.bl(pc, 0xfffffff0078c1ef4)) # uio_offset
asm_read.emit(bld.mov_reg, 20, 0) # x20 = offset

asm_read.emit(bld.mov_reg, 0, 19)
asm_read.emit(lambda pc: bld.bl(pc, 0xfffffff0078c17b4)) # uio_resid
asm_read.emit(bld.mov_reg, 21, 0) # x21 = resid

# Check if vp == dyld_vp
asm_read.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007d5d000))
asm_read.emit(bld.ldr_reg, 9, 9, 0xa38) # x9 = dyld_vp
asm_read.emit(bld.cmp_xreg, 22, 9)
asm_read.emit(lambda pc, tgt: bld.b_eq(pc, tgt), 'is_dyld_read')

# launchd:
# file_size = 541600 (0x843a0)
asm_read.emit(bld.mov_ximm, 8, 0x43a0)
asm_read.emit(bld.movk_ximm, 8, 0x0008, 16)
asm_read.emit(lambda pc: bld.adrp(0, pc, 0xfffffff00899c000))
asm_read.emit(lambda pc, tgt: bld.b(pc, tgt), 'read_common')

# dyld:
# file_size = 922912 (0xe1520)
asm_read.label('is_dyld_read')
asm_read.emit(bld.mov_ximm, 8, 0x1520)
asm_read.emit(bld.movk_ximm, 8, 0x000e, 16)
asm_read.emit(lambda pc: bld.adrp(0, pc, 0xfffffff008a24000))

# Common read logic:
# x8 = file_size, x0 = payload_base, x20 = offset, x21 = resid, x19 = uio
asm_read.label('read_common')
# If offset >= file_size or resid == 0 -> EOF
asm_read.emit(bld.cmp_xreg, 20, 8)
asm_read.emit(lambda pc, tgt: bld.b_hs(pc, tgt), 'read_eof')
asm_read.emit(lambda pc, tgt: bld.cbz(21, pc, tgt), 'read_eof')

# count = min(resid, file_size - offset)
asm_read.emit(bld.sub_reg_reg_64, 22, 8, 20)
asm_read.emit(bld.cmp_xreg, 21, 22)
asm_read.emit(bld.csel_lo, 22, 21, 22)

# uiomove(payload_base + offset, count, uio)
asm_read.emit(bld.add_reg_reg, 0, 0, 20) # src = payload_base + offset
asm_read.emit(bld.mov_reg, 1, 22)        # count
asm_read.emit(bld.mov_reg, 2, 19)        # uio
asm_read.emit(lambda pc: bld.bl(pc, 0xfffffff0078c0678)) # uiomove
asm_read.emit(lambda pc, tgt: bld.b(pc, tgt), 'read_out')

asm_read.label('read_eof')
asm_read.emit(bld.mov_wimm, 0, 0)

asm_read.label('read_out')
asm_read.emit(bld.ldp, 21, 22, 31, 0x10)
asm_read.emit(bld.ldp, 19, 20, 31, 0x20)
asm_read.emit(bld.ldp, 29, 30, 31, 0x30)
asm_read.emit(bld.add_sp_sp, 0x40)
asm_read.emit(bld.ret)

opcodes_read = asm_read.assemble()
raw_read = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_read)
print(f"custom_read: {len(raw_read)} bytes (ends at 0x{va_read + len(raw_read):x})")

# =====================================================================
# 12. custom_pagein @ va_pagein
# =====================================================================
asm_pagein = bld.Assembler(va_pagein)
asm_pagein.emit(bld.sub_sp_sp, 0x60)
asm_pagein.emit(bld.stp, 29, 30, 31, 0x50)
asm_pagein.emit(bld.stp, 19, 20, 31, 0x40)
asm_pagein.emit(bld.stp, 21, 22, 31, 0x30)
asm_pagein.emit(bld.stp, 23, 24, 31, 0x20)
asm_pagein.emit(bld.add_reg_sp, 29, 0x50)

asm_pagein.emit(bld.mov_reg, 19, 0)         # x19 = ap
asm_pagein.emit(bld.ldr_reg, 20, 19, 0x10)  # x20 = upl
asm_pagein.emit(bld.ldr_wreg, 21, 19, 0x18) # w21 = pl_offset
asm_pagein.emit(bld.ldr_reg, 22, 19, 0x20)  # x22 = f_offset
asm_pagein.emit(bld.ldr_reg, 23, 19, 0x28)  # x23 = size

# ubc_upl_map(upl, &dst_addr)
asm_pagein.emit(bld.mov_reg, 0, 20)
asm_pagein.emit(bld.add_reg_sp, 1, 0x18)
asm_pagein.emit(lambda pc: bld.bl(pc, 0xfffffff00790d010))
asm_pagein.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'pagein_out')

asm_pagein.emit(bld.ldr_reg, 24, 31, 0x18) # x24 = dst_addr
asm_pagein.emit(bld.add_reg_reg_uxtw, 24, 24, 21) # dst = dst_addr + pl_offset

# Check if vp == dyld_vp
asm_pagein.emit(bld.ldr_reg, 8, 19, 0x08) # x8 = vp
asm_pagein.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007d5d000))
asm_pagein.emit(bld.ldr_reg, 9, 9, 0xa38) # x9 = dyld_vp
asm_pagein.emit(bld.cmp_xreg, 8, 9)
asm_pagein.emit(lambda pc, tgt: bld.b_eq(pc, tgt), 'dyld_pagein_setup')

# launchd:
asm_pagein.emit(bld.mov_ximm, 8, 0x43a0)
asm_pagein.emit(bld.movk_ximm, 8, 0x0008, 16) # file_size = 541600
asm_pagein.emit(lambda pc: bld.adrp(1, pc, 0xfffffff00899c000))
asm_pagein.emit(lambda pc, tgt: bld.b(pc, tgt), 'pagein_copy_common')

# dyld:
asm_pagein.label('dyld_pagein_setup')
asm_pagein.emit(bld.mov_ximm, 8, 0x1520)
asm_pagein.emit(bld.movk_ximm, 8, 0x000e, 16) # file_size = 922912
asm_pagein.emit(lambda pc: bld.adrp(1, pc, 0xfffffff008a24000))

# pagein_copy_common:
# x8 = file_size, x1 = payload_base
asm_pagein.label('pagein_copy_common')
# to_copy = (f_offset < file_size) ? min(size, file_size - f_offset) : 0
asm_pagein.emit(bld.mov_ximm, 2, 0)
asm_pagein.emit(bld.cmp_xreg, 22, 8)
asm_pagein.emit(lambda pc, tgt: bld.b_hs(pc, tgt), 'do_zero')
asm_pagein.emit(bld.sub_reg_reg_64, 2, 8, 22)
asm_pagein.emit(bld.cmp_xreg, 23, 2)
asm_pagein.emit(bld.csel_lo, 2, 23, 2)
asm_pagein.emit(lambda pc, tgt: bld.cbz(2, pc, tgt), 'do_zero')

# memcpy(dst, payload_base + f_offset, to_copy)
asm_pagein.emit(bld.mov_reg, 0, 24)
asm_pagein.emit(bld.add_reg_reg, 1, 1, 22) # src = payload_base + f_offset
asm_pagein.emit(lambda pc: bld.bl(pc, 0xfffffff007c6c970)) # memmove

# bzero(dst + to_copy, size - to_copy)
asm_pagein.label('do_zero')
asm_pagein.emit(bld.sub_reg_reg_64, 1, 23, 2)
asm_pagein.emit(lambda pc, tgt: bld.cbz(1, pc, tgt), 'do_unmap')
asm_pagein.emit(bld.add_reg_reg, 0, 24, 2)
asm_pagein.emit(lambda pc: bld.bl(pc, 0xfffffff007c6cb20)) # bzero

asm_pagein.label('do_unmap')
# ubc_upl_unmap(upl)
asm_pagein.emit(bld.mov_reg, 0, 20)
asm_pagein.emit(lambda pc: bld.bl(pc, 0xfffffff00790d04c))

# ubc_upl_commit_range(upl, pl_offset, size, 0xc)
asm_pagein.emit(bld.mov_reg, 0, 20)
asm_pagein.emit(bld.mov_wreg, 1, 21)
asm_pagein.emit(bld.mov_reg, 2, 23)
asm_pagein.emit(bld.mov_wimm, 3, 0xc)
asm_pagein.emit(lambda pc: bld.bl(pc, 0xfffffff00790d0d0))

asm_pagein.emit(bld.mov_wimm, 0, 0)

asm_pagein.label('pagein_out')
asm_pagein.emit(bld.ldp, 23, 24, 31, 0x20)
asm_pagein.emit(bld.ldp, 21, 22, 31, 0x30)
asm_pagein.emit(bld.ldp, 19, 20, 31, 0x40)
asm_pagein.emit(bld.ldp, 29, 30, 31, 0x50)
asm_pagein.emit(bld.add_sp_sp, 0x60)
asm_pagein.emit(bld.ret)

opcodes_pagein = asm_pagein.assemble()
raw_pagein = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_pagein)
print(f"custom_pagein: {len(raw_pagein)} bytes (ends at 0x{va_pagein + len(raw_pagein):x})")

# =====================================================================
# Now write everything into the Mach-O buffer
# =====================================================================
with open('xnu_arm64_bdev_test2.macho', 'rb') as f:
    buf = bytearray(f.read())

buf[fo_strat : fo_strat + len(raw_strategy)] = raw_strategy
buf[fo_open : fo_open + len(raw_open)] = raw_open
buf[fo_close : fo_close + len(raw_close)] = raw_close
buf[fo_psize : fo_psize + len(raw_psize)] = raw_psize
buf[fo_ioctl : fo_ioctl + len(raw_ioctl)] = raw_ioctl
buf[fo_ret0 : fo_ret0 + len(raw_ret0)] = raw_ret0
buf[fo_mountroot : fo_mountroot + len(raw_mountroot)] = raw_mountroot
buf[fo_lookup : fo_lookup + len(raw_lookup)] = raw_lookup
buf[fo_getattr : fo_getattr + len(raw_getattr)] = raw_getattr
buf[fo_read : fo_read + len(raw_read)] = raw_read
buf[fo_pagein : fo_pagein + len(raw_pagein)] = raw_pagein
buf[fo_root : fo_root + len(raw_root)] = raw_root

# Verify no overlap across all routines:
routines = [
    ('strat', fo_strat, len(raw_strategy)),
    ('open', fo_open, len(raw_open)),
    ('close', fo_close, len(raw_close)),
    ('psize', fo_psize, len(raw_psize)),
    ('ioctl', fo_ioctl, len(raw_ioctl)),
    ('ret0', fo_ret0, len(raw_ret0)),
    ('mountroot', fo_mountroot, len(raw_mountroot)),
    ('lookup', fo_lookup, len(raw_lookup)),
    ('getattr', fo_getattr, len(raw_getattr)),
    ('read', fo_read, len(raw_read)),
    ('pagein', fo_pagein, len(raw_pagein)),
    ('root', fo_root, len(raw_root)),
]
routines.sort(key=lambda x: x[1])
for i in range(len(routines)-1):
    c_name, c_fo, c_len = routines[i]
    n_name, n_fo, _ = routines[i+1]
    assert c_fo + c_len <= n_fo, f"OVERLAP: {c_name} [0x{c_fo:x}..0x{c_fo+c_len:x}] collides with {n_name} at 0x{n_fo:x}"
assert routines[-1][1] + routines[-1][2] <= 0x54c000, "Routines exceed __TEXT_EXEC padding!"
print('All driver and vnodeop routines verified strictly non-overlapping in executable padding!')

# =====================================================================
# Populate bdevsw slots 0 and 1 on Page 32 using chained fixups
# =====================================================================
bdev_targets = [
    fo_open,     # d_open
    fo_close,    # d_close
    fo_strat,    # d_strategy
    fo_ioctl,    # d_ioctl
    fo_open,     # d_dump
    fo_psize,    # d_psize
]
for slot in (0, 1):
    base_fo = 0xc9cf88 + slot * 0x38
    for i, tgt in enumerate(bdev_targets):
        fo = base_fo + i * 8
        orig = struct.unpack('<Q', buf[fo:fo+8])[0]
        buf[fo:fo+8] = struct.pack('<Q', (orig & ~0x3fffffff) | tgt)
    struct.pack_into('<Q', buf, base_fo + 0x30, 2) # d_type (D_DISK)

print('bdevsw slots 0 and 1 chained fixups updated cleanly!')

# =====================================================================
# Splice APFS into vfsconf Entry 3 on Page 17 chained fixups
# =====================================================================
fo_entry2 = 0xc8d9a8
orig_e2 = struct.unpack('<Q', buf[fo_entry2:fo_entry2+8])[0]
tgt_e2 = orig_e2 & 0x3fffffff
buf[fo_entry2:fo_entry2+8] = struct.pack('<Q', (24 << 51) | tgt_e2)

# Entry 3 at fo 0xc8da08 (VA 0xfffffff007c91a08)
# vfc_vfsops points to routefs_vfsops at 0x1c8580 (already valid, slid, and PAC-signed)
struct.pack_into('<Q', buf, 0xc8da08, (10 << 51) | 0x1c8580)
buf[0xc8da10:0xc8da20] = b'apfs\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
struct.pack_into('<II', buf, 0xc8da20, 20, 0)
struct.pack_into('<Q', buf, 0xc8da28, 0x04000020)

# vfc_mountroot at 0x54b400, next 130, AUTH_REBASE with div 0xa51f (Key IA)
vfc_mr_val = (1 << 63) | (130 << 51) | (0xa51f << 32) | 0x54b400
struct.pack_into('<Q', buf, 0xc8da30, vfc_mr_val)
struct.pack_into('<Q', buf, 0xc8da38, 0)
struct.pack_into('<Q', buf, 0xc8da40, 0)
struct.pack_into('<Q', buf, 0xc8da48, 0x104)
struct.pack_into('<QQ', buf, 0xc8da50, 0, 0)

print('APFS vfsconf configured in Entry 3 at 0xc8da08 (vfsops -> routefs_vfsops, mountroot -> AUTH 0x54b400)!')

# =====================================================================
# Patch bsd_init rootvp authentication check @ 0xfffffff007858944
# =====================================================================
fo_rootvp_auth = 0x854944
orig_auth_insn = struct.unpack('<I', buf[fo_rootvp_auth:fo_rootvp_auth+4])[0]
assert orig_auth_insn == 0x36000a35, f"Unexpected instruction at 0x854944: 0x{orig_auth_insn:08x}"
struct.pack_into('<I', buf, fo_rootvp_auth, 0x52800035)
print('Patched bsd_init rootvp authentication check at 0xfffffff007858944 to mov w21, #1!')

# =====================================================================
# Patch IOTaskHasEntitlement @ 0xfffffff007b89840 and 0xfffffff007b898b4
# =====================================================================
fo_ent1 = 0xb85840
fo_ent2 = 0xb858b4
struct.pack_into('<II', buf, fo_ent1, 0x52800020, 0xd65f03c0)
struct.pack_into('<II', buf, fo_ent2, 0x52800020, 0xd65f03c0)
print('Patched IOTaskHasEntitlement at 0xfffffff007b89840 and 0xfffffff007b898b4 to ret 1!')

# =====================================================================
# Patch offline owner SystemOS and Data scratch mount checks in init_program
# =====================================================================
fo_sysos_auth = 0x88bbb8
fo_sysos_panic = 0x88bbd8
struct.pack_into('<I', buf, fo_sysos_auth, 0x52800016)
struct.pack_into('<I', buf, fo_sysos_panic, 0xd503201f)
print('Patched SystemOS offline owner mount check at 0xfffffff00788fbb8 & 0xfffffff00788fbd8!')

fo_data_panic = 0x88bdb8
struct.pack_into('<I', buf, fo_data_panic, 0xd503201f)
print('Patched Data scratch offline mount check at 0xfffffff00788fdb8!')

# =====================================================================
# Append launchd.bin & dyld.bin, and expand __LINKEDIT segment
# =====================================================================
with open('launchd.bin', 'rb') as f:
    launchd_bytes = f.read()

assert len(launchd_bytes) == 541600, f"Unexpected launchd size: {len(launchd_bytes)}"

# Align launchd to 16KB boundary
pad_l = (16384 - (len(launchd_bytes) % 16384)) % 16384
launchd_padded = launchd_bytes + b'\x00' * pad_l

with open('dyld.bin', 'rb') as f:
    dyld_bytes = f.read()

assert len(dyld_bytes) == 922912, f"Unexpected dyld size: {len(dyld_bytes)}"

# Align dyld to 16KB boundary
pad_d = (16384 - (len(dyld_bytes) % 16384)) % 16384
dyld_padded = dyld_bytes + b'\x00' * pad_d

payload = launchd_padded + dyld_padded
payload_size = len(payload)

# Update __LINKEDIT LC_SEGMENT_64 command at 0x1348
fo_linkedit_lc = 0x1348
vmsize_orig = struct.unpack('<Q', buf[fo_linkedit_lc + 32 : fo_linkedit_lc + 40])[0]
filesize_orig = struct.unpack('<Q', buf[fo_linkedit_lc + 48 : fo_linkedit_lc + 56])[0]
assert vmsize_orig == 0x998000 and filesize_orig == 0x998000

new_vmsize = vmsize_orig + payload_size
new_filesize = filesize_orig + payload_size
struct.pack_into('<Q', buf, fo_linkedit_lc + 32, new_vmsize)
struct.pack_into('<Q', buf, fo_linkedit_lc + 48, new_filesize)

orig_file_size = len(buf)
assert orig_file_size == 0x01778000, f"Unexpected orig file size: 0x{orig_file_size:x}"
buf.extend(payload)
print(f"__LINKEDIT updated: vmsize 0x{vmsize_orig:x} -> 0x{new_vmsize:x}, filesize 0x{filesize_orig:x} -> 0x{new_filesize:x}")
print(f"launchd appended at FO 0x{orig_file_size:x} (VA 0xfffffff00899c000, len 0x{len(launchd_padded):x}).")
print(f"dyld appended at FO 0x{orig_file_size + len(launchd_padded):x} (VA 0xfffffff008a24000, len 0x{len(dyld_padded):x}).")
print(f"Total Mach-O size: {len(buf)} bytes.")

# =====================================================================
# Verify fixup chains on all modified pages
# =====================================================================
def verify_chain(page_name, start_fo, expected_fo, expected_end):
    curr = start_fo
    visited = []
    while True:
        visited.append(curr)
        val = struct.unpack('<Q', buf[curr:curr+8])[0]
        nxt = (val >> 51) & 0x7ff
        if nxt == 0:
            break
        curr += nxt * 4
    for ef in expected_fo:
        assert ef in visited, f"Page {page_name}: expected 0x{ef:x} in chain, but missing!"
    assert curr == expected_end, f"Page {page_name}: expected end at 0x{expected_end:x}, got 0x{curr:x}"
    print(f"Chain {page_name} verification passed: {len(visited)} chained pointers, ended at 0x{curr:x}.")

verify_chain("Page 17 (vfsconf)", 0xc8d000, [0xc8d9a8, 0xc8da08, 0xc8da30, 0xc8dc38], 0xc8dfc8)
verify_chain("Page 32 (bdevsw)", 0xc9c420, [0xc9cf88, 0xc9cfc0, 0xc9cff8], 0xc9cff8)

# Save patched kernel
with open('xnu_arm64_bdev_final.macho', 'wb') as f:
    f.write(buf)

print('Successfully created patched xnu_arm64_bdev_final.macho!')
