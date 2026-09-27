# -*- coding: utf-8 -*-
"""Emulación de la MANET: medio inalámbrico, movilidad y enrutamiento.

Modelo (discreto en el tiempo, 1 tick = 10 ms simulados):
  * Radio: dos nodos están enlazados si su distancia es <= min(alcance_i, alcance_j).
    Cada transmisión de un salto tarda 1 tick y se pierde con probabilidad p_perdida.
  * Capa de enlace: los envíos unicast se reintentan hasta REINTENTOS_MAC veces
    (como el ACK de 802.11). Los broadcast (RREQ) no se reintentan.
  * Movilidad: "random waypoint" (destino aleatorio, velocidad v, pausa) o nodos fijos.
  * Enrutamiento: AODV simplificado (bajo demanda):
      RREQ por inundación con identificador (origen, id) y TTL,
      ruta inversa en cada nodo intermedio, RREP unicast por la ruta inversa,
      rutas con tiempo de vida, reparación local cuando un enlace se rompe,
      reintento de descubrimiento y descarte tras MAX_RREQ intentos.
  * Paquete de aplicación (PDU canónica, independiente de la arquitectura):
      byte 0 = destino al enviar / origen al recibir, byte 1 = tipo, bytes 2.. = datos
      (enteros de 32 bits con signo en big-endian = "orden de red").
"""

import math
import random
from collections import deque

import arquitecturas

TICK_S = 0.01
REINTENTOS_MAC = 3
TTL = 12
VIDA_RUTA = 300             # ticks
ESPERA_RREP = 40            # ticks antes de reintentar un RREQ
MAX_RREQ = 3
TIPOS = {1: 'SUMA', 2: 'RESULTADO', 3: 'PING', 4: 'PONG'}


class Paquete:
    _n = 0

    def __init__(self, clase, origen, destino, datos=b'', **extra):
        Paquete._n += 1
        self.uid = Paquete._n
        self.clase = clase          # DATOS | RREQ | RREP
        self.origen, self.destino = origen, destino
        self.datos = datos
        self.saltos = 0
        self.t0 = extra.pop('t0', 0)
        self.__dict__.update(extra)


class Nodo:
    def __init__(self, nid, modelo, programa, x, y, alcance=100.0, entradas=None,
                 velocidad=0.0, pausa=0):
        self.id, self.modelo = nid, modelo
        self.cpu = arquitecturas.crear(modelo, programa, entradas)
        self.programa = programa
        self.ipc = arquitecturas.IPC[modelo]
        self.x, self.y = float(x), float(y)
        self.alcance = alcance
        self.velocidad, self.pausa = velocidad, pausa
        self.meta = None
        self.espera = 0
        self.rutas = {}              # destino -> [siguiente, saltos, expira]
        self.pendientes = {}         # destino -> deque de paquetes esperando ruta
        self.buscando = {}           # destino -> (t_ultimo_rreq, intentos)
        self.vistos = set()          # (origen, id) de RREQ ya procesados
        self.rreq_id = 0
        self.energia = 0.0
        self.error = None

    @property
    def nombre(self):
        return '%s#%d' % (self.modelo, self.id)


