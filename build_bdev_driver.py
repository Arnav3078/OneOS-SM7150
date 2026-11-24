
import struct, capstone

# Encoders
def sub_sp_sp(imm): return 0xd1000000 | ((imm & 0xfff) << 10) | (31 << 5) | 31
def add_sp_sp(imm): return 0x91000000 | ((imm & 0xfff) << 10) | (31 << 5) | 31
def add_reg_sp(xd, imm): return 0x91000000 | ((imm & 0xfff) << 10) | (31 << 5) | xd
def add_reg_reg(xd, xn, xm): return 0x8b000000 | (xm << 16) | (xn << 5) | xd
def add_reg_reg_uxtw(xd, xn, wm): return 0x8b204000 | (wm << 16) | (xn << 5) | xd
def add_reg_reg_lsr(xd, xn, xm, shift): return 0x8b400000 | ((shift & 0x3f) << 10) | (xm << 16) | (xn << 5) | xd
def add_reg_imm(xd, xn, imm): return 0x91000000 | ((imm & 0xfff) << 10) | (xn << 5) | xd
def sub_reg_reg(wd, wn, wm): return 0x4b000000 | (wm << 16) | (wn << 5) | wd
def lsr_reg_imm(xd, xn, shift): return 0xd340fc00 | ((shift & 0x3f) << 16) | (xn << 5) | xd

def stp(rt1, rt2, rn, imm): return 0xa9000000 | (((imm >> 3) & 0x7f) << 15) | (rt2 << 10) | (rn << 5) | rt1
def ldp(rt1, rt2, rn, imm): return 0xa9400000 | (((imm >> 3) & 0x7f) << 15) | (rt2 << 10) | (rn << 5) | rt1
def str_reg(rt, rn, imm): return 0xf9000000 | (((imm >> 3) & 0x1ff) << 10) | (rn << 5) | rt
def str_wreg(wt, rn, imm): return 0xb9000000 | (((imm >> 2) & 0x1ff) << 10) | (rn << 5) | wt
def ldr_wreg(wt, rn, imm): return 0xb9400000 | (((imm >> 2) & 0x1ff) << 10) | (rn << 5) | wt
def ldr_reg(rt, rn, imm): return 0xf9400000 | (((imm >> 3) & 0x1ff) << 10) | (rn << 5) | rt
def ldr_reg_uxtw3(rt, rn, wm): return 0xf8605800 | (wm << 16) | (rn << 5) | rt
def ldrb_reg(rt, rn, imm): return 0x39400000 | ((imm & 0xfff) << 10) | (rn << 5) | rt

def mov_reg(xd, xm): return 0xaa0003e0 | (xm << 16) | xd
def mov_wreg(wd, wm): return 0x2a0003e0 | (wm << 16) | wd
def mov_wimm(wd, imm): return 0x52800000 | ((imm & 0xffff) << 5) | wd
def movk_wimm(wd, imm, lsl): return 0x72800000 | ((lsl // 16) << 21) | ((imm & 0xffff) << 5) | wd
def mov_ximm(xd, imm): return 0xd2800000 | ((imm & 0xffff) << 5) | xd
def movk_ximm(xd, imm, lsl): return 0xf2800000 | ((lsl // 16) << 21) | ((imm & 0xffff) << 5) | xd

def cmp_reg(wn, wm): return 0x6b00001f | (wm << 16) | (wn << 5)
def cmp_wimm(wn, imm): return 0x7100001f | ((imm & 0xfff) << 10) | (wn << 5)
def csel_w_lo(wd, wn, wm): return 0x1a803000 | (wm << 16) | (wn << 5) | wd
def csel_lo(xd, xn, xm): return 0x9a803000 | (xm << 16) | (xn << 5) | xd

def ret(): return 0xd65f03c0
def nop(): return 0xd503201f

def adrp(xd, pc, target_page):
    pc_page = pc & ~0xfff
    imm = (target_page - pc_page) >> 12
    immlo = imm & 3
    immhi = (imm >> 2) & 0x7ffff
    return 0x90000000 | (immlo << 29) | (immhi << 5) | xd

def bl(pc, target):
    offset = (target - pc) >> 2
    return 0x94000000 | (offset & 0x03ffffff)

def b(pc, target):
    offset = (target - pc) >> 2
    return 0x14000000 | (offset & 0x03ffffff)

def b_eq(pc, target):
    offset = (target - pc) >> 2
    return 0x54000000 | ((offset & 0x7ffff) << 5)

def b_ne(pc, target):
    offset = (target - pc) >> 2
    return 0x54000001 | ((offset & 0x7ffff) << 5)

def b_hs(pc, target):
    offset = (target - pc) >> 2
    return 0x54000002 | ((offset & 0x7ffff) << 5)

def b_lo(pc, target):
    offset = (target - pc) >> 2
    return 0x54000003 | ((offset & 0x7ffff) << 5)

def cbz(xn, pc, target):
    offset = (target - pc) >> 2
    return 0xb4000000 | ((offset & 0x7ffff) << 5) | xn

def cbz_w(wn, pc, target):
    offset = (target - pc) >> 2
    return 0x34000000 | ((offset & 0x7ffff) << 5) | wn

def cbnz(xn, pc, target):
    offset = (target - pc) >> 2
    return 0xb5000000 | ((offset & 0x7ffff) << 5) | xn

def cbnz_w(wn, pc, target):
    offset = (target - pc) >> 2
    return 0x35000000 | ((offset & 0x7ffff) << 5) | wn

def tbz(wn, bit, pc, target):
    offset = (target - pc) >> 2
    return 0x36000000 | ((bit & 0x1f) << 19) | ((offset & 0x3fff) << 5) | wn

print('Encoders defined!')

class Assembler:
    def __init__(self, base_va):
        self.base_va = base_va
        self.labels = {}
        self.instructions = []

    def label(self, name):
        self.instructions.append(('label', name))

    def emit(self, fn, *args):
        self.instructions.append(('insn', fn, args))

    def assemble(self):
        # Pass 1: find label addresses
        pc = self.base_va
        for item in self.instructions:
            if item[0] == 'label':
                self.labels[item[1]] = pc
            else:
                pc += 4

        # Pass 2: encode instructions
        pc = self.base_va
        opcodes = []
        for item in self.instructions:
            if item[0] == 'label':
                continue
            fn, args = item[1], item[2]
            # Replace string labels with actual target addresses
            resolved_args = []
            for a in args:
                if isinstance(a, str) and a in self.labels:
                    resolved_args.append(self.labels[a])
                else:
                    resolved_args.append(a)
            # Some encoders take pc as first or second arg
            # We call fn(pc, *resolved_args) or fn(*resolved_args)
            try:
                op = fn(pc, *resolved_args)
            except TypeError:
                op = fn(*resolved_args)
            opcodes.append((pc, op))
            pc += 4
        return opcodes

print('Assembler class ready')
