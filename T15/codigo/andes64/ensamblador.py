# -*- coding: utf-8 -*-
"""Ensamblador de dos pasadas para el computador de 64 bits.

Sintaxis:
    etiqueta:  NEMONICO operandos      ; comentario
Directivas:
    .org expr            fija la dirección de ensamblado
    .equ NOMBRE expr     define una constante
    .dword expr, ...     palabras de 64 bits (enteros o etiquetas)
    .double real, ...    reales IEEE 754 de doble precisión
    .string "texto"      bytes ASCII terminados en 0
    .space n             reserva n bytes en cero
    .include "archivo"   ensambla otro módulo en este punto
Operandos de memoria (F5):  dir  |  [dir] (indirecto)  |  dir(R12) (indexado)
"""

import os
import re
import struct

import isa


MASK64 = (1 << 64) - 1


class ErrorEnsamblado(Exception):
    pass


class Objeto:
    """Resultado del ensamblado: código máquina + tabla de símbolos + reubicación."""

    def __init__(self):
        self.origen = None
        self.inicio = 0
        self.simbolos = {}
        self.segmentos = []        # (direccion, bytes, texto_fuente)
        self.reubicacion = []      # (direccion, tipo)  tipo in F3, F5, F6, D64

    def fin(self):
        return max((d + len(b) for d, b, _ in self.segmentos), default=0)

    def tamano(self):
        return self.fin() - (self.origen or 0)


def _quitar_comentario(linea):
    fuera, cad = [], False
    for ch in linea:
        if ch == '"':
            cad = not cad
        if ch == ';' and not cad:
            break
        fuera.append(ch)
    return ''.join(fuera).strip()


def _separar_operandos(texto):
    partes, actual, prof, cad = [], '', 0, False
    for ch in texto:
        if ch == '"':
            cad = not cad
        if ch in '([' and not cad:
            prof += 1
        if ch in ')]' and not cad:
            prof -= 1
        if ch == ',' and prof == 0 and not cad:
            partes.append(actual.strip())
            actual = ''
        else:
            actual += ch
    if actual.strip():
        partes.append(actual.strip())
    return partes


