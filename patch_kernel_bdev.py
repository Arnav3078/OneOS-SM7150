import struct
import build_bdev_driver as bld
import capstone

# 1. Assemble bdev_strategy
asm = bld.Assembler(0x200054f210)

asm.emit(bld.sub_sp_sp, 0x80)
asm.emit(bld.stp, 27, 28, 31, 0x10)
asm.emit(bld.stp, 25, 26, 31, 0x20)
asm.emit(bld.stp, 23, 24, 31, 0x30)
asm.emit(bld.stp, 21, 22, 31, 0x40)
asm.emit(bld.stp, 19, 20, 31, 0x50)
asm.emit(bld.stp, 29, 30, 31, 0x60)
asm.emit(bld.add_reg_sp, 29, 0x60)
asm.emit(bld.mov_reg, 19, 0) # mov x19, x0 (bp)

# Step A: Query buf fields
asm.emit(bld.mov_reg, 0, 19)
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075adda8)) # buf_device
asm.emit(bld.mov_wreg, 20, 0) # w20 = dev

asm.emit(bld.mov_reg, 0, 19)
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075add5c)) # buf_blkno
asm.emit(bld.mov_reg, 21, 0) # x21 = blkno

asm.emit(bld.mov_reg, 0, 19)
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad420)) # buf_count
asm.emit(bld.mov_wreg, 22, 0) # w22 = count

asm.emit(bld.mov_reg, 0, 19)
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad3e4)) # buf_flags
asm.emit(bld.mov_wreg, 23, 0) # w23 = flags

# Step B: Map buffer memory
asm.emit(bld.str_reg, 31, 31, 8) # str xzr, [sp, #8]
asm.emit(bld.mov_reg, 0, 19)
asm.emit(bld.add_reg_sp, 1, 8) # add x1, sp, #8
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075adfac)) # buf_map(bp, &vaddr)
asm.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'err_map')
asm.emit(bld.ldr_reg, 24, 31, 8) # x24 = vaddr

# Step C: Find disk for role os
asm.emit(lambda pc: bld.adrp(8, pc, 0xfffffff007d8b000))
asm.emit(bld.add_reg_imm, 8, 8, 0x598) # &disks[0]
asm.emit(bld.mov_wimm, 9, 0) # idx = 0

asm.label('find_loop')
asm.emit(bld.ldr_reg_uxtw3, 10, 8, 9) # x10 = disks[idx]
asm.emit(lambda pc, tgt: bld.cbz(10, pc, tgt), 'next_disk')
asm.emit(bld.ldrb_reg, 11, 10, 0xf1)
asm.emit(bld.cmp_wimm, 11, ord('o'))
asm.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'next_disk')
asm.emit(bld.ldrb_reg, 11, 10, 0xf2)
asm.emit(bld.cmp_wimm, 11, ord('s'))
asm.emit(lambda pc, tgt: bld.b_ne(pc, tgt), 'next_disk')
asm.emit(bld.ldrb_reg, 11, 10, 0xf3)
asm.emit(lambda pc, tgt: bld.cbz(11, pc, tgt), 'found_disk')

asm.label('next_disk')
asm.emit(bld.add_reg_imm, 9, 9, 1)
asm.emit(bld.cmp_wimm, 9, 16)
asm.emit(lambda pc, tgt: bld.b_lo(pc, tgt), 'find_loop')
asm.emit(bld.ldr_reg, 10, 8, 0) # fallback: disks[0]

asm.label('found_disk')
asm.emit(lambda pc, tgt: bld.cbz(10, pc, tgt), 'err_nodev')

# Step D: Get bounce buffer virtual address
asm.emit(bld.ldr_reg, 8, 10, 0x98) # desc = [disk + 0x98]
asm.emit(lambda pc, tgt: bld.cbz(8, pc, tgt), 'err_eio')
asm.emit(bld.ldr_reg, 25, 8, 0xb8) # bounce = [desc + 0xb8]
asm.emit(lambda pc, tgt: bld.cbz(25, pc, tgt), 'err_eio')

