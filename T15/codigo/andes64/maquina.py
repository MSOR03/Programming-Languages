# -*- coding: utf-8 -*-
"""Emulador del computador de 64 bits (Tareas 9 y 10): CPU, jerarquía de memoria,
periféricos de E/S y tarjeta de red. Solo usa la biblioteca estándar de Python."""

import struct
from collections import deque

import isa

MASK = (1 << 64) - 1
BIT63 = 1 << 63
TAM_RAM = 4096           # 4 KB, bus de direcciones de 12 bits
CICLOS = {'L1': 1, 'L2': 5, 'RAM': 20}


class ErrorCPU(Exception):
    pass


def con_signo(v):
    return v - (1 << 64) if v & BIT63 else v


def bits_a_real(v):
    return struct.unpack('>d', v.to_bytes(8, 'big'))[0]


def real_a_bits(x):
    return int.from_bytes(struct.pack('>d', x), 'big')


# ----------------------------------------------------------------------------- memoria
class Cache:
    """Caché de correspondencia directa con líneas de 8 bytes (solo lleva etiquetas y
    estadísticas: los datos siempre están actualizados en RAM, escritura inmediata)."""

    def __init__(self, nombre, lineas):
        self.nombre, self.lineas = nombre, lineas
        self.etiquetas = [None] * lineas
        self.aciertos = self.fallos = 0

    def buscar(self, bloque):
        i = bloque % self.lineas
        if self.etiquetas[i] == bloque:
            self.aciertos += 1
            return True
        self.fallos += 1
        return False

    def llenar(self, bloque):
        self.etiquetas[bloque % self.lineas] = bloque

    def reiniciar(self):
        self.etiquetas = [None] * self.lineas
        self.aciertos = self.fallos = 0


class Memoria:
    """Registros -> L1 (128 B) -> L2 (512 B) -> RAM (4 KB) -> disco (archivos .obj)."""

    def __init__(self):
        self.ram = bytearray(TAM_RAM)
        self.l1 = Cache('L1', 16)     # 16 líneas x 8 B = 128 B
        self.l2 = Cache('L2', 64)     # 64 líneas x 8 B = 512 B
        self.ciclos = 0
        self.al_escribir = None       # aviso para invalidar instrucciones predecodificadas

    def _verificar(self, d, n):
        if d < 0 or d + n > TAM_RAM:
            raise ErrorCPU('acceso fuera de la RAM: 0x%03X (+%d)' % (d, n))

    def _jerarquia(self, d, n):
        for b in range(d >> 3, ((d + n - 1) >> 3) + 1):
            if self.l1.buscar(b):
                self.ciclos += CICLOS['L1']
            elif self.l2.buscar(b):
                self.ciclos += CICLOS['L2']
                self.l1.llenar(b)
            else:
                self.ciclos += CICLOS['RAM']
                self.l2.llenar(b)
                self.l1.llenar(b)

    def leer(self, d, n):
        self._verificar(d, n)
        self._jerarquia(d, n)
        return int.from_bytes(self.ram[d:d + n], 'big')

    def escribir(self, d, n, valor):
        self._verificar(d, n)
        self._jerarquia(d, n)
        self.ram[d:d + n] = (valor & ((1 << (8 * n)) - 1)).to_bytes(n, 'big')
        if self.al_escribir:
            self.al_escribir(d, n)

    def poner_bit(self, d, bit, valor):
        """Escritura directa de un bit (bit 7 = más significativo del byte)."""
        self._verificar(d, 1)
        if valor:
            self.ram[d] |= (1 << bit)
        else:
            self.ram[d] &= ~(1 << bit) & 0xFF
        if self.al_escribir:
            self.al_escribir(d, 1)


