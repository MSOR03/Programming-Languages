# -*- coding: utf-8 -*-
"""Módulo Enlazador-Cargador (parte "Cargador").

Formato del archivo objeto (.obj, texto plano, se puede editar bit a bit):
    ORIGEN 000            dirección para la que fue ensamblado (hex)
    INICIO 000            dirección de la primera instrucción a ejecutar
    SIMBOLO nombre 1A0    tabla de símbolos
    REUBICA 004 F3        campo de dirección que debe corregirse si se carga en otra dirección
    000: 00000011 00000000 0000...   ; línea fuente
El cargador lee el objeto desde la memoria secundaria (disco), lo reubica si se pide otra
dirección de carga y lo monta en la RAM; finalmente fija el PC en la dirección de inicio.
"""

import re

import isa
from ensamblador import Objeto


def guardar_obj(obj, ruta):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write('; archivo objeto - computador de 64 bits (Tarea 17)\n')
        f.write('ORIGEN %03X\nINICIO %03X\n' % (obj.origen or 0, obj.inicio))
        for nombre, d in sorted(obj.simbolos.items(), key=lambda x: x[1]):
            f.write('SIMBOLO %s %03X\n' % (nombre, d))
        for d, tipo in obj.reubicacion:
            f.write('REUBICA %03X %s\n' % (d, tipo))
        for d, datos, fuente in obj.segmentos:
            f.write('%03X: %s ; %s\n' % (d, ' '.join(format(b, '08b') for b in datos), fuente))


def leer_obj(ruta):
    obj = Objeto()
    with open(ruta, encoding='utf-8') as f:
        for linea in f:
            linea = linea.split(';', 1)[0].strip()
            if not linea:
                continue
            p = linea.split()
            if p[0] == 'ORIGEN':
                obj.origen = int(p[1], 16)
            elif p[0] == 'INICIO':
                obj.inicio = int(p[1], 16)
            elif p[0] == 'SIMBOLO':
                obj.simbolos[p[1]] = int(p[2], 16)
            elif p[0] == 'REUBICA':
                obj.reubicacion.append((int(p[1], 16), p[2]))
            else:
                m = re.match(r'([0-9A-Fa-f]+):\s*([01\s]*)$', linea)
                if not m:
                    raise ValueError('línea de objeto inválida: %s' % linea)
                bits = m.group(2).replace(' ', '')
                datos = int(bits, 2).to_bytes(len(bits) // 8, 'big') if bits else b''
                obj.segmentos.append((int(m.group(1), 16), datos, ''))
    return obj


def _corregir(imagen, base, d, tipo, delta):
    """Suma delta al campo de dirección de la instrucción/dato ubicado en d."""
    i = d - base
    if tipo == 'D64':
        v = int.from_bytes(imagen[i:i + 8], 'big')
        imagen[i:i + 8] = ((v + delta) & ((1 << 64) - 1)).to_bytes(8, 'big')
        return
    n = {'F3': 4, 'F5': 5, 'F6': 5}[tipo]
    w = int.from_bytes(imagen[i:i + n], 'big')
    f = int(tipo[1])
    campo = isa.decodificar(f, w)
    if tipo == 'F6':
        nuevo = (campo['inm'] + delta) & 0xFFFF
        w = (w & ~(0xFFFF << 2)) | (nuevo << 2)
    else:
        despl = 4 if tipo == 'F3' else 6
        nuevo = (campo['dir'] + delta) & 0xFFF
        w = (w & ~(0xFFF << despl)) | (nuevo << despl)
    imagen[i:i + n] = w.to_bytes(n, 'big')


def cargar(cpu, obj, direccion=None):
    """Monta el objeto en la RAM. Si `direccion` difiere del origen, reubica.
    Devuelve (dirección de carga, dirección de inicio)."""
    base = obj.origen or 0
    destino = base if direccion is None else direccion
    delta = destino - base
    fin = obj.fin()
    imagen = bytearray(fin - base)
    for d, datos, _ in obj.segmentos:
        imagen[d - base:d - base + len(datos)] = datos
    if delta:
        for d, tipo in obj.reubicacion:
            _corregir(imagen, base, d, tipo, delta)
    if destino + len(imagen) > len(cpu.mem.ram):
        raise ValueError('el programa no cabe en la RAM a partir de 0x%03X' % destino)
    cpu.mem.ram[destino:destino + len(imagen)] = imagen
    cpu.predecod.clear()
    inicio = obj.inicio + delta
    cpu.pc = inicio
    return destino, inicio
