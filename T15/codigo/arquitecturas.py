# -*- coding: utf-8 -*-
"""Adaptadores: presentan a las tres CPU heterogéneas con una interfaz común para la red.

Interfaz común de un nodo-computador:
    cargar(ruta_fuente, entradas)   ensambla con SU propio ensamblador y carga el binario
    paso()                          ejecuta una instrucción de SU propio repertorio
    detenida, instrucciones, salida
    enviar  (lo asigna la red)      función que recibe los bytes que la NIC transmite
    rx                              cola de paquetes recibidos que la NIC entrega a la CPU
"""

import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, 'andes64'))

import cargador as _andes_cargador        # noqa: E402
import ensamblador as _andes_ensamblador  # noqa: E402
import maquina as _andes                  # noqa: E402
from caribe16 import Caribe16             # noqa: E402,F401
from orinoco32 import Orinoco32           # noqa: E402,F401


class Andes64:
    FABRICANTE = 'Industrias Andinas de Cómputo (IAC)'
    MODELO = 'ANDES-64'
    PALABRA = 64

    def __init__(self):
        self.cpu = _andes.CPU(eco=False)

    @property
    def enviar(self):
        return self.cpu.nic.enlace

    @enviar.setter
    def enviar(self, f):
        self.cpu.nic.enlace = f

    @property
    def rx(self):
        return self.cpu.nic.recibidas

    @property
    def detenida(self):
        return self.cpu.detenida

    @property
    def instrucciones(self):
        return self.cpu.instrucciones

    @property
    def salida(self):
        return self.cpu.es.salida

    def paso(self):
        return self.cpu.paso()

    def estado(self):
        return 'PC=%03X R0=%X R2=%X' % (self.cpu.pc, self.cpu.R[0], self.cpu.R[2])

    def cargar_fuente(self, ruta):
        obj = _andes_ensamblador.ensamblar(ruta)
        _andes_cargador.cargar(self.cpu, obj)
        return obj.tamano()


MODELOS = {'ANDES-64': Andes64, 'ORINOCO-32': Orinoco32, 'CARIBE-16': Caribe16}
EXTENSION = {'ANDES-64': '.a64', 'ORINOCO-32': '.o32', 'CARIBE-16': '.c16'}
# instrucciones que ejecuta cada CPU por tick de simulación (relojes distintos)
IPC = {'ANDES-64': 8, 'ORINOCO-32': 5, 'CARIBE-16': 3}


def crear(modelo, programa, entradas=None):
    """Crea la CPU del modelo, ensambla `programa` (nombre sin extensión dentro de
    programas/<modelo>/) y lo carga. `entradas` alimenta el periférico de entrada."""
    cpu = MODELOS[modelo]()
    ruta = os.path.join(AQUI, 'programas', modelo.lower(), programa + EXTENSION[modelo])
    cpu.cargar_fuente(ruta)
    if entradas:
        if modelo != 'ANDES-64':
            raise ValueError('solo ANDES-64 tiene periférico de entrada de datos')
        cpu.cpu.es.entrada.extend(entradas)
    return cpu