class Ensamblador:
    def __init__(self):
        self.simbolos = {}
        self.constantes = {}

    # ---------------------------------------------------------------- expresiones
    def valor(self, expr, pc):
        """Evalúa sumas/restas de números, caracteres, constantes y etiquetas.
        Devuelve (valor, usa_etiqueta)."""
        expr = expr.strip()
        tokens = re.findall(r"'[^']'|[+-]|[^+\-\s]+", expr)
        total, signo, usa_etq, esperando = 0, 1, False, True
        for t in tokens:
            if t in '+-' and len(t) == 1:
                signo = signo * (-1 if t == '-' else 1)
                continue
            if t.startswith("'"):
                v = ord(t[1])
            elif t == '$':
                v, usa_etq = pc, True
            elif re.fullmatch(r'0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d[\d_]*', t):
                v = int(t.replace('_', ''), 0)
            elif t in self.constantes:
                v = self.constantes[t]
            elif t in self.simbolos:
                v, usa_etq = self.simbolos[t], True
            else:
                raise ErrorEnsamblado('símbolo no definido: %s' % t)
            total += signo * v
            signo, esperando = 1, False
        if esperando:
            raise ErrorEnsamblado('expresión vacía: %r' % expr)
        return total, usa_etq

    @staticmethod
    def registro(t):
        t = t.strip().upper()
        if t not in isa.REGISTROS:
            raise ErrorEnsamblado('registro inválido: %s' % t)
        return isa.REGISTROS[t]

    # ---------------------------------------------------------------- lectura
    def _leer_lineas(self, ruta, visitados=None):
        visitados = visitados or []
        ruta = os.path.abspath(ruta)
        if ruta in visitados:
            raise ErrorEnsamblado('inclusión circular: %s' % ruta)
        with open(ruta, encoding='utf-8') as f:
            for num, cruda in enumerate(f, 1):
                limpia = _quitar_comentario(cruda.rstrip('\n'))
                m = re.match(r'\s*\.include\s+"([^"]+)"', limpia, re.I)
                if m:
                    otra = os.path.join(os.path.dirname(ruta), m.group(1))
                    yield from self._leer_lineas(otra, visitados + [ruta])
                else:
                    yield os.path.basename(ruta), num, cruda.rstrip('\n'), limpia

    def _tamano(self, nemonico, ops):
        n = nemonico.upper()
        n = isa.ALIAS.get(n, n)
        if n in isa.POR_NOMBRE:
            return isa.BYTES[isa.POR_NOMBRE[n][1]]
        if n == '.DWORD' or n == '.DOUBLE':
            return 8 * len(ops)
        if n == '.STRING':
            return len(self._cadena(ops[0])) + 1
        if n == '.SPACE':
            return self.valor(ops[0], 0)[0]
        raise ErrorEnsamblado('nemónico desconocido: %s' % nemonico)

    @staticmethod
    def _cadena(t):
        t = t.strip()
        if not (t.startswith('"') and t.endswith('"')):
            raise ErrorEnsamblado('se esperaba una cadena entre comillas')
        return t[1:-1].replace('\\n', '\n').replace('\\t', '\t').encode('ascii')

    def _partir(self, limpia):
        etq = None
        m = re.match(r'^([A-Za-z_][\w]*)\s*:(.*)$', limpia)
        if m:
            etq, limpia = m.group(1), m.group(2).strip()
        if not limpia:
            return etq, None, []
        partes = limpia.split(None, 1)
        return etq, partes[0], _separar_operandos(partes[1]) if len(partes) > 1 else []

    # ---------------------------------------------------------------- ensamblado
    def ensamblar_archivo(self, ruta):
        lineas = list(self._leer_lineas(ruta))
        obj = Objeto()
        # ---- pasada 1: direcciones de las etiquetas
        pc = 0
        for arch, num, cruda, limpia in lineas:
            try:
                etq, nem, ops = self._partir(limpia)
                if etq:
                    if etq in self.simbolos:
                        raise ErrorEnsamblado('etiqueta duplicada: %s' % etq)
                    self.simbolos[etq] = pc
                if not nem:
                    continue
                u = nem.upper()
                if u == '.ORG':
                    pc = self.valor(ops[0], pc)[0]
                    if etq:
                        self.simbolos[etq] = pc
                elif u == '.EQU':
                    nombre, expr = ops[0].split(None, 1) if len(ops) == 1 else (ops[0], ops[1])
                    self.constantes[nombre.strip()] = self.valor(expr, pc)[0]
                else:
                    pc += self._tamano(nem, ops)
            except ErrorEnsamblado as e:
                raise ErrorEnsamblado('%s:%d: %s\n    %s' % (arch, num, e, cruda.strip()))
        # ---- pasada 2: generación de código
        pc = 0
        for arch, num, cruda, limpia in lineas:
            try:
                etq, nem, ops = self._partir(limpia)
                if not nem:
                    continue
                u = nem.upper()
                if u == '.ORG':
                    pc = self.valor(ops[0], pc)[0]
                    if obj.origen is None:
                        obj.origen = pc
                    continue
                if u == '.EQU':
                    continue
                if obj.origen is None:
                    obj.origen = pc
                datos, reub = self._generar(u, ops, pc)
                for desp, tipo in reub:
                    obj.reubicacion.append((pc + desp, tipo))
                obj.segmentos.append((pc, datos, cruda.strip()))
                pc += len(datos)
            except ErrorEnsamblado as e:
                raise ErrorEnsamblado('%s:%d: %s\n    %s' % (arch, num, e, cruda.strip()))
        if obj.fin() > 4096:
            raise ErrorEnsamblado('el programa no cabe en la RAM de 4 KB (termina en 0x%X)' % obj.fin())
        obj.simbolos = dict(self.simbolos)
        obj.inicio = obj.origen or 0
        return obj

    def _generar(self, u, ops, pc):
        if u == '.DWORD':
            datos, reub = b'', []
            for i, o in enumerate(ops):
                v, e = self.valor(o, pc)
                datos += (v & MASK64).to_bytes(8, 'big')
                if e:
                    reub.append((8 * i, 'D64'))
            return datos, reub
        if u == '.DOUBLE':
            return b''.join(struct.pack('>d', float(o)) for o in ops), []
        if u == '.STRING':
            return self._cadena(ops[0]) + b'\0', []
        if u == '.SPACE':
            return bytes(self.valor(ops[0], pc)[0]), []
        u = isa.ALIAS.get(u, u)
        opcode, f, _ = isa.POR_NOMBRE[u]
        campos, reub = {}, []

        def exigir(n):
            if len(ops) != n:
                raise ErrorEnsamblado('%s espera %d operando(s)' % (u, n))

        if f == 1:
            exigir(0)
        elif f == 2:
            if u in ('IN', 'OUT'):
                if len(ops) not in (1, 2):
                    raise ErrorEnsamblado('%s espera registro[, D|H|C|F]' % u)
                campos['rd'] = self.registro(ops[0])
                campos['modo'] = isa.MODOS_ES[ops[1].strip().upper()] if len(ops) == 2 else 0
            else:
                exigir(1)
                campos['rd'] = self.registro(ops[0])
        elif f == 3:
            exigir(1)
            v, e = self.valor(ops[0], pc)
            self._rango(v, 0, 0xFFF, 'dirección')
            campos['direccion'] = v
            if e:
                reub.append((0, 'F3'))
        elif f == 4:
            if u == 'MOV':
                exigir(2)
                campos['rd'], campos['rf1'] = self.registro(ops[0]), self.registro(ops[1])
            elif u in ('CMP', 'TEST'):
                exigir(2)
                campos['rf1'], campos['rf2'] = self.registro(ops[0]), self.registro(ops[1])
            else:
                exigir(3)
                campos['rd'], campos['rf1'], campos['rf2'] = (self.registro(o) for o in ops)
        elif f == 5:
            exigir(2)
            campos['rd'] = self.registro(ops[0])
            t = ops[1].strip()
            m = re.fullmatch(r'(.+)\(\s*R12\s*\)', t, re.I)
            if t.startswith('[') and t.endswith(']'):
                campos['modo'], t = isa.INDIRECTO, t[1:-1]
            elif m:
                campos['modo'], t = isa.INDEXADO, m.group(1)
            v, e = self.valor(t, pc)
            self._rango(v, 0, 0xFFF, 'dirección')
            campos['direccion'] = v
            if e:
                reub.append((0, 'F5'))
        elif f == 6:
            if u == 'MOVK':
                exigir(3)
                campos['modo'] = self.valor(ops[2], pc)[0]
                self._rango(campos['modo'], 0, 3, 'trozo')
            else:
                exigir(2)
            campos['rd'] = self.registro(ops[0])
            v, e = self.valor(ops[1], pc)
            self._rango(v, -0x8000, 0xFFFF, 'inmediato')
            if v < 0:
                campos['modo'] = 1
            campos['inm'] = v & 0xFFFF
            if e:
                reub.append((0, 'F6'))
        valor, bits = isa.codificar(f, opcode, **campos)
        return isa.a_bytes(valor, bits), reub

    @staticmethod
    def _rango(v, lo, hi, que):
        if not lo <= v <= hi:
            raise ErrorEnsamblado('%s fuera de rango: %d' % (que, v))


def ensamblar(ruta):
    return Ensamblador().ensamblar_archivo(ruta)


def listado(obj):
    """Listado con dirección, bits y línea fuente."""
    lineas = []
    for d, datos, fuente in obj.segmentos:
        bits = ' '.join(format(b, '08b') for b in datos[:8])
        if len(datos) > 8:
            bits += ' ...(%d B)' % len(datos)
        lineas.append('%03X: %-44s ; %s' % (d, bits, fuente))
    return '\n'.join(lineas)


if __name__ == '__main__':
    import sys
    import cargador
    if len(sys.argv) < 2:
        print('uso: python ensamblador.py programa.asm [salida.obj]')
        sys.exit(1)
    o = ensamblar(sys.argv[1])
    salida = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(sys.argv[1])[0] + '.obj'
    cargador.guardar_obj(o, salida)
    print(listado(o))
    print('\n%d bytes, origen 0x%03X -> %s' % (o.tamano(), o.origen, salida))
