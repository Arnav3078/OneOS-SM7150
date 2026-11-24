import struct
import build_bdev_driver as bld

print("=== Assembling bdev driver, custom vnodeops, and launchd ===")

# =====================================================================
# 1. bdev_strategy @ 0xfffffff00754f210
# =====================================================================
asm_strat = bld.Assembler(0xfffffff00754f210)
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

# Step B: Get disk object from gOneiOSHostedDisk
asm_strat.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d5d000))
asm_strat.emit(bld.ldr_reg, 10, 8, 0x9f0) # x10 = gOneiOSHostedDisk
asm_strat.emit(lambda pc, tgt: bld.cbz(10, pc, tgt), 'err_nodev')

# Step C: buf_map(bp, &vaddr)
asm_strat.emit(bld.mov_reg, 0, 19)
asm_strat.emit(bld.add_reg_sp, 1, 0x78)
asm_strat.emit(lambda pc: bld.bl(pc, 0xfffffff0075ae0c4)) # buf_map
asm_strat.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'err_map')
asm_strat.emit(bld.ldr_reg, 24, 31, 0x78) # x24 = vaddr

# Step D: Bounce buffer at disk + 0x110
asm_strat.emit(bld.add_reg_imm, 25, 10, 0x110) # x25 = bounce buffer
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
print(f"bdev_strategy: {len(raw_strategy)} bytes (from 0xfffffff00754f210)")

# 2. bdev_open @ 0xfffffff00754f360
raw_open = struct.pack('<II', 0x52800000, 0xd65f03c0)

# 3. bdev_close @ 0xfffffff00754f368
raw_close = struct.pack('<II', 0x52800000, 0xd65f03c0)

# 4. bdev_psize @ 0xfffffff00754f370
raw_psize = struct.pack('<IIII',
    0xd2858000, # mov x0, #0x2c00
    0xf2a01400, # movk x0, #0xa0, lsl #16 -> 0xa02c00 = 10,496,000 sectors
    0xd65f03c0, # ret
    0xd503201f  # nop
)

# 5. bdev_ioctl @ 0xfffffff00754f380
asm_ioctl = bld.Assembler(0xfffffff00754f380)
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

# =====================================================================
# 6. apfs_mountroot @ 0xfffffff00754f400
# =====================================================================
asm_mountroot = bld.Assembler(0xfffffff00754f400)
asm_mountroot.emit(bld.sub_sp_sp, 0x90)
asm_mountroot.emit(bld.stp, 29, 30, 31, 0x80)
asm_mountroot.emit(bld.stp, 19, 20, 31, 0x70)
asm_mountroot.emit(bld.stp, 21, 22, 31, 0x60)
asm_mountroot.emit(bld.add_reg_sp, 29, 0x80)
asm_mountroot.emit(bld.mov_reg, 19, 0) # x19 = mp
asm_mountroot.emit(bld.mov_reg, 20, 1) # x20 = devvp
asm_mountroot.emit(bld.mov_reg, 21, 2) # x21 = ctx

# Step 1: Copy 64 entries from *devfs_vnodeop_p to custom_vnodeops (0xfffffff007c81310)
asm_mountroot.emit(lambda pc: bld.adrp(0, pc, 0xfffffff007c81000))
asm_mountroot.emit(bld.add_reg_imm, 0, 0, 0x310) # dst = 0xfffffff007c81310
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

# Overwrite slots in custom_vnodeops:
asm_mountroot.emit(lambda pc: bld.adrp(10, pc, 0xfffffff007c81000))
asm_mountroot.emit(bld.add_reg_imm, 10, 10, 0x310) # x10 = custom_vnodeops

