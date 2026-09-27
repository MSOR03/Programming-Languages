# -*- coding: utf-8 -*-
"""ORINOCO-32  (fabricante: Orinoco Systems S.A.)

Máquina de pila (cero direcciones), palabra de 32 bits, memoria de 8 KB direccionable por
byte y ordenada en little-endian (bus de direcciones de 13 bits). Las operaciones toman sus
operandos de la cima de una pila de datos de 32 entradas implementada en registros internos;
las direcciones de retorno van a una pila de retorno separada de 16 entradas.

Instrucciones de longitud variable (opcode de 8 bits):
    1 byte   opcode                         (la mayoría: ADD, DUP, SEND, ...)
    2 bytes  opcode + inm8 con signo        (PUSHB)
    3 bytes  opcode + dir16 little-endian   (JMP, JZ, JNZ, CALL)
    5 bytes  opcode + inm32 little-endian   (PUSH)

Registros: PC (13), SP de datos (5), RSP de retorno (4), IR (hasta 40 bits).
Banderas: O (desbordamiento aritmético), E (error de pila).
NIC: SEND ( dir n -- ) transmite n bytes;  RECV ( dir -- n ) recibe un paquete (0 si no hay).

Lenguaje ensamblador de Orinoco Systems (estilo Forth, en minúsculas):
    fact:   dup pushb 1 gt jz fin  ...   ; comentario
            .org 0x100   .word 7   .bytes 10
"""

import re
from collections import deque

M32 = 0xFFFFFFFF
TAM = 8192

# nemonico: (opcode, bytes de operando)
ISA = {
    'nop': (0x00, 0), 'halt': (0x01, 0),
    'push': (0x10, 4), 'pushb': (0x11, 1), 'dup': (0x12, 0), 'drop': (0x13, 0),
    'swap': (0x14, 0), 'over': (0x15, 0), 'rot': (0x16, 0),
    'add': (0x20, 0), 'sub': (0x21, 0), 'mul': (0x22, 0), 'div': (0x23, 0),
    'mod': (0x24, 0), 'neg': (0x25, 0), 'and': (0x28, 0), 'or': (0x29, 0),
    'xor': (0x2A, 0), 'not': (0x2B, 0), 'shl': (0x2C, 0), 'shr': (0x2D, 0),
    'eq': (0x30, 0), 'lt': (0x31, 0), 'gt': (0x32, 0),
    'jmp': (0x40, 2), 'jz': (0x41, 2), 'jnz': (0x42, 2), 'call': (0x43, 2), 'ret': (0x44, 0),
    'load': (0x50, 0), 'store': (0x51, 0), 'loadb': (0x52, 0), 'storeb': (0x53, 0),
    'in': (0x60, 0), 'out': (0x61, 0), 'outc': (0x62, 0),
    'send': (0x70, 0), 'recv': (0x71, 0), 'bswap': (0x72, 0),
}
POR_CODIGO = {c: (n, k) for n, (c, k) in ISA.items()}


class ErrorOrinoco(Exception):
    pass


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