# Step E: Chunk transfer loop
asm.emit(bld.mov_wimm, 26, 0) # transferred = 0

asm.label('xfer_loop')
asm.emit(bld.cmp_reg, 26, 22)
asm.emit(lambda pc, tgt: bld.b_hs(pc, tgt), 'xfer_done')

asm.emit(bld.sub_reg_reg, 27, 22, 26) # rem = count - transferred
asm.emit(bld.mov_wimm, 8, 0) # 0x100000 (1MB)
asm.emit(bld.movk_wimm, 8, 0x10, 16)
asm.emit(bld.cmp_reg, 27, 8)
asm.emit(bld.csel_w_lo, 27, 27, 8) # chunk = min(rem, 1MB)

# block = blkno + (transferred >> 9)
asm.emit(bld.lsr_reg_imm, 8, 26, 9)
asm.emit(bld.add_reg_reg, 2, 21, 8) # x2 = block

asm.emit(lambda pc, tgt: bld.tbz(23, 0, pc, tgt), 'do_write')

# READ: OneiOSHostedDisk::transfer(disk, 0, block, chunk)
asm.emit(bld.mov_reg, 0, 10)
asm.emit(bld.mov_wimm, 1, 0) # type = 0
asm.emit(bld.mov_wreg, 3, 27) # nbytes = chunk
asm.emit(lambda pc: bld.bl(pc, 0xfffffff007c0f3f4))
asm.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'err_xfer')

# memcpy(vaddr + transferred, bounce, chunk)
asm.emit(bld.add_reg_reg_uxtw, 0, 24, 26) # dst = vaddr + transferred
asm.emit(bld.mov_reg, 1, 25) # src = bounce
asm.emit(bld.mov_wreg, 2, 27) # len = chunk
asm.emit(lambda pc: bld.bl(pc, 0xfffffff007c6c970))
asm.emit(lambda pc, tgt: bld.b(pc, tgt), 'xfer_next')

# WRITE: memcpy(bounce, vaddr + transferred, chunk)
asm.label('do_write')
asm.emit(bld.mov_reg, 0, 25) # dst = bounce
asm.emit(bld.add_reg_reg_uxtw, 1, 24, 26) # src = vaddr + transferred
asm.emit(bld.mov_wreg, 2, 27) # len = chunk
asm.emit(lambda pc: bld.bl(pc, 0xfffffff007c6c970))

# OneiOSHostedDisk::transfer(disk, 1, block, chunk)
asm.emit(bld.mov_reg, 0, 10)
asm.emit(bld.mov_wimm, 1, 1) # type = 1
asm.emit(bld.mov_wreg, 3, 27) # nbytes = chunk
asm.emit(lambda pc: bld.bl(pc, 0xfffffff007c0f3f4))
asm.emit(lambda pc, tgt: bld.cbnz_w(0, pc, tgt), 'err_xfer')

asm.label('xfer_next')
asm.emit(bld.add_reg_reg, 26, 26, 27)
asm.emit(lambda pc, tgt: bld.b(pc, tgt), 'xfer_loop')

# Error handlers
asm.label('err_map')
asm.emit(bld.mov_wreg, 1, 0) # err from buf_map
asm.emit(bld.mov_reg, 0, 19)
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad390)) # buf_seterror
asm.emit(lambda pc, tgt: bld.b(pc, tgt), 'finish')

asm.label('err_nodev')
asm.emit(bld.mov_reg, 0, 19)
asm.emit(bld.mov_wimm, 1, 19) # ENODEV
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad390))
asm.emit(lambda pc, tgt: bld.b(pc, tgt), 'finish')

asm.label('err_eio')
asm.label('err_xfer')
asm.emit(bld.mov_reg, 0, 19)
asm.emit(bld.mov_wimm, 1, 5) # EIO
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad390))
asm.emit(lambda pc, tgt: bld.b(pc, tgt), 'finish')