# ret0_stub = 0xfffffff00754f610
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff00754f000))
asm_mountroot.emit(bld.add_reg_imm, 8, 8, 0x610)
asm_mountroot.emit(bld.str_reg, 8, 10, 7*8)  # vnop_open
asm_mountroot.emit(bld.str_reg, 8, 10, 9*8)  # vnop_close
asm_mountroot.emit(bld.str_reg, 8, 10, 10*8) # vnop_access
asm_mountroot.emit(bld.str_reg, 8, 10, 22*8) # vnop_mmap_check
asm_mountroot.emit(bld.str_reg, 8, 10, 23*8) # vnop_mmap
asm_mountroot.emit(bld.str_reg, 8, 10, 24*8) # vnop_mnomap
asm_mountroot.emit(bld.str_reg, 8, 10, 32*8) # vnop_mkdir
asm_mountroot.emit(bld.str_reg, 8, 10, 33*8) # vnop_compound_mkdir

# Slot 3 (vnop_lookup) = custom_lookup (0xfffffff00754f620)
asm_mountroot.emit(bld.add_reg_imm, 9, 8, 0x620 - 0x610)
asm_mountroot.emit(bld.str_reg, 9, 10, 3*8)

# Slot 11 (vnop_getattr) = custom_getattr (0xfffffff00754f740)
asm_mountroot.emit(bld.add_reg_imm, 9, 8, 0x740 - 0x610)
asm_mountroot.emit(bld.str_reg, 9, 10, 11*8)

# Slot 13 (vnop_read) = custom_read (0xfffffff00754f7d0)
asm_mountroot.emit(bld.add_reg_imm, 9, 8, 0x7d0 - 0x610)
asm_mountroot.emit(bld.str_reg, 9, 10, 13*8)

# Slot 46 (vnop_pagein) = custom_pagein (0xfffffff00754f860)
asm_mountroot.emit(bld.add_reg_imm, 9, 8, 0x860 - 0x610)
asm_mountroot.emit(bld.str_reg, 9, 10, 46*8)

# Step 2: Create rootvp (VDIR)
for off in range(0, 0x60, 8):
    asm_mountroot.emit(bld.str_reg, 31, 31, off)

asm_mountroot.emit(bld.str_reg, 19, 31, 0x00) # params.vnfs_mp = mp
asm_mountroot.emit(bld.mov_wimm, 8, 2)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x08)  # params.vnfs_vtype = 2 (VDIR)
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff0070a6000))
asm_mountroot.emit(bld.add_reg_imm, 8, 8, 0xa8f) # params.vnfs_str = '/'
asm_mountroot.emit(bld.str_reg, 8, 31, 0x10)
asm_mountroot.emit(bld.mov_wimm, 8, 1)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x20)  # params.vnfs_fsnode = 1
asm_mountroot.emit(bld.str_reg, 10, 31, 0x28) # params.vnfs_vops = custom_vnodeops
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
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007c81000))
asm_mountroot.emit(bld.str_reg, 22, 8, 0x300) # apfs_rootvp = rootvp

# Step 3: Create launchd_vp (VREG)
asm_mountroot.emit(bld.mov_wimm, 8, 1)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x08) # params.vnfs_vtype = 1 (VREG)
asm_mountroot.emit(lambda pc: bld.adrp(8, pc, 0xfffffff0070e4000))
asm_mountroot.emit(bld.add_reg_imm, 8, 8, 0x815) # params.vnfs_str = 'launchd'
asm_mountroot.emit(bld.str_reg, 8, 31, 0x10)
asm_mountroot.emit(bld.str_reg, 22, 31, 0x18) # params.vnfs_dvp = rootvp
asm_mountroot.emit(bld.mov_wimm, 8, 2)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x20) # params.vnfs_fsnode = 2
asm_mountroot.emit(bld.str_reg, 31, 31, 0x30) # params.vnfs_markroot = 0
asm_mountroot.emit(bld.mov_ximm, 8, 0x43a0)
asm_mountroot.emit(bld.movk_ximm, 8, 0x0008, 16)
asm_mountroot.emit(bld.str_reg, 8, 31, 0x40) # params.vnfs_filesize = 541600 (ubc_info_init)
asm_mountroot.emit(bld.str_reg, 31, 31, 0x58) # clear vp