class Orinoco32:
    FABRICANTE = 'Orinoco Systems S.A.'
    MODELO = 'ORINOCO-32'
    PALABRA = 32

    def __init__(self):
        self.mem = bytearray(TAM)
        self.salida = []
        self.enviar = None
        self.rx = deque()
        self.reiniciar()

    def reiniciar(self, pc=0):
        self.pila, self.ret = [], []
        self.pc, self.ir = pc, 0
        self.O = self.E = 0
        self.detenida = False
        self.instrucciones = 0

    # -- pila ----------------------------------------------------------------
    def _push(self, v):
        if len(self.pila) >= 32:
            self.E = 1
            raise ErrorOrinoco('desbordamiento de la pila de datos')
        self.pila.append(v & M32)

    def _pop(self):
        if not self.pila:
            self.E = 1
            raise ErrorOrinoco('pila de datos vacía (PC=%04X)' % self.pc)
        return self.pila.pop()

    def _l32(self, d):
        return int.from_bytes(self.mem[d % TAM:d % TAM + 4], 'little')

    def paso(self):
        if self.detenida:
            return False
        op = self.mem[self.pc]
        if op not in POR_CODIGO:
            raise ErrorOrinoco('opcode inválido %02X en %04X' % (op, self.pc))
        nombre, k = POR_CODIGO[op]
        arg = int.from_bytes(self.mem[self.pc + 1:self.pc + 1 + k], 'little') if k else 0
        self.ir = int.from_bytes(self.mem[self.pc:self.pc + 1 + k], 'big')
        self.pc = (self.pc + 1 + k) % TAM
        self.instrucciones += 1
        P, Q = self._push, self._pop
        if nombre == 'halt':
            self.detenida = True
        elif nombre == 'push':
            P(arg)
        elif nombre == 'pushb':
            P(arg - 256 if arg & 0x80 else arg)
        elif nombre == 'dup':
            v = Q(); P(v); P(v)
        elif nombre == 'drop':
            Q()
        elif nombre == 'swap':
            b, a = Q(), Q(); P(b); P(a)
        elif nombre == 'over':
            b, a = Q(), Q(); P(a); P(b); P(a)
        elif nombre == 'rot':
            c, b, a = Q(), Q(), Q(); P(b); P(c); P(a)
        elif nombre in ('add', 'sub', 'mul', 'div', 'mod', 'and', 'or', 'xor',
                        'shl', 'shr', 'eq', 'lt', 'gt'):
            b, a = Q(), Q()
            sa, sb = s32(a), s32(b)
            if nombre == 'add':
                r = sa + sb
            elif nombre == 'sub':
                r = sa - sb
            elif nombre == 'mul':
                r = sa * sb
            elif nombre in ('div', 'mod'):
                if sb == 0:
                    raise ErrorOrinoco('división por cero')
                q = abs(sa) // abs(sb) * (1 if (sa >= 0) == (sb >= 0) else -1)
                r = q if nombre == 'div' else sa - q * sb
            elif nombre == 'and':
                r = a & b
            elif nombre == 'or':
                r = a | b
            elif nombre == 'xor':
                r = a ^ b
            elif nombre == 'shl':
                r = (a << b) & M32
            elif nombre == 'shr':
                r = a >> b
            elif nombre == 'eq':
                r = int(a == b)
            elif nombre == 'lt':
                r = int(sa < sb)
            else:
                r = int(sa > sb)
            if nombre in ('add', 'sub', 'mul'):
                self.O = 1 if not -2 ** 31 <= r < 2 ** 31 else self.O
            P(r)
        elif nombre == 'neg':
            P(-s32(Q()))
        elif nombre == 'not':
            P(~Q())
        elif nombre == 'jmp':
            self.pc = arg
        elif nombre == 'jz':
            if Q() == 0:
                self.pc = arg
        elif nombre == 'jnz':
            if Q() != 0:
                self.pc = arg
        elif nombre == 'call':
            if len(self.ret) >= 16:
                raise ErrorOrinoco('desbordamiento de la pila de retorno')
            self.ret.append(self.pc)
            self.pc = arg
        elif nombre == 'ret':
            self.pc = self.ret.pop()
        elif nombre == 'load':
            P(self._l32(Q()))
        elif nombre == 'store':
            d, v = Q(), Q()
            self.mem[d % TAM:d % TAM + 4] = (v & M32).to_bytes(4, 'little')
        elif nombre == 'loadb':
            P(self.mem[Q() % TAM])
        elif nombre == 'storeb':
            d, v = Q(), Q()
            self.mem[d % TAM] = v & 0xFF
        elif nombre == 'out':
            self.salida.append(str(s32(Q())))
        elif nombre == 'outc':
            self.salida.append(chr(Q() & 0xFF))
        elif nombre == 'in':
            P(0)
        elif nombre == 'bswap':
            P(int.from_bytes((Q() & M32).to_bytes(4, 'little'), 'big'))
        elif nombre == 'send':
            n, d = Q(), Q()
            if self.enviar:
                self.enviar(bytes(self.mem[d:d + n]))
        elif nombre == 'recv':
            d = Q()
            if self.rx:
                datos = self.rx.popleft()
                self.mem[d:d + len(datos)] = datos
                P(len(datos))
            else:
                P(0)
        return not self.detenida

    def estado(self):
        return 'PC=%04X pila=%s O=%d' % (self.pc, [s32(v) for v in self.pila[-4:]], self.O)

    def cargar_fuente(self, ruta):
        imagen, simbolos = ensamblar(ruta)
        for d, b in imagen.items():
            self.mem[d] = b
        self.reiniciar(simbolos.get('inicio', 0))
        return len(imagen)


def ensamblar(ruta):
    tokens = []                       # (num_linea, token)
    with open(ruta, encoding='utf-8') as f:
        for num, cruda in enumerate(f, 1):
            for t in cruda.split(';', 1)[0].split():
                tokens.append((num, t))
    simbolos = {}
    for pasada in (1, 2):
        imagen, pc, i = {}, 0, 0
        while i < len(tokens):
            num, t = tokens[i]
            i += 1
            try:
                if t.endswith(':'):
                    if pasada == 1:
                        simbolos[t[:-1]] = pc
                    continue
                if t == '.org':
                    pc = _valor(tokens[i][1], simbolos, pasada)
                    i += 1
                    continue
                if t == '.word':
                    v = _valor(tokens[i][1], simbolos, pasada)
                    i += 1
                    for k, b in enumerate((v & M32).to_bytes(4, 'little')):
                        imagen[pc + k] = b
                    pc += 4
                    continue
                if t == '.bytes':
                    pc += _valor(tokens[i][1], simbolos, pasada)
                    i += 1
                    continue
                if t not in ISA:
                    raise ErrorOrinoco('instrucción desconocida "%s"' % t)
                op, k = ISA[t]
                imagen[pc] = op
                if k:
                    v = _valor(tokens[i][1], simbolos, pasada)
                    i += 1
                    for j, b in enumerate((v & ((1 << (8 * k)) - 1)).to_bytes(k, 'little')):
                        imagen[pc + 1 + j] = b
                pc += 1 + k
            except (ErrorOrinoco, IndexError, KeyError, ValueError) as e:
                raise ErrorOrinoco('%s:%d: %s' % (ruta, num, e))
    return imagen, simbolos


def _valor(t, simbolos, pasada):
    if re.fullmatch(r'-?(0x[0-9a-fA-F]+|\d+)', t):
        return int(t, 0)
    if t.startswith("'") and len(t) == 3:
        return ord(t[1])
    if pasada == 1:
        return 0
    return simbolos[t]