# ----------------------------------------------------------------------------- periféricos
class Perifericos:
    """Periférico de entrada (cola de valores o teclado) y de salida (pantalla/búfer)."""

    def __init__(self, entradas=None, eco=True, interactivo=False):
        self.entrada = deque(entradas or [])
        self.salida = []
        self.eco = eco
        self.interactivo = interactivo

    def leer(self, modo):
        if not self.entrada:
            if not self.interactivo:
                raise ErrorCPU('IN: el periférico de entrada no tiene datos')
            self.entrada.append(input('IN> '))
        t = str(self.entrada.popleft()).strip()
        if modo == 0:
            return int(t, 0) & MASK
        if modo == 1:
            return int(t, 16) & MASK
        if modo == 2:
            return ord(t[0]) if t else 10
        return real_a_bits(float(t))

    def escribir(self, valor, modo):
        if modo == 0:
            s = str(con_signo(valor))
        elif modo == 1:
            s = '%016X' % valor
        elif modo == 2:
            s = chr(valor & 0xFF)
        else:
            s = repr(bits_a_real(valor))
        self.salida.append(s)
        if self.eco:
            print(s, end='', flush=True)

    def texto(self):
        return ''.join(self.salida)


class NIC:
    """Tarjeta de red. Aislada, funciona como lazo local (lo que se envía se puede recibir);
    conectada a una red, `enlace` es una función que entrega la trama al medio."""

    def __init__(self):
        self.recibidas = deque()
        self.enviadas = []
        self.enlace = None

    def enviar(self, datos):
        self.enviadas.append(bytes(datos))
        if self.enlace:
            self.enlace(bytes(datos))
        else:
            self.recibidas.append(bytes(datos))