asm_mountroot.emit(bld.mov_wimm, 0, 0)
asm_mountroot.emit(bld.mov_wimm, 1, 0x58)
asm_mountroot.emit(bld.add_reg_sp, 2, 0x00)
asm_mountroot.emit(bld.add_reg_sp, 3, 0x58)
asm_mountroot.emit(bld.mov_wimm, 4, 2)
asm_mountroot.emit(lambda pc: bld.bl(pc, 0xfffffff0075d44e0)) # vnode_create_internal
asm_mountroot.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'mount_fail')

asm_mountroot.emit(bld.ldr_reg, 8, 31, 0x58) # x8 = launchd_vp
asm_mountroot.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007c81000))
asm_mountroot.emit(bld.str_reg, 8, 9, 0x308) # launchd_vp = vp

# Success: return 0
asm_mountroot.emit(bld.mov_wimm, 0, 0)
asm_mountroot.emit(lambda pc, tgt: bld.b(pc, tgt), 'mount_ret')

asm_mountroot.label('mount_fail')

asm_mountroot.label('mount_ret')
asm_mountroot.emit(bld.ldp, 21, 22, 31, 0x60)
asm_mountroot.emit(bld.ldp, 19, 20, 31, 0x70)
asm_mountroot.emit(bld.ldp, 29, 30, 31, 0x80)
asm_mountroot.emit(bld.add_sp_sp, 0x90)
asm_mountroot.emit(bld.ret)

opcodes_mountroot = asm_mountroot.assemble()
raw_mountroot = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_mountroot)
print(f"apfs_mountroot: {len(raw_mountroot)} bytes (ends at 0x{0xfffffff00754f400 + len(raw_mountroot):x})")

# =====================================================================
# 7. apfs_root @ 0xfffffff00754f5b0
# =====================================================================
asm_root = bld.Assembler(0xfffffff00754f5b0)
asm_root.emit(bld.ldr_reg, 8, 0, 0x8f8) # mp->mnt_data
asm_root.emit(lambda pc, tgt: bld.cbnz(8, pc, tgt), 'has_vp')
asm_root.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007c81000))
asm_root.emit(bld.ldr_reg, 8, 9, 0x300) # apfs_rootvp

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
print(f"apfs_root: {len(raw_root)} bytes (ends at 0x{0xfffffff00754f5b0 + len(raw_root):x})")

# =====================================================================
# 8. ret0_stub @ 0xfffffff00754f610
# =====================================================================
raw_ret0 = struct.pack('<II', 0x52800000, 0xd65f03c0)

# =====================================================================
# 9. custom_lookup @ 0xfffffff00754f620
# =====================================================================
asm_lookup = bld.Assembler(0xfffffff00754f620)
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
asm_lookup.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'check_dev_launchd')

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
asm_lookup.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007c81000))
asm_lookup.emit(bld.ldr_reg, 0, 8, 0x308) # x0 = launchd_vp
asm_lookup.emit(bld.mov_reg, 24, 0)       # x24 = launchd_vp
asm_lookup.emit(lambda pc: bld.bl(pc, 0xfffffff0075d3c70)) # vnode_get
asm_lookup.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'out_err')
asm_lookup.emit(bld.str_reg, 24, 20, 0)   # *vpp = launchd_vp
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
asm_lookup.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007c81000))
asm_lookup.emit(bld.ldr_reg, 0, 8, 0x300) # x0 = rootvp
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
print(f"custom_lookup: {len(raw_lookup)} bytes (ends at 0x{0xfffffff00754f620 + len(raw_lookup):x})")

# =====================================================================
# 10. custom_getattr @ 0xfffffff00754f740
# =====================================================================
asm_getattr = bld.Assembler(0xfffffff00754f740)
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
asm_getattr.emit(lambda pc: bld.adrp(9, pc, 0xfffffff007c81000))
asm_getattr.emit(bld.ldr_reg, 9, 9, 0x308) # x9 = launchd_vp
asm_getattr.emit(bld.cmp_xreg, 2, 9)
asm_getattr.emit(lambda pc, tgt: bld.b_eq(pc, tgt), 'is_launchd')

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

opcodes_getattr = asm_getattr.assemble()
raw_getattr = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes_getattr)
print(f"custom_getattr: {len(raw_getattr)} bytes (ends at 0x{0xfffffff00754f740 + len(raw_getattr):x})")

