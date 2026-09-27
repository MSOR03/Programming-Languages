# -*- coding: utf-8 -*-
"""CARIBE-16  (fabricante: Compañía Caribeña de Calculadoras, "CCC")

Máquina de acumulador, palabra de 16 bits, memoria de 1024 palabras direccionable por
palabra (bus de direcciones de 10 bits). Instrucción de longitud fija de 16 bits:

      15      11 10  9                  0
     +----------+---+--------------------+
     |  opcode  | M |     operando       |      M = 0 directo, M = 1 inmediato
     +----------+---+--------------------+

Registros: ACC (16), X índice (16), PC (10), IR (16).  Banderas: Z, N, C.
No tiene multiplicación ni pila: las subrutinas se llaman con JSR (guarda el retorno en la
primera palabra de la subrutina, como el PDP-8) y se retorna con JMI (salto indirecto).
NIC de 8 bits: transmite el byte bajo de cada palabra del búfer.

Lenguaje ensamblador (sintaxis propia de la CCC):
    etiqueta:  LDA  #5        ; inmediato
               ADD  var       ; directo
               LDAX tabla     ; indexado: M[tabla + X]
               ORG 100 / WORD 7 / SPACE 10
"""

import re
from collections import deque

M16 = 0xFFFF
TAM = 1024

# nemonico: (opcode, admite_inmediato)
ISA = {
    'HLT': (0, False),  'LDA': (1, True),   'STA': (2, False),  'ADD': (3, True),
    'SUB': (4, True),   'AND': (5, True),   'OR': (6, True),    'XOR': (7, True),
    'SHL': (8, True),   'SHR': (9, True),   'LDX': (10, True),  'STX': (11, False),
    'ADX': (12, True),  'LDAX': (13, False), 'STAX': (14, False), 'JMP': (15, False),
    'JZ': (16, False),  'JNZ': (17, False), 'JN': (18, False),  'JC': (19, False),
    'JSR': (20, False), 'JMI': (21, False), 'CMP': (22, True),  'IN': (23, False),
    'OUT': (24, True),  'NSND': (25, False), 'NRCV': (26, False), 'NOP': (27, False),
    'ADC': (28, True),  'CPX': (29, True),  'TAX': (30, False), 'TXA': (31, False),
}
SIN_OPERANDO = {'HLT', 'NOP', 'TAX', 'TXA', 'IN'}
POR_CODIGO = {c: n for n, (c, _) in ISA.items()}


class ErrorCaribe(Exception):
    pass


class Caribe16:
    FABRICANTE = 'Compañía Caribeña de Calculadoras (CCC)'
    MODELO = 'CARIBE-16'
    PALABRA = 16

    def __init__(self):
        self.mem = [0] * TAM
        self.salida = []
        self.enviar = None                 # lo conecta la red
        self.rx = deque()
        self.reiniciar()

    def reiniciar(self, pc=0):
        self.acc = self.x = 0
        self.pc, self.ir = pc, 0
        self.Z = self.N = self.C = 0
        self.detenida = False
        self.instrucciones = 0

    def _banderas(self, v):
        self.Z = 1 if v == 0 else 0
        self.N = (v >> 15) & 1

    def paso(self):
        if self.detenida:
            return False
        self.ir = w = self.mem[self.pc]
        op, m, arg = w >> 11, (w >> 10) & 1, w & 0x3FF
        self.pc = (self.pc + 1) % TAM
        self.instrucciones += 1
        nombre = POR_CODIGO[op]
        val = arg if m else self.mem[arg]
        if nombre == 'HLT':
            self.detenida = True
        elif nombre == 'LDA':
            self.acc = val
            self._banderas(self.acc)
        elif nombre == 'STA':
            self.mem[arg] = self.acc
        elif nombre in ('ADD', 'ADC'):
            t = self.acc + val + (self.C if nombre == 'ADC' else 0)
            self.C = 1 if t > M16 else 0
            self.acc = t & M16
            self._banderas(self.acc)
        elif nombre in ('SUB', 'CMP'):
            t = self.acc - val
            self.C = 1 if t < 0 else 0
            self._banderas(t & M16)
            if nombre == 'SUB':
                self.acc = t & M16
        elif nombre == 'AND':
            self.acc &= val
            self._banderas(self.acc)
        elif nombre == 'OR':
            self.acc |= val
            self._banderas(self.acc)
        elif nombre == 'XOR':
            self.acc ^= val
            self._banderas(self.acc)
        elif nombre == 'SHL':
            self.C = (self.acc >> (16 - val)) & 1 if 0 < val <= 16 else 0
            self.acc = (self.acc << val) & M16
            self._banderas(self.acc)
        elif nombre == 'SHR':
            self.C = (self.acc >> (val - 1)) & 1 if val > 0 else 0
            self.acc >>= val
            self._banderas(self.acc)
        elif nombre == 'LDX':
            self.x = val
        elif nombre == 'STX':
            self.mem[arg] = self.x
        elif nombre == 'ADX':
            self.x = (self.x + val) & M16
        elif nombre == 'CPX':
            t = self.x - val
            self.C = 1 if t < 0 else 0
            self._banderas(t & M16)
        elif nombre == 'LDAX':
            self.acc = self.mem[(arg + self.x) % TAM]
            self._banderas(self.acc)
        elif nombre == 'STAX':
            self.mem[(arg + self.x) % TAM] = self.acc
        elif nombre == 'JMP':
            self.pc = arg
        elif nombre == 'JZ':
            self.pc = arg if self.Z else self.pc
        elif nombre == 'JNZ':
            self.pc = arg if not self.Z else self.pc
        elif nombre == 'JN':
            self.pc = arg if self.N else self.pc
        elif nombre == 'JC':
            self.pc = arg if self.C else self.pc
        elif nombre == 'JSR':
            self.mem[arg] = self.pc
            self.pc = (arg + 1) % TAM
        elif nombre == 'JMI':
            self.pc = self.mem[arg] % TAM
        elif nombre == 'TAX':
            self.x = self.acc
        elif nombre == 'TXA':
            self.acc = self.x
            self._banderas(self.acc)
        elif nombre == 'OUT':
            v = self.acc
            self.salida.append(chr(v & 0xFF) if val == 1 else str(v - 0x10000 if v & 0x8000 else v))
        elif nombre == 'IN':
            self.acc = 0
        elif nombre == 'NSND':
            n = self.acc
            datos = bytes(self.mem[(arg + i) % TAM] & 0xFF for i in range(n))
            if self.enviar:
                self.enviar(datos)
        elif nombre == 'NRCV':
            if self.rx:
                datos = self.rx.popleft()
                for i, b in enumerate(datos):
                    self.mem[(arg + i) % TAM] = b
                self.acc = len(datos)
            else:
                self.acc = 0
            self._banderas(self.acc)
        return not self.detenida

    def estado(self):
        return 'ACC=%04X X=%04X PC=%03X Z=%d N=%d C=%d' % (self.acc, self.x, self.pc, self.Z, self.N, self.C)

    # ------------------------------------------------------------------ ensamblador
    def cargar_fuente(self, ruta):
        codigo, simbolos = ensamblar(ruta)
        for d, w in codigo.items():
            self.mem[d] = w
        self.reiniciar(simbolos.get('inicio', 0))
        return len(codigo)