# ----------------------------------------------------------------------------- CPU
class CPU:
    def __init__(self, entradas=None, eco=True, interactivo=False):
        self.mem = Memoria()
        self.mem.al_escribir = self._invalidar
        self.es = Perifericos(entradas, eco, interactivo)
        self.nic = NIC()
        self.reiniciar()

    # -- estado --------------------------------------------------------------
    def reiniciar(self, pc=0):
        self.R = [0] * 16
        self.R[13] = TAM_RAM          # SP: la pila crece hacia abajo desde el tope de la RAM
        self.pc = pc
        self.Z = self.N = self.C = self.V = 0
        self.I = 0
        self.int_en = 0
        self.ir = 0
        self.detenida = False
        self.instrucciones = 0
        self.predecod = {}
        self.mem.ciclos = 0
        self.mem.l1.reiniciar()
        self.mem.l2.reiniciar()

    @property
    def fr(self):
        return self.Z | (self.N << 1) | (self.C << 2) | (self.V << 3) | (self.I << 4)

    def _invalidar(self, d, n):
        for p in range(d - 4, d + n):
            self.predecod.pop(p, None)

    # -- utilidades de banderas ---------------------------------------------
    def _zn(self, r):
        self.Z = 1 if r == 0 else 0
        self.N = r >> 63

    def _suma(self, a, b, c=0):
        t = a + b + c
        r = t & MASK
        self.C = 1 if t > MASK else 0
        self.V = 1 if (~(a ^ b) & (a ^ r)) & BIT63 else 0
        self._zn(r)
        return r

    def _resta(self, a, b, c=0):
        r = (a - b - c) & MASK
        self.C = 1 if a < b + c else 0           # préstamo
        self.V = 1 if ((a ^ b) & (a ^ r)) & BIT63 else 0
        self._zn(r)
        return r

    def _logica(self, r):
        self.C = self.V = 0
        self._zn(r)
        return r

    def _shl(self, a, n):
        if n == 0:
            self._zn(a)
            return a
        r = (a << n) & MASK if n < 64 else 0
        self.C = (a >> (64 - n)) & 1 if n <= 64 else 0
        self.V = 0
        self._zn(r)
        return r

    def _shr(self, a, n):
        if n == 0:
            self._zn(a)
            return a
        r = a >> n if n < 64 else 0
        self.C = (a >> (n - 1)) & 1 if n <= 64 else 0
        self.V = 0
        self._zn(r)
        return r

    def _sar(self, a, n):
        s = con_signo(a)
        if n == 0:
            self._zn(a)
            return a
        r = (s >> min(n, 63)) & MASK
        self.C = (s >> (min(n, 64) - 1)) & 1
        self.V = 0
        self._zn(r)
        return r

    def _cond(self, nombre):
        Z, N, C, V = self.Z, self.N, self.C, self.V
        return {
            'JMP': True, 'CALL': True,
            'JZ': Z, 'JNZ': not Z, 'JC': C, 'JNC': not C, 'JN': N, 'JNN': not N,
            'JV': V, 'JNV': not V, 'JL': N != V, 'JGE': N == V,
            'JG': (not Z) and N == V, 'JLE': Z or N != V,
            'JA': (not C) and (not Z), 'JBE': C or Z,
        }[nombre]

    def _push(self, v):
        self.R[13] = (self.R[13] - 8) & MASK
        self.mem.escribir(self.R[13], 8, v)

    def _pop(self):
        v = self.mem.leer(self.R[13], 8)
        self.R[13] = (self.R[13] + 8) & MASK
        return v

    # -- ciclo de instrucción ------------------------------------------------
    def buscar_decodificar(self, pc):
        """Fetch + Decode. Lee primero los 16 bits del opcode y con él la longitud."""
        op = self.mem.leer(pc, 2)
        if op not in isa.POR_OPCODE:
            raise ErrorCPU('opcode inválido 0x%04X en PC=0x%03X' % (op, pc))
        nombre, formato = isa.POR_OPCODE[op]
        n = isa.BYTES[formato]
        palabra = self.mem.leer(pc, n)
        self.ir = palabra
        return nombre, formato, n, isa.decodificar(formato, palabra)

    def paso(self):
        """Ejecuta una instrucción. Devuelve False si la CPU está detenida."""
        if self.detenida:
            return False
        pc = self.pc
        d = self.predecod.get(pc)
        if d is None:
            d = self.buscar_decodificar(pc)
            self.predecod[pc] = d
        else:
            self.mem._jerarquia(pc, d[2])      # el fetch igualmente pasa por las cachés
        nombre, formato, n, c = d
        self.pc = (pc + n) & 0xFFF
        self.instrucciones += 1
        self._ejecutar(nombre, formato, c)
        return not self.detenida

    def correr(self, max_instrucciones=None):
        limite = max_instrucciones or float('inf')
        while not self.detenida and self.instrucciones < limite:
            self.paso()
        return self.detenida

    def _ejecutar(self, op, f, c):
        R = self.R
        if f == 4:
            rd, a, b = c['rd'], R[c['rf1']], R[c['rf2']]
            if op == 'MOV':    R[rd] = a
            elif op == 'ADD':  R[rd] = self._suma(a, b)
            elif op == 'ADC':  R[rd] = self._suma(a, b, self.C)
            elif op == 'SUB':  R[rd] = self._resta(a, b)
            elif op == 'SBB':  R[rd] = self._resta(a, b, self.C)
            elif op == 'MUL':
                t = a * b
                R[rd] = t & MASK
                self.C = self.V = 1 if t > MASK else 0
                self._zn(R[rd])
            elif op in ('DIV', 'MOD', 'DIVU', 'MODU'):
                if b == 0:
                    raise ErrorCPU('división por cero')
                if op in ('DIVU', 'MODU'):
                    r = a // b if op == 'DIVU' else a % b
                else:
                    sa, sb = con_signo(a), con_signo(b)
                    q = abs(sa) // abs(sb)
                    q = q if (sa >= 0) == (sb >= 0) else -q
                    r = q if op == 'DIV' else sa - q * sb
                R[rd] = self._logica(r & MASK)
            elif op == 'AND':  R[rd] = self._logica(a & b)
            elif op == 'OR':   R[rd] = self._logica(a | b)
            elif op == 'XOR':  R[rd] = self._logica(a ^ b)
            elif op == 'SHL':  R[rd] = self._shl(a, b)
            elif op == 'SHR':  R[rd] = self._shr(a, b)
            elif op == 'SAR':  R[rd] = self._sar(a, b)
            elif op == 'CMP':  self._resta(a, b)
            elif op == 'TEST': self._logica(a & b)
            elif op == 'LDR':  R[rd] = self.mem.leer((a + b) & MASK, 8)
            elif op == 'STR':  self.mem.escribir((a + b) & MASK, 8, R[rd])
            elif op == 'LDRB': R[rd] = self.mem.leer((a + b) & MASK, 1)
            elif op == 'STRB': self.mem.escribir((a + b) & MASK, 1, R[rd])
        elif f == 6:
            rd, modo, inm = c['rd'], c['modo'], c['inm']
            v = inm | (MASK ^ 0xFFFF) if (modo == 1 and inm & 0x8000) else inm
            a = R[rd]
            if op == 'MOVI':   R[rd] = v
            elif op == 'MOVK':
                s = 16 * modo
                R[rd] = (a & ~(0xFFFF << s) & MASK) | (inm << s)
            elif op == 'ADDI': R[rd] = self._suma(a, v)
            elif op == 'SUBI': R[rd] = self._resta(a, v)
            elif op == 'MULI':
                t = a * v
                R[rd] = t & MASK
                self.C = self.V = 1 if t > MASK else 0
                self._zn(R[rd])
            elif op == 'ANDI': R[rd] = self._logica(a & v)
            elif op == 'ORI':  R[rd] = self._logica(a | v)
            elif op == 'XORI': R[rd] = self._logica(a ^ v)
            elif op == 'SHLI': R[rd] = self._shl(a, inm)
            elif op == 'SHRI': R[rd] = self._shr(a, inm)
            elif op == 'SARI': R[rd] = self._sar(a, inm)
            elif op == 'CMPI': self._resta(a, v)
        elif f == 3:
            if self._cond(op):
                if op == 'CALL':
                    self._push(self.pc)
                    R[14] = self.pc
                self.pc = c['dir']
        elif f == 2:
            r, modo = c['rd'], c['modo']
            if op == 'INC':    R[r] = self._suma(R[r], 1)
            elif op == 'DEC':  R[r] = self._resta(R[r], 1)
            elif op == 'NOT':  R[r] = self._logica(~R[r] & MASK)
            elif op == 'NEG':  R[r] = self._resta(0, R[r])
            elif op == 'CLR':  R[r] = self._logica(0)
            elif op == 'PUSH': self._push(R[r])
            elif op == 'POP':  R[r] = self._pop()
            elif op == 'IN':   R[r] = self.es.leer(modo)
            elif op == 'OUT':  self.es.escribir(R[r], modo)
            elif op == 'JR':   self.pc = R[r] & 0xFFF
        elif f == 5:
            r, modo, d = c['rd'], c['modo'], c['dir']
            if modo == isa.INDIRECTO:
                d = self.mem.leer(d, 8) & 0xFFF
            elif modo == isa.INDEXADO:
                d = (d + R[12]) & 0xFFF
            if op == 'LOAD':    R[r] = self.mem.leer(d, 8)
            elif op == 'STORE': self.mem.escribir(d, 8, R[r])
            elif op == 'LEA':   R[r] = d
            elif op == 'NSEND':
                n = R[r]
                self.nic.enviar(bytes(self.mem.ram[d:d + n]))
            elif op == 'NRECV':
                if self.nic.recibidas:
                    datos = self.nic.recibidas.popleft()
                    for i, b in enumerate(datos):
                        self.mem.escribir(d + i, 1, b)
                    R[r] = len(datos)
                else:
                    R[r] = 0
        else:  # F1
            if op == 'HLT':   self.detenida = True
            elif op == 'RET': self.pc = self._pop() & 0xFFF
            elif op == 'EI':  self.int_en = 1
            elif op == 'DI':  self.int_en = 0
            elif op == 'CLC': self.C = 0
            elif op == 'STC': self.C = 1
        R[13] &= MASK
        self.I = 1 if (self.es.entrada or self.nic.recibidas) else 0

    # -- presentación --------------------------------------------------------
    def estado(self):
        lineas = []
        for i in range(0, 16, 4):
            lineas.append('  '.join('R%-2d=%016X' % (j, self.R[j]) for j in range(i, i + 4)))
        lineas.append('PC=%03X  IR=%010X  SP=%03X  FR=%s  [Z=%d N=%d C=%d V=%d I=%d]  instr=%d'
                      % (self.pc, self.ir, self.R[13], format(self.fr, '08b'),
                         self.Z, self.N, self.C, self.V, self.I, self.instrucciones))
        return '\n'.join(lineas)

    def estadisticas(self):
        l1, l2 = self.mem.l1, self.mem.l2
        return ('instrucciones=%d  ciclos_memoria=%d  L1 %d/%d aciertos  L2 %d/%d aciertos'
                % (self.instrucciones, self.mem.ciclos, l1.aciertos, l1.aciertos + l1.fallos,
                   l2.aciertos, l2.aciertos + l2.fallos))