# =====================================================================
# 11. custom_read @ 0xfffffff00754f7d0
# =====================================================================
asm_read = bld.Assembler(0xfffffff00754f7d0)
asm_read.emit(bld.sub_sp_sp, 0x40)
asm_read.emit(bld.stp, 29, 30, 31, 0x30)
asm_read.emit(bld.stp, 19, 20, 31, 0x20)
asm_read.emit(bld.stp, 21, 22, 31, 0x10)
asm_read.emit(bld.add_reg_sp, 29, 0x30)

asm_read.emit(bld.ldr_reg, 19, 0, 0x10) # x19 = uio
asm_read.emit(bld.mov_reg, 0, 19)
asm_read.emit(lambda pc: bld.bl(pc, 0xfffffff0078c1ef4)) # uio_offset
asm_read.emit(bld.mov_reg, 20, 0) # x20 = offset

asm_read.emit(bld.mov_reg, 0, 19)
asm_read.emit(lambda pc: bld.bl(pc, 0xfffffff0078c17b4)) # uio_resid
asm_read.emit(bld.mov_reg, 21, 0) # x21 = resid

# file_size = 541600 (0x843a0)
asm_read.emit(bld.mov_ximm, 8, 0x43a0)
asm_read.emit(bld.movk_ximm, 8, 0x0008, 16)

# If offset >= file_size or resid == 0 -> EOF
asm_read.emit(bld.cmp_xreg, 20, 8)
asm_read.emit(lambda pc, tgt: bld.b_hs(pc, tgt), 'read_eof')
asm_read.emit(lambda pc, tgt: bld.cbz(21, pc, tgt), 'read_eof')

# count = min(resid, file_size - offset)
asm_read.emit(bld.sub_reg_reg_64, 22, 8, 20)
asm_read.emit(bld.cmp_xreg, 21, 22)
asm_read.emit(bld.csel_lo, 22, 21, 22)

# uiomove(launchd_payload + offset, count, uio)
asm_read.emit(bld.mov_ximm, 0, 0xc000)
asm_read.emit(bld.movk_ximm, 0, 0x0899, 16)
asm_read.emit(bld.movk_ximm, 0, 0xfff0, 32)
asm_read.emit(bld.movk_ximm, 0, 0xffff, 48)
asm_read.emit(bld.add_reg_reg, 0, 0, 20) # src = payload + offset
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
print(f"custom_read: {len(raw_read)} bytes (ends at 0x{0xfffffff00754f7d0 + len(raw_read):x})")

# =====================================================================
# 12. custom_pagein @ 0xfffffff00754f860
# =====================================================================
asm_pagein = bld.Assembler(0xfffffff00754f860)
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

# file_size = 541600 (0x843a0)
asm_pagein.emit(bld.mov_ximm, 8, 0x43a0)
asm_pagein.emit(bld.movk_ximm, 8, 0x0008, 16)

# to_copy = (f_offset < file_size) ? min(size, file_size - f_offset) : 0
asm_pagein.emit(bld.mov_ximm, 2, 0)
asm_pagein.emit(bld.cmp_xreg, 22, 8)
asm_pagein.emit(lambda pc, tgt: bld.b_hs(pc, tgt), 'do_zero')
asm_pagein.emit(bld.sub_reg_reg_64, 2, 8, 22)
asm_pagein.emit(bld.cmp_xreg, 23, 2)
asm_pagein.emit(bld.csel_lo, 2, 23, 2)
asm_pagein.emit(lambda pc, tgt: bld.cbz(2, pc, tgt), 'do_zero')

# memcpy(dst, launchd_payload + f_offset, to_copy)
asm_pagein.emit(bld.mov_reg, 0, 24)
asm_pagein.emit(bld.mov_ximm, 1, 0xc000)
asm_pagein.emit(bld.movk_ximm, 1, 0x0899, 16)
asm_pagein.emit(bld.movk_ximm, 1, 0xfff0, 32)
asm_pagein.emit(bld.movk_ximm, 1, 0xffff, 48)
asm_pagein.emit(bld.add_reg_reg, 1, 1, 22) # src = payload + f_offset
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
print(f"custom_pagein: {len(raw_pagein)} bytes (ends at 0x{0xfffffff00754f860 + len(raw_pagein):x})")