def ensamblar(ruta):
    lineas = []
    with open(ruta, encoding='utf-8') as f:
        for num, cruda in enumerate(f, 1):
            t = cruda.split(';', 1)[0].strip()
            if t:
                lineas.append((num, t))
    simbolos, pc = {}, 0

    def partir(t):
        etq = None
        m = re.match(r'^(\w+):\s*(.*)$', t)
        if m:
            etq, t = m.group(1), m.group(2)
        p = t.split(None, 1)
        return etq, (p[0].upper() if p else None), (p[1].strip() if len(p) > 1 else '')

    for num, t in lineas:                            # pasada 1
        etq, nem, arg = partir(t)
        if nem == 'EQU':
            simbolos[etq] = _num(arg, simbolos)
            continue
        if etq:
            simbolos[etq] = pc
        if nem == 'ORG':
            pc = _num(arg, simbolos)
        elif nem == 'SPACE':
            pc += _num(arg, simbolos)
        elif nem:
            pc += 1
    codigo, pc = {}, 0
    for num, t in lineas:                            # pasada 2
        etq, nem, arg = partir(t)
        try:
            if nem is None or nem == 'EQU':
                continue
            if nem == 'ORG':
                pc = _num(arg, simbolos)
                continue
            if nem == 'SPACE':
                pc += _num(arg, simbolos)
                continue
            if nem == 'WORD':
                codigo[pc] = _num(arg, simbolos) & M16
            else:
                if nem not in ISA:
                    raise ErrorCaribe('nemónico desconocido %s' % nem)
                op, admite = ISA[nem]
                m = 0
                if nem in SIN_OPERANDO:
                    v = 0
                else:
                    if arg.startswith('#'):
                        if not admite:
                            raise ErrorCaribe('%s no admite modo inmediato' % nem)
                        m, arg = 1, arg[1:]
                    v = _num(arg, simbolos)
                    if not 0 <= v < TAM:
                        raise ErrorCaribe('operando fuera de rango (0..1023): %d' % v)
                codigo[pc] = (op << 11) | (m << 10) | v
            pc += 1
        except (ErrorCaribe, KeyError, ValueError) as e:
            raise ErrorCaribe('%s:%d: %s' % (ruta, num, e))
    return codigo, simbolos


def _num(t, simbolos):
    total = 0
    for signo, tok in re.findall(r'([+-]?)\s*([^+\-\s]+)', t):
        if tok.startswith("'"):
            v = ord(tok[1])
        elif re.fullmatch(r'0x[0-9a-fA-F]+|\d+', tok):
            v = int(tok, 0)
        else:
            v = simbolos[tok]
        total += -v if signo == '-' else v
    return total