# Finish
asm.label('xfer_done')
asm.label('finish')
asm.emit(bld.mov_reg, 0, 19)
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075ae0d4)) # buf_unmap

asm.emit(bld.sub_reg_reg, 1, 22, 26) # resid = count - transferred
asm.emit(bld.mov_reg, 0, 19)
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075ad448)) # buf_setresid

asm.emit(bld.mov_reg, 0, 19)
asm.emit(lambda pc: bld.bl(pc, 0xfffffff0075ae4f0)) # buf_biodone

# Epilogue
asm.emit(bld.ldp, 29, 30, 31, 0x60)
asm.emit(bld.ldp, 19, 20, 31, 0x50)
asm.emit(bld.ldp, 21, 22, 31, 0x40)
asm.emit(bld.ldp, 23, 24, 31, 0x30)
asm.emit(bld.ldp, 25, 26, 31, 0x20)
asm.emit(bld.ldp, 27, 28, 31, 0x10)
asm.emit(bld.add_sp_sp, 0x80)
asm.emit(bld.ret)

opcodes = asm.assemble()
raw_strategy = b''.join(op.to_bytes(4, 'little') for pc, op in opcodes)
print(f'bdev_strategy: {len(raw_strategy)} bytes')

# Helper routines:
# bdev_open @ 0x200054f3c0: mov w0, #0; ret
raw_open = struct.pack('<II', 0x52800000, 0xd65f03c0)
# bdev_close @ 0x200054f3c8: mov w0, #0; ret
raw_close = struct.pack('<II', 0x52800000, 0xd65f03c0)
# bdev_ioctl @ 0x200054f3d0: mov w0, #0; ret
raw_ioctl = struct.pack('<II', 0x52800000, 0xd65f03c0)
# bdev_psize @ 0x200054f3d8: mov x0, #0xf000; movk x0, #0xa7, lsl #16; ret
raw_psize = struct.pack('<III', 0xd29e0000, 0xf2a014e0, 0xd65f03c0)

with open('xnu_arm64_bdev_test2.macho', 'rb') as f:
    buf = bytearray(f.read())

# Write routines to file offset 0x00c69100 (VA 0x200054f210)
fo_code = 0x0054b210
buf[fo_code : fo_code + len(raw_strategy)] = raw_strategy
buf[fo_code + 0x1b0 : fo_code + 0x1b0 + len(raw_open)] = raw_open
buf[fo_code + 0x1b8 : fo_code + 0x1b8 + len(raw_close)] = raw_close
buf[fo_code + 0x1c0 : fo_code + 0x1c0 + len(raw_ioctl)] = raw_ioctl
buf[fo_code + 0x1c8 : fo_code + 0x1c8 + len(raw_psize)] = raw_psize

print('Code written into padding region!')

# Populate bdevsw slots 0 and 1
# VA: 0xfffffff007ca0f88 (fo 0xc9cf88)
# struct bdevsw:
# +00: d_open     (0x200054f3c0)
# +08: d_close    (0x200054f3c8)
# +10: d_strategy (0x200054f210)
# +18: d_ioctl    (0x200054f3d0)
# +20: d_dump     (0x200054f3c0)
# +28: d_psize    (0x200054f3d8)
# +30: d_type     (2)
slot_data = struct.pack('<QQQQQQQ',
    0x200054f3c0,
    0x200054f3c8,
    0x200054f210,
    0x200054f3d0,
    0x200054f3c0,
    0x200054f3d8,
    2
)

fo_bdevsw = 0xc9cf88
buf[fo_bdevsw : fo_bdevsw + 0x38] = slot_data # Slot 0
buf[fo_bdevsw + 0x38 : fo_bdevsw + 0x70] = slot_data # Slot 1

print('bdevsw slots 0 and 1 populated!')

with open('xnu_arm64_bdev_final.macho', 'wb') as f:
    f.write(buf)

print('Saved xnu_arm64_bdev_final.macho!')