# =====================================================================
# Now write everything into the Mach-O buffer
# =====================================================================
with open('xnu_arm64_bdev_test2.macho', 'rb') as f:
    buf = bytearray(f.read())

fo_code = 0x0054b210 # VA 0xfffffff00754f210
buf[fo_code : fo_code + len(raw_strategy)] = raw_strategy
buf[fo_code + 0x150 : fo_code + 0x150 + len(raw_open)] = raw_open         # 0xfffffff00754f360
buf[fo_code + 0x158 : fo_code + 0x158 + len(raw_close)] = raw_close       # 0xfffffff00754f368
buf[fo_code + 0x160 : fo_code + 0x160 + len(raw_psize)] = raw_psize       # 0xfffffff00754f370
buf[fo_code + 0x170 : fo_code + 0x170 + len(raw_ioctl)] = raw_ioctl       # 0xfffffff00754f380
buf[fo_code + 0x1f0 : fo_code + 0x1f0 + len(raw_mountroot)] = raw_mountroot # 0xfffffff00754f400
buf[fo_code + 0x3a0 : fo_code + 0x3a0 + len(raw_root)] = raw_root         # 0xfffffff00754f5b0
buf[fo_code + 0x400 : fo_code + 0x400 + len(raw_ret0)] = raw_ret0         # 0xfffffff00754f610
buf[fo_code + 0x410 : fo_code + 0x410 + len(raw_lookup)] = raw_lookup     # 0xfffffff00754f620
buf[fo_code + 0x530 : fo_code + 0x530 + len(raw_getattr)] = raw_getattr   # 0xfffffff00754f740
buf[fo_code + 0x5c0 : fo_code + 0x5c0 + len(raw_read)] = raw_read         # 0xfffffff00754f7d0
buf[fo_code + 0x650 : fo_code + 0x650 + len(raw_pagein)] = raw_pagein     # 0xfffffff00754f860

print('All driver and vnodeop routines written to executable padding!')

