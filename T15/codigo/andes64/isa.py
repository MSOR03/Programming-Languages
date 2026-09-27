# -*- coding: utf-8 -*-
"""Conjunto de instrucciones (ISA) del computador de 64 bits diseñado en la Tarea 9.

Formatos de microinstrucción (longitud variable, el opcode de 16 bits va siempre primero):

  F1  sin operando           opcode16                                   16 bits
  F2  un registro            opcode16 modo2 reg4                        24 bits (22 + 2 relleno)
  F3  salto / control        opcode16 dir12                             28 bits
  F4  registro-registro      opcode16 modos4 rd4 rf1_4 rf2_4            32 bits
  F5  acceso a memoria       opcode16 modo2 reg4 dir12                  36 bits (34 + 2 relleno)
  F6  operando inmediato     opcode16 modo2 rd4 inm16                   40 bits (38 + 2 relleno)

La memoria es direccionable por byte, así que cada instrucción ocupa ceil(bits/8) bytes y el
PC avanza exactamente esa cantidad (los bits de relleno no se interpretan).
El byte alto del opcode coincide con el número de formato: 0x01xx -> F1, ..., 0x06xx -> F6.
"""

BITS = {1: 16, 2: 24, 3: 28, 4: 32, 5: 36, 6: 40}
BYTES = {f: (b + 7) // 8 for f, b in BITS.items()}

# (nemonico, opcode, formato, descripcion)
INSTRUCCIONES = [
    # ---------------- F1: sin operando ----------------
    ('NOP',   0x0100, 1, 'No realiza ninguna operación'),
    ('HLT',   0x0101, 1, 'Detiene la CPU'),
    ('RET',   0x0102, 1, 'Retorno de subrutina: PC <- pop()'),
    ('EI',    0x0103, 1, 'Habilita interrupciones (INT_EN <- 1)'),
    ('DI',    0x0104, 1, 'Deshabilita interrupciones (INT_EN <- 0)'),
    ('CLC',   0x0105, 1, 'Borra la bandera de acarreo (C <- 0)'),
    ('STC',   0x0106, 1, 'Activa la bandera de acarreo (C <- 1)'),
    # ---------------- F2: un registro ----------------
    ('INC',   0x0200, 2, 'R <- R + 1'),
    ('DEC',   0x0201, 2, 'R <- R - 1'),
    ('NOT',   0x0202, 2, 'R <- ~R (complemento a uno)'),
    ('NEG',   0x0203, 2, 'R <- -R (complemento a dos)'),
    ('CLR',   0x0204, 2, 'R <- 0'),
    ('PUSH',  0x0205, 2, 'SP <- SP-8 ; M[SP] <- R'),
    ('POP',   0x0206, 2, 'R <- M[SP] ; SP <- SP+8'),
    ('IN',    0x0207, 2, 'R <- periférico de entrada (modo: D entero, H hex, C carácter, F real)'),
    ('OUT',   0x0208, 2, 'periférico de salida <- R (modo: D entero, H hex, C carácter, F real)'),
    ('JR',    0x0209, 2, 'Salto indirecto por registro: PC <- R'),
    # ---------------- F3: saltos ----------------
    ('JMP',   0x0300, 3, 'Salto incondicional'),
    ('JZ',    0x0301, 3, 'Salta si Z=1 (igual)'),
    ('JNZ',   0x0302, 3, 'Salta si Z=0 (distinto)'),
    ('JC',    0x0303, 3, 'Salta si C=1 (acarreo / menor sin signo)'),
    ('JNC',   0x0304, 3, 'Salta si C=0 (mayor o igual sin signo)'),
    ('JN',    0x0305, 3, 'Salta si N=1 (negativo)'),
    ('JNN',   0x0306, 3, 'Salta si N=0 (no negativo)'),
    ('JV',    0x0307, 3, 'Salta si V=1 (desbordamiento)'),
    ('JNV',   0x0308, 3, 'Salta si V=0'),
    ('JL',    0x0309, 3, 'Salta si menor con signo (N != V)'),
    ('JGE',   0x030A, 3, 'Salta si mayor o igual con signo (N == V)'),
    ('JG',    0x030B, 3, 'Salta si mayor con signo (Z=0 y N == V)'),
    ('JLE',   0x030C, 3, 'Salta si menor o igual con signo (Z=1 o N != V)'),
    ('JA',    0x030D, 3, 'Salta si mayor sin signo (C=0 y Z=0)'),
    ('JBE',   0x030E, 3, 'Salta si menor o igual sin signo (C=1 o Z=1)'),
    ('CALL',  0x030F, 3, 'Llamada: push(PC) ; R14 <- PC ; PC <- dir'),
    # ---------------- F4: registro-registro ----------------
    ('MOV',   0x0400, 4, 'Rd <- Rf1'),
    ('ADD',   0x0401, 4, 'Rd <- Rf1 + Rf2'),
    ('ADC',   0x0402, 4, 'Rd <- Rf1 + Rf2 + C'),
    ('SUB',   0x0403, 4, 'Rd <- Rf1 - Rf2'),
    ('SBB',   0x0404, 4, 'Rd <- Rf1 - Rf2 - C'),
    ('MUL',   0x0405, 4, 'Rd <- (Rf1 * Rf2) mod 2^64'),
    ('DIV',   0x0406, 4, 'Rd <- Rf1 / Rf2 (entera con signo, trunca)'),
    ('DIVU',  0x0407, 4, 'Rd <- Rf1 / Rf2 (entera sin signo)'),
    ('MOD',   0x0408, 4, 'Rd <- Rf1 mod Rf2 (con signo)'),
    ('MODU',  0x0409, 4, 'Rd <- Rf1 mod Rf2 (sin signo)'),
    ('AND',   0x040A, 4, 'Rd <- Rf1 AND Rf2'),
    ('OR',    0x040B, 4, 'Rd <- Rf1 OR Rf2'),
    ('XOR',   0x040C, 4, 'Rd <- Rf1 XOR Rf2'),
    ('SHL',   0x040D, 4, 'Rd <- Rf1 << Rf2'),
    ('SHR',   0x040E, 4, 'Rd <- Rf1 >> Rf2 (lógico)'),
    ('SAR',   0x040F, 4, 'Rd <- Rf1 >> Rf2 (aritmético)'),
    ('CMP',   0x0410, 4, 'Banderas <- Rf1 - Rf2'),
    ('TEST',  0x0411, 4, 'Banderas <- Rf1 AND Rf2'),
    ('LDR',   0x0412, 4, 'Rd <- M64[Rf1 + Rf2]'),
    ('STR',   0x0413, 4, 'M64[Rf1 + Rf2] <- Rd'),
    ('LDRB',  0x0414, 4, 'Rd <- M8[Rf1 + Rf2]'),
    ('STRB',  0x0415, 4, 'M8[Rf1 + Rf2] <- Rd (byte bajo)'),
    # ---------------- F5: memoria ----------------
    ('LOAD',  0x0500, 5, 'R <- M64[dir]   (modo: directo, [indirecto], dir(R12) indexado)'),
    ('STORE', 0x0501, 5, 'M64[dir] <- R'),
    ('LEA',   0x0502, 5, 'R <- dirección efectiva'),
    ('NSEND', 0x0503, 5, 'NIC: envía R bytes desde dir'),
    ('NRECV', 0x0504, 5, 'NIC: recibe un bloque en dir ; R <- bytes recibidos'),
    # ---------------- F6: inmediato ----------------
    ('MOVI',  0x0600, 6, 'Rd <- inm (modo 00 extensión con ceros, 01 con signo)'),
    ('MOVK',  0x0601, 6, 'Inserta inm en el trozo de 16 bits número modo de Rd'),
    ('ADDI',  0x0602, 6, 'Rd <- Rd + inm'),
    ('SUBI',  0x0603, 6, 'Rd <- Rd - inm'),
    ('MULI',  0x0604, 6, 'Rd <- Rd * inm'),
    ('ANDI',  0x0605, 6, 'Rd <- Rd AND inm'),
    ('ORI',   0x0606, 6, 'Rd <- Rd OR inm'),
    ('XORI',  0x0607, 6, 'Rd <- Rd XOR inm'),
    ('SHLI',  0x0608, 6, 'Rd <- Rd << inm'),
    ('SHRI',  0x0609, 6, 'Rd <- Rd >> inm (lógico)'),
    ('SARI',  0x060A, 6, 'Rd <- Rd >> inm (aritmético)'),
    ('CMPI',  0x060B, 6, 'Banderas <- Rd - inm'),
]

# Alias aceptados por el ensamblador (no son opcodes nuevos)
ALIAS = {'JE': 'JZ', 'JNE': 'JNZ', 'JB': 'JC', 'JAE': 'JNC'}

POR_NOMBRE = {n: (op, f, d) for n, op, f, d in INSTRUCCIONES}
POR_OPCODE = {op: (n, f) for n, op, f, d in INSTRUCCIONES}

# Modos de los periféricos de E/S (campo modo de F2)
MODOS_ES = {'D': 0, 'H': 1, 'C': 2, 'F': 3}
# Modos de direccionamiento de F5
DIRECTO, INDIRECTO, INDEXADO = 0, 1, 2

REGISTROS = {('R%d' % i): i for i in range(16)}
REGISTROS.update({'SP': 13, 'LR': 14, 'ACC': 15})


def codificar(formato, opcode, modo=0, rd=0, rf1=0, rf2=0, direccion=0, inm=0):
    """Devuelve (entero_con_los_bits, numero_de_bits_utiles) de una instrucción."""
    if formato == 1:
        return opcode, 16
    if formato == 2:
        return (opcode << 8) | (modo << 6) | (rd << 2), 24
    if formato == 3:
        return (opcode << 12) | (direccion & 0xFFF), 28
    if formato == 4:
        return (opcode << 16) | (modo << 12) | (rd << 8) | (rf1 << 4) | rf2, 32
    if formato == 5:
        return (opcode << 20) | (modo << 18) | (rd << 14) | ((direccion & 0xFFF) << 2), 36
    if formato == 6:
        return (opcode << 24) | (modo << 22) | (rd << 18) | ((inm & 0xFFFF) << 2), 40
    raise ValueError('formato desconocido')


def a_bytes(valor, bits):
    """Alinea los bits útiles a la izquierda de ceil(bits/8) bytes (relleno con ceros)."""
    n = (bits + 7) // 8
    return (valor << (n * 8 - bits)).to_bytes(n, 'big')


def decodificar(formato, palabra):
    """palabra: entero con los n bytes de la instrucción (relleno incluido)."""
    if formato == 1:
        return {}
    if formato == 2:
        return {'modo': (palabra >> 6) & 3, 'rd': (palabra >> 2) & 15}
    if formato == 3:
        return {'dir': (palabra >> 4) & 0xFFF}
    if formato == 4:
        return {'modo': (palabra >> 12) & 15, 'rd': (palabra >> 8) & 15,
                'rf1': (palabra >> 4) & 15, 'rf2': palabra & 15}
    if formato == 5:
        return {'modo': (palabra >> 22) & 3, 'rd': (palabra >> 18) & 15,
                'dir': (palabra >> 6) & 0xFFF}
    if formato == 6:
        return {'modo': (palabra >> 22) & 3, 'rd': (palabra >> 18) & 15,
                'inm': (palabra >> 2) & 0xFFFF}
    raise ValueError('formato desconocido')