class Red:
    def __init__(self, ancho=300, alto=300, p_perdida=0.0, semilla=1, verboso=False):
        self.ancho, self.alto = ancho, alto
        self.p = p_perdida
        self.rnd = random.Random(semilla)
        self.nodos = {}
        self.t = 0
        self.en_vuelo = []           # (t_llegada, receptor, emisor, paquete)
        self.eventos = []
        self.verboso = verboso
        self.m = {'datos_app': 0, 'entregados': 0, 'latencias': [], 'tx_datos': 0,
                  'tx_rreq': 0, 'tx_rrep': 0, 'retransmisiones': 0, 'rupturas': 0,
                  'descubrimientos': 0, 'descartados': 0, 'perdidas_radio': 0}
        self.envios, self.entregas = [], []

    # ------------------------------------------------------------------ construcción
    def agregar(self, nodo):
        self.nodos[nodo.id] = nodo
        nodo.cpu.enviar = lambda datos, n=nodo: self._desde_nic(n, datos)
        return nodo

    def log(self, texto):
        linea = '[t=%5d] %s' % (self.t, texto)
        self.eventos.append(linea)
        if self.verboso:
            print(linea)

    # ------------------------------------------------------------------ radio
    def distancia(self, a, b):
        return math.hypot(a.x - b.x, a.y - b.y)

    def enlazados(self, a, b):
        return a is not b and self.distancia(a, b) <= min(a.alcance, b.alcance)

    def vecinos(self, n):
        return [o for o in self.nodos.values() if self.enlazados(n, o)]

    def enlaces(self):
        ids = sorted(self.nodos)
        return [(i, j) for k, i in enumerate(ids) for j in ids[k + 1:]
                if self.enlazados(self.nodos[i], self.nodos[j])]

    def _transmitir(self, emisor, paquete, siguiente=None):
        """siguiente=None: broadcast. Devuelve False si el enlace unicast falló."""
        emisor.energia += 1.0
        clave = {'DATOS': 'tx_datos', 'RREQ': 'tx_rreq', 'RREP': 'tx_rrep'}[paquete.clase]
        self.m[clave] += 1
        if siguiente is None:
            for v in self.vecinos(emisor):
                if self.rnd.random() >= self.p:
                    self.en_vuelo.append((self.t + 1, v.id, emisor.id, paquete))
                else:
                    self.m['perdidas_radio'] += 1
            return True
        receptor = self.nodos[siguiente]
        for intento in range(REINTENTOS_MAC):
            if intento:
                self.m['retransmisiones'] += 1
                emisor.energia += 1.0
            if not self.enlazados(emisor, receptor):
                break
            if self.rnd.random() >= self.p:
                self.en_vuelo.append((self.t + 1, receptor.id, emisor.id, paquete))
                return True
            self.m['perdidas_radio'] += 1
        return False

    # ------------------------------------------------------------------ AODV
    def _ruta(self, nodo, destino):
        r = nodo.rutas.get(destino)
        if r and r[2] >= self.t:
            return r
        nodo.rutas.pop(destino, None)
        return None

    def _instalar(self, nodo, destino, siguiente, saltos):
        r = self._ruta(nodo, destino)
        if r is None or saltos <= r[1] or r[0] == siguiente:
            nodo.rutas[destino] = [siguiente, saltos, self.t + VIDA_RUTA]

    def _enviar_datos(self, nodo, paquete):
        """Reenvía un paquete de datos desde `nodo` hacia paquete.destino."""
        r = self._ruta(nodo, paquete.destino)
        if r is None:
            nodo.pendientes.setdefault(paquete.destino, deque()).append(paquete)
            if paquete.destino not in nodo.buscando:
                self._descubrir(nodo, paquete.destino, 1)
            return
        r[2] = self.t + VIDA_RUTA
        if not self._transmitir(nodo, paquete, r[0]):
            self.m['rupturas'] += 1
            self.log('%s: se rompió el enlace con #%d (ruta a #%d); reparación local'
                     % (nodo.nombre, r[0], paquete.destino))
            for d in [d for d, rr in nodo.rutas.items() if rr[0] == r[0]]:
                del nodo.rutas[d]
            self._enviar_datos(nodo, paquete)

    def _descubrir(self, nodo, destino, intento):
        nodo.rreq_id += 1
        nodo.buscando[destino] = (self.t, intento)
        nodo.vistos.add((nodo.id, nodo.rreq_id))
        self.m['descubrimientos'] += 1
        self.log('%s: RREQ #%d buscando ruta a #%d (intento %d)'
                 % (nodo.nombre, nodo.rreq_id, destino, intento))
        p = Paquete('RREQ', nodo.id, destino, rid=nodo.rreq_id, t0=self.t)
        self._transmitir(nodo, p)

    def _vencimientos(self):
        for nodo in self.nodos.values():
            for destino, (t, intento) in list(nodo.buscando.items()):
                if self._ruta(nodo, destino):
                    del nodo.buscando[destino]
                elif self.t - t >= ESPERA_RREP:
                    if intento < MAX_RREQ:
                        self._descubrir(nodo, destino, intento + 1)
                    else:
                        perdidos = nodo.pendientes.pop(destino, [])
                        self.m['descartados'] += len(perdidos)
                        del nodo.buscando[destino]
                        self.log('%s: sin ruta a #%d, se descartan %d paquete(s)'
                                 % (nodo.nombre, destino, len(perdidos)))

    def _recibir(self, nodo, emisor, p):
        nodo.energia += 0.5
        if p.clase == 'RREQ':
            if (p.origen, p.rid) in nodo.vistos:
                return
            nodo.vistos.add((p.origen, p.rid))
            saltos = p.saltos + 1
            self._instalar(nodo, p.origen, emisor, saltos)      # ruta inversa
            if nodo.id == p.destino:
                self.log('%s: RREQ de #%d llegó en %d salto(s); responde RREP'
                         % (nodo.nombre, p.origen, saltos))
                rrep = Paquete('RREP', nodo.id, p.origen, saltos_ruta=0, t0=self.t)
                self._rrep(nodo, rrep)
            elif saltos < TTL:
                q = Paquete('RREQ', p.origen, p.destino, rid=p.rid, t0=p.t0)
                q.saltos = saltos
                self._transmitir(nodo, q)
        elif p.clase == 'RREP':
            p.saltos_ruta += 1
            self._instalar(nodo, p.origen, emisor, p.saltos_ruta)  # ruta directa
            if nodo.id == p.destino:
                self.log('%s: ruta a #%d establecida vía #%d (%d saltos)'
                         % (nodo.nombre, p.origen, emisor, p.saltos_ruta))
                nodo.buscando.pop(p.origen, None)
                for q in nodo.pendientes.pop(p.origen, []):
                    self._enviar_datos(nodo, q)
            else:
                self._rrep(nodo, p)
        else:  # DATOS
            p.saltos += 1
            self._instalar(nodo, p.origen, emisor, p.saltos)      # aprende la ruta de vuelta
            if nodo.id == p.destino:
                lat = self.t - p.t0
                self.m['entregados'] += 1
                self.m['latencias'].append(lat)
                tipo = p.datos[0] if p.datos else 0
                valor = int.from_bytes(p.datos[1:5], 'big', signed=True) if len(p.datos) >= 5 else 0
                self.entregas.append((self.t, p.origen, nodo.id, tipo, valor, lat, p.saltos))
                self.log('%s: recibe %s(%d) de #%d  [%d salto(s), %d ticks]'
                         % (nodo.nombre, TIPOS.get(tipo, tipo), valor, p.origen, p.saltos, lat))
                nodo.cpu.rx.append(bytes([p.origen]) + p.datos)
            else:
                self._enviar_datos(nodo, p)

    def _rrep(self, nodo, rrep):
        r = self._ruta(nodo, rrep.destino)
        if r is None or not self._transmitir(nodo, rrep, r[0]):
            self.log('%s: no pudo reenviar el RREP hacia #%d' % (nodo.nombre, rrep.destino))

    # ------------------------------------------------------------------ interfaz NIC
    def _desde_nic(self, nodo, datos):
        if len(datos) < 2:
            return
        destino = datos[0]
        if destino not in self.nodos:
            self.log('%s: destino #%d inexistente' % (nodo.nombre, destino))
            return
        p = Paquete('DATOS', nodo.id, destino, bytes(datos[1:]), t0=self.t)
        tipo = datos[1]
        valor = int.from_bytes(datos[2:6], 'big', signed=True) if len(datos) >= 6 else 0
        self.m['datos_app'] += 1
        self.envios.append((self.t, nodo.id, destino, tipo, valor))
        self.log('%s: envía %s(%d) a #%d' % (nodo.nombre, TIPOS.get(tipo, tipo), valor, destino))
        self._enviar_datos(nodo, p)

    # ------------------------------------------------------------------ movilidad
    def _mover(self):
        for n in self.nodos.values():
            if n.velocidad <= 0:
                continue
            if n.espera > 0:
                n.espera -= 1
                continue
            if n.meta is None:
                n.meta = (self.rnd.uniform(0, self.ancho), self.rnd.uniform(0, self.alto))
            dx, dy = n.meta[0] - n.x, n.meta[1] - n.y
            d = math.hypot(dx, dy)
            paso = n.velocidad * TICK_S
            if d <= paso:
                n.x, n.y = n.meta
                n.meta, n.espera = None, n.pausa
            else:
                n.x += dx / d * paso
                n.y += dy / d * paso

    # ------------------------------------------------------------------ simulación
    def paso(self):
        self.t += 1
        self._mover()
        llegan = [e for e in self.en_vuelo if e[0] <= self.t]
        self.en_vuelo = [e for e in self.en_vuelo if e[0] > self.t]
        for _, rid, eid, p in llegan:
            self._recibir(self.nodos[rid], eid, p)
        for n in self.nodos.values():
            if n.error or n.cpu.detenida:
                continue
            try:
                for _ in range(n.ipc):
                    if not n.cpu.paso():
                        self.log('%s: la CPU ejecutó HLT' % n.nombre)
                        break
            except Exception as e:           # error de la CPU de ese nodo
                n.error = str(e)
                self.log('%s: ERROR de CPU: %s' % (n.nombre, e))
        self._vencimientos()

    def correr(self, max_ticks, hasta=None):
        """Avanza hasta max_ticks o hasta que el nodo `hasta` se detenga."""
        while self.t < max_ticks:
            self.paso()
            if hasta is not None and self.nodos[hasta].cpu.detenida:
                break
        return self.t

    # ------------------------------------------------------------------ reportes
    def resumen(self):
        m = self.m
        lat = m['latencias']
        return {
            'ticks': self.t,
            'datos_app': m['datos_app'],
            'entregados': m['entregados'],
            'pdr': m['entregados'] / m['datos_app'] if m['datos_app'] else 0.0,
            'latencia_media': sum(lat) / len(lat) if lat else 0.0,
            'latencia_max': max(lat) if lat else 0,
            'tx_datos': m['tx_datos'], 'tx_rreq': m['tx_rreq'], 'tx_rrep': m['tx_rrep'],
            'retransmisiones': m['retransmisiones'], 'rupturas': m['rupturas'],
            'descubrimientos': m['descubrimientos'], 'descartados': m['descartados'],
            'perdidas_radio': m['perdidas_radio'],
            'sobrecarga': (m['tx_rreq'] + m['tx_rrep']) / max(1, m['tx_datos']),
            'energia': {n.nombre: round(n.energia, 1) for n in self.nodos.values()},
            'instrucciones': {n.nombre: n.cpu.instrucciones for n in self.nodos.values()},
        }

    def mapa(self, columnas=60):
        """Instantánea ASCII de las posiciones (número = id del nodo)."""
        filas = max(3, round(columnas * self.alto / self.ancho / 2))
        g = [[' '] * columnas for _ in range(filas)]
        for n in self.nodos.values():
            c = min(columnas - 1, int(n.x / self.ancho * (columnas - 1)))
            f = min(filas - 1, int(n.y / self.alto * (filas - 1)))
            g[f][c] = str(n.id % 10)
        borde = '+' + '-' * columnas + '+'
        return '\n'.join([borde] + ['|' + ''.join(r) + '|' for r in g] + [borde])