# =====================================================================
# Populate bdevsw slots 0 and 1 on Page 32 using chained fixups
# =====================================================================
bdev_targets = [
    0x54b360, # d_open
    0x54b368, # d_close
    0x54b210, # d_strategy
    0x54b380, # d_ioctl
    0x54b360, # d_dump
    0x54b370, # d_psize
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
# Splice apfs_vfsops into Page 1 chained fixups
# =====================================================================
fo_290 = 0xc7d290
orig_290 = struct.unpack('<Q', buf[fo_290:fo_290+8])[0]
tgt_290 = orig_290 & 0x3fffffff
buf[fo_290:fo_290+8] = struct.pack('<Q', (2 << 51) | tgt_290)

# apfs_vfsops at fo 0xc7d298 (VA 0xfffffff007c81298)
# struct vfsops (12 entries = 96 bytes)
# ret0_stub is at 0x54b610
# apfs_root is at 0x54b5b0
vfsops_entries = [
    (0, (2 << 51) | 0x54b610),   # [00] vfs_mount -> ret0_stub, next=2 (+8 B)
    (1, (2 << 51) | 0x54b610),   # [08] vfs_start -> ret0_stub, next=2 (+8 B)
    (2, (2 << 51) | 0x54b610),   # [10] vfs_unmount -> ret0_stub, next=2 (+8 B)
    (3, (4 << 51) | 0x54b5b0),   # [18] vfs_root -> apfs_root, next=4 (+16 B) [skips quotactl]
    (4, 0),                      # [20] vfs_quotactl = NULL
    (5, (2 << 51) | 0x54b610),   # [28] vfs_statfs -> ret0_stub, next=2 (+8 B)
    (6, (2 << 51) | 0x54b610),   # [30] vfs_sync -> ret0_stub, next=2 (+8 B)
    (7, (6 << 51) | 0x54b610),   # [38] vfs_vget -> ret0_stub, next=6 (+24 B) [skips fhtovp, vptofh]
    (8, 0),                      # [40] vfs_fhtovp = NULL
    (9, 0),                      # [48] vfs_vptofh = NULL
    (10, (138 << 51) | 0x54b610),# [50] vfs_init -> ret0_stub, next=138 (+552 B) -> lands on 0xc7d510
    (11, 0),                     # [58] vfs_sysctl = NULL
]
for idx, val in vfsops_entries:
    struct.pack_into('<Q', buf, 0xc7d298 + idx*8, val)

print('apfs_vfsops spliced into Page 1 fixup chain at 0xc7d298!')

# =====================================================================
# Splice APFS into vfsconf Entry 3 on Page 17 chained fixups
# =====================================================================
fo_entry2 = 0xc8d9a8
orig_e2 = struct.unpack('<Q', buf[fo_entry2:fo_entry2+8])[0]
tgt_e2 = orig_e2 & 0x3fffffff
buf[fo_entry2:fo_entry2+8] = struct.pack('<Q', (24 << 51) | tgt_e2)

# Entry 3 at fo 0xc8da08 (VA 0xfffffff007c91a08)
struct.pack_into('<Q', buf, 0xc8da08, (10 << 51) | 0xc7d298)
buf[0xc8da10:0xc8da20] = b'apfs\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
struct.pack_into('<II', buf, 0xc8da20, 20, 0)
struct.pack_into('<Q', buf, 0xc8da28, 0x04000020)
# vfc_mountroot at 0x54b400, next 130
struct.pack_into('<Q', buf, 0xc8da30, (130 << 51) | 0x54b400)
struct.pack_into('<Q', buf, 0xc8da38, 0)
struct.pack_into('<Q', buf, 0xc8da40, 0)
struct.pack_into('<Q', buf, 0xc8da48, 0x104)
struct.pack_into('<QQ', buf, 0xc8da50, 0, 0)

print('APFS vfsconf configured in Entry 3 at 0xc8da08!')

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

# Clear global pointers at 0xfffffff007c81300 (fo 0xc7d300):
# 0xc7d300: apfs_rootvp (8 B)
# 0xc7d308: launchd_vp (8 B)
# 0xc7d310 .. 0xc7d510: custom_vnodeops (512 B)
buf[0xc7d300 : 0xc7d510] = b'\x00' * 528
print('Cleared global rootvp, launchd_vp, and custom_vnodeops memory!')

# =====================================================================
# Append launchd.bin and expand __LINKEDIT segment
# =====================================================================
with open('launchd.bin', 'rb') as f:
    launchd_bytes = f.read()

assert len(launchd_bytes) == 541600, f"Unexpected launchd size: {len(launchd_bytes)}"

# Align to 16KB boundary
pad_len = (16384 - (len(launchd_bytes) % 16384)) % 16384
launchd_padded = launchd_bytes + b'\x00' * pad_len
payload_size = len(launchd_padded)

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
buf.extend(launchd_padded)
print(f"__LINKEDIT updated: vmsize 0x{vmsize_orig:x} -> 0x{new_vmsize:x}, filesize 0x{filesize_orig:x} -> 0x{new_filesize:x}")
print(f"launchd appended at FO 0x{orig_file_size:x} (VA 0xfffffff00899c000). Total size: {len(buf)} bytes.")

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

verify_chain("Page 1 (vfsops)", 0xc7d168, [0xc7d290, 0xc7d298, 0xc7d2e8, 0xc7d510], 0xc7df10)
verify_chain("Page 17 (vfsconf)", 0xc8d000, [0xc8d9a8, 0xc8da08, 0xc8da30, 0xc8dc38], 0xc8dfc8)
verify_chain("Page 32 (bdevsw)", 0xc9c420, [0xc9cf88, 0xc9cfc0, 0xc9cff8], 0xc9cff8)

# Save patched kernel
with open('xnu_arm64_bdev_final.macho', 'wb') as f:
    f.write(buf)

print('Successfully created patched xnu_arm64_bdev_final.macho!')
