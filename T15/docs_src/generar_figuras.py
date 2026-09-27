# -*- coding: utf-8 -*-
"""Figuras y tablas del informe de la Tarea 15 a partir de codigo/resultados/resultados.json."""

import json
import os
import statistics as st
import sys

import graficas as G

AQUI = os.path.dirname(os.path.abspath(__file__))
COD = os.path.join(os.path.dirname(AQUI), 'codigo')
RES = os.path.join(COD, 'resultados', 'resultados.json')
FIGS = os.path.join(AQUI, 'figs')


def guardar(nombre, texto):
    os.makedirs(FIGS, exist_ok=True)
    with open(os.path.join(FIGS, nombre), 'w', encoding='utf-8') as f:
        f.write(texto)


def coma(v, d=2):
    return ('%.*f' % (d, v)).replace('.', ',')


def resultados():
    with open(RES, encoding='utf-8') as f:
        r = json.load(f)
    # ---------------- E1
    guardar('e1_salida.html', '<pre>%s</pre>' % r['e1']['salida'].strip())
    guardar('e1_bitacora.html', '<pre class="largo">%s</pre>' % '\n'.join(
        e.replace('<', '&lt;') for e in r['e1']['eventos']))
    s = r['e1']['resumen']
    filas = ['<table><tr><th>Métrica</th><th class="n">Valor</th></tr>']
    for k in ('ticks', 'datos_app', 'entregados', 'latencia_media', 'latencia_max', 'tx_datos',
              'tx_rreq', 'tx_rrep', 'descubrimientos'):
        filas.append('<tr><td>%s</td><td class="n">%s</td></tr>' % (k, s[k]))
    for k in ('energia', 'instrucciones'):
        filas.append('<tr><td>%s</td><td class="n">%s</td></tr>' % (k, ', '.join('%s: %s' % kv for kv in s[k].items())))
    filas.append('</table>')
    guardar('e1_metricas.html', '\n'.join(filas))

    # ---------------- E2 (velocidad)
    def pong(c):
        a, b = c['salida'].split(':')[1].split('/')
        return int(a) / int(b)
    filas = ['<table><tr><th class="n">v (m/s)</th><th>PONG recibidos por semilla (1..5)</th><th class="n">Éxito app.</th>'
             '<th class="n">PDR</th><th class="n">Latencia media (ticks)</th><th class="n">RREQ tx</th>'
             '<th class="n">Rupturas</th><th class="n">Descartados</th></tr>']
    xs, pdr, exito, lat, rreq = [], [], [], [], []
    for g in r['e2']:
        c = g['corridas']
        xs.append(g['velocidad'])
        exito.append(st.mean(pong(x) for x in c))
        pdr.append(st.mean(x['pdr'] for x in c))
        lat.append(st.mean(x['latencia_media'] for x in c))
        rreq.append(st.mean(x['tx_rreq'] for x in c))
        filas.append('<tr><td class="n">%g</td><td class="mono">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td>'
                     '<td class="n">%s</td><td class="n">%s</td><td class="n">%s</td></tr>'
                     % (g['velocidad'], ' · '.join(x['salida'].split(': ')[1] for x in c), coma(exito[-1] * 100, 1) + ' %',
                        coma(pdr[-1], 3), coma(lat[-1], 1), coma(rreq[-1], 1),
                        coma(st.mean(x['rupturas'] for x in c), 1), coma(st.mean(x['descartados'] for x in c), 1)))
    filas.append('</table>')
    guardar('e2_tabla.html', '\n'.join(filas))
    guardar('e2_pdr.svg', G.lineas([('PDR de la red', list(zip(xs, pdr))),
                                    ('PING respondidos', list(zip(xs, exito)))],
                                   'velocidad máxima de los nodos (m/s)', 'fracción entregada', ymin=0, ymax=1.05))
    guardar('e2_control.svg', G.lineas([('RREQ transmitidos', list(zip(xs, rreq)))],
                                       'velocidad máxima de los nodos (m/s)', 'transmisiones de RREQ por corrida',
                                       etiquetas_directas=False, ymin=0))

    # ---------------- E3 (pérdidas)
    filas = ['<table><tr><th class="n">p pérdida</th><th>PONG recibidos por semilla</th><th class="n">Éxito app.</th>'
             '<th class="n">PDR</th><th class="n">Latencia media</th><th class="n">Retransmisiones</th>'
             '<th class="n">Rupturas falsas</th><th class="n">RREQ tx</th></tr>']
    ps, pdr3, ex3, lat3, retx = [], [], [], [], []
    for g in r['e3']:
        c = g['corridas']
        ps.append(g['perdida'])
        ex3.append(st.mean(pong(x) for x in c))
        pdr3.append(st.mean(x['pdr'] for x in c))
        lat3.append(st.mean(x['latencia_media'] for x in c))
        retx.append(st.mean(x['retransmisiones'] for x in c))
        filas.append('<tr><td class="n">%s</td><td class="mono">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td>'
                     '<td class="n">%s</td><td class="n">%s</td><td class="n">%s</td></tr>'
                     % (coma(g['perdida'], 1), ' · '.join(x['salida'].split(': ')[1] for x in c), coma(ex3[-1] * 100, 1) + ' %',
                        coma(pdr3[-1], 3), coma(lat3[-1], 1), coma(retx[-1], 1),
                        coma(st.mean(x['rupturas'] for x in c), 1), coma(st.mean(x['tx_rreq'] for x in c), 1)))
    filas.append('</table>')
    guardar('e3_tabla.html', '\n'.join(filas))
    teorico = [(p, (1 - p ** 3) ** 4) for p in ps]          # 4 saltos, 3 intentos MAC por salto
    guardar('e3_pdr.svg', G.lineas([('PDR medido', list(zip(ps, pdr3))),
                                    ('modelo (1 − p³)⁴', teorico)],
                                   'probabilidad de pérdida por transmisión p', 'fracción entregada', ymin=0, ymax=1.05))
    guardar('e3_latencia.svg', G.lineas([('latencia media', list(zip(ps, lat3)))],
                                        'probabilidad de pérdida por transmisión p', 'latencia de extremo a extremo (ticks)',
                                        etiquetas_directas=False, ymin=0))

    # ---------------- E4 (tiempo de servicio)
    ns = [g['n'] for g in r['e4']]
    modelos = ['ANDES-64#4', 'ORINOCO-32#2', 'CARIBE-16#3']
    grupos = [(m.split('#')[0], [g['servicio'][m][0] for g in r['e4']]) for m in modelos]
    guardar('e4_servicio.svg', G.barras(['SUMA(%d)' % n for n in ns], grupos, 'ticks de servicio (1 tick = 10 ms)'))
    filas = ['<table><tr><th class="n">n</th>' + ''.join('<th class="n">%s (ticks)</th>' % m.split('#')[0] for m in modelos)
             + '<th class="n">Resultado</th><th class="n">CARIBE / ANDES</th></tr>']
    for g in r['e4']:
        t = [g['servicio'][m][0] for m in modelos]
        filas.append('<tr><td class="n">%d</td>%s<td class="n">%d</td><td class="n">%s</td></tr>'
                     % (g['n'], ''.join('<td class="n">%d</td>' % x for x in t), g['servicio'][modelos[0]][1], coma(t[2] / t[0], 1)))
    filas.append('</table>')
    guardar('e4_tabla.html', '\n'.join(filas))


def isa_tablas():
    sys.path.insert(0, COD)
    import caribe16
    import orinoco32
    f = ['<table><tr><th>Nemónico</th><th class="n">Opcode</th><th>Inmediato</th><th>Nemónico</th><th class="n">Opcode</th><th>Inmediato</th></tr>']
    items = sorted(caribe16.ISA.items(), key=lambda kv: kv[1][0])
    mitad = (len(items) + 1) // 2
    for a, b in zip(items[:mitad], items[mitad:] + [None]):
        celdas = []
        for it in (a, b):
            if it:
                celdas.append('<td class="mono">%s</td><td class="n">%d</td><td>%s</td>' % (it[0], it[1][0], '#' if it[1][1] else ''))
            else:
                celdas.append('<td></td><td></td><td></td>')
        f.append('<tr>%s</tr>' % ''.join(celdas))
    f.append('</table>')
    guardar('isa_caribe.html', '\n'.join(f))
    f = ['<table><tr><th>Nemónico</th><th class="n">Opcode</th><th class="n">Bytes</th><th>Nemónico</th><th class="n">Opcode</th><th class="n">Bytes</th></tr>']
    items = sorted(orinoco32.ISA.items(), key=lambda kv: kv[1][0])
    mitad = (len(items) + 1) // 2
    for a, b in zip(items[:mitad], items[mitad:] + [None]):
        celdas = []
        for it in (a, b):
            if it:
                celdas.append('<td class="mono">%s</td><td class="n mono">0x%02X</td><td class="n">%d</td>' % (it[0], it[1][0], 1 + it[1][1]))
            else:
                celdas.append('<td></td><td></td><td></td>')
        f.append('<tr>%s</tr>' % ''.join(celdas))
    f.append('</table>')
    guardar('isa_orinoco.html', '\n'.join(f))


def bloques(nombre, fab, cpu, regs, banderas, mem, bdat, bdir, bctl, es):
    """Diagrama de bloques von Neumann de un fabricante (CPU, memoria, E/S y buses)."""
    W, H = 640, 330
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="Arial, Helvetica, sans-serif" font-size="10.5">' % (W, H, W, H)]

    def caja(x, y, w, h, titulo, lineas, grosor=1):
        s.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#ffffff" stroke="#000" stroke-width="%s"/>' % (x, y, w, h, grosor))
        s.append('<text x="%d" y="%d" text-anchor="middle" font-weight="bold">%s</text>' % (x + w / 2, y + 15, titulo))
        for i, l in enumerate(lineas):
            s.append('<text x="%d" y="%d" text-anchor="middle">%s</text>' % (x + w / 2, y + 31 + 13 * i, l))

    s.append('<text x="%d" y="16" text-anchor="middle" font-size="13" font-weight="bold">%s — %s</text>' % (W / 2, nombre, fab))
    # CPU
    s.append('<rect x="20" y="30" width="330" height="170" fill="#ffffff" stroke="#000" stroke-width="1.5"/>')
    s.append('<text x="30" y="46" font-weight="bold">CPU (%s)</text>' % cpu)
    caja(30, 56, 150, 62, 'Unidad de control', ['PC, IR', 'fetch – decode – execute'])
    caja(190, 56, 150, 62, 'ALU', ['operaciones enteras', 'actualiza banderas'])
    caja(30, 126, 150, 66, 'Registros', regs)
    caja(190, 126, 150, 66, 'Banderas', banderas)
    caja(410, 30, 210, 90, 'Memoria principal', mem)
    caja(410, 140, 210, 60, 'Unidad de E/S', es)
    # buses
    ys = [235, 265, 295]
    etiquetas = ['Bus de datos (%s)' % bdat, 'Bus de direcciones (%s)' % bdir, 'Bus de control (%s)' % bctl]
    anchos = [3, 2, 1]
    for y, et, g in zip(ys, etiquetas, anchos):
        s.append('<line x1="20" x2="620" y1="%d" y2="%d" stroke="#000" stroke-width="%d"/>' % (y, y, g))
        s.append('<text x="24" y="%d">%s</text>' % (y - 4, et))
    for x, y0 in ((185, 200), (440, 120), (515, 200)):
        s.append('<line x1="%d" x2="%d" y1="%d" y2="295" stroke="#000" stroke-dasharray="3 2"/>' % (x, x, y0))
    s.append('<text x="520" y="318">NIC / radio → MANET</text>')
    s.append('<line x1="580" x2="580" y1="200" y2="310" stroke="#000" stroke-dasharray="1 2"/>')
    s.append('</svg>')
    return '\n'.join(s)


def disenos():
    guardar('bloques_andes.svg', bloques(
        'ANDES-64', 'Industrias Andinas de Cómputo', 'máquina de registros, 64 bits',
        ['R0–R15 de 64 bits', 'R13 = SP, R14 = LR', 'MAR, MDR'], ['Z  N  C  V  I', '(registro FR, 8 bits)'],
        ['RAM 4 KB, por byte, big-endian', 'caché L1 128 B + L2 512 B', 'pila en RAM (crece hacia abajo)'],
        '64 bits', '12 bits', '12 señales', ['IN / OUT (modos D H C F)', 'NIC: NSEND / NRECV']))
    guardar('bloques_orinoco.svg', bloques(
        'ORINOCO-32', 'Orinoco Systems S.A.', 'máquina de pila, 32 bits',
        ['pila de datos: 32 × 32 bits', 'pila de retorno: 16', 'SP (5 b), RSP (4 b)'], ['O (desbordamiento)', 'E (error de pila)'],
        ['8 KB, por byte, little-endian', 'sin caché', 'palabras de 32 bits'],
        '32 bits', '13 bits', '8 señales', ['out / outc', 'NIC: send / recv, bswap']))
    guardar('bloques_caribe.svg', bloques(
        'CARIBE-16', 'Compañía Caribeña de Calculadoras', 'máquina de acumulador, 16 bits',
        ['ACC (16 bits)', 'X índice (16 bits)', 'PC (10 b), IR (16 b)'], ['Z  N  C', '(sin desbordamiento)'],
        ['1024 palabras de 16 bits', 'direccionable por palabra', 'sin pila (JSR estilo PDP-8)'],
        '16 bits', '10 bits', '6 señales', ['OUT (decimal / carácter)', 'NIC de 8 bits: NSND / NRCV']))

    guardar('capas.svg', G.capas([
        ('Aplicación (programas en 3 lenguajes ensambladores distintos)', 'coordinador.a64 · cliente_ping.a64 · servidor.a64 · servidor.o32 · servidor.c16', 0),
        ('CPU heterogéneas: ANDES-64 · ORINOCO-32 · CARIBE-16', 'cada una con su ISA binaria, registros, banderas, memoria y reloj (8, 5 y 3 instr./tick)', 1),
        ('NIC de cada fabricante  ↔  PDU canónica', 'byte 0 destino/origen · byte 1 tipo · enteros de 32 bits big-endian (orden de red)', 2),
        ('Capa de red: AODV simplificado', 'RREQ por inundación · RREP por la ruta inversa · tiempo de vida · reparación local', 3),
        ('Capa de enlace y medio de radio', 'alcance 100 m · 1 tick por salto · pérdida p · 3 reintentos MAC · movilidad random waypoint', 4),
    ]))
    guardar('formatos.svg', G.campos_bits([
        ('ANDES-64  F6 (16–40 b)', [('opcode', 16), ('modo', 2), ('rd', 4), ('inm', 16), ('relleno', 2)]),
        ('ORINOCO-32  1 B', [('op', 8)]),
        ('ORINOCO-32  2 B', [('op', 8), ('inm8', 8)]),
        ('ORINOCO-32  3 B', [('op', 8), ('dir16 (LE)', 16)]),
        ('ORINOCO-32  5 B', [('op', 8), ('inm32 (little-endian)', 32)]),
        ('CARIBE-16  fija', [('op', 5), ('M', 1), ('operando', 10)]),
    ], total=40))
    guardar('pdu.svg', G.campos_bits([
        ('PDU enviada por la CPU', [('destino', 8), ('tipo', 8), ('valor int32 big-endian', 32)]),
        ('PDU entregada a la CPU', [('origen', 8), ('tipo', 8), ('valor int32 big-endian', 32)]),
    ], total=48))
    # secuencia AODV (E1)
    ancho, alto = 640, 330
    xs = {1: 110, 2: 320, 3: 530}
    nom = {1: 'ANDES-64 #1', 2: 'ORINOCO-32 #2', 3: 'CARIBE-16 #3'}
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" font-family="Arial, Helvetica, sans-serif" font-size="10">' % (ancho, alto, ancho, alto),
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#52514e"/></marker></defs>']
    cols = {1: G.SERIE[0], 2: G.SERIE[1], 3: G.SERIE[2]}
    for n, x in xs.items():
        s.append('<rect x="%d" y="6" width="120" height="22" fill="#ffffff" stroke="#000000"/>' % (x - 60))
        s.append('<text x="%d" y="21" text-anchor="middle" fill="#000000" font-weight="bold">%s</text>' % (x, nom[n]))
        s.append('<line x1="%d" x2="%d" y1="28" y2="%d" stroke="#b9b8b3" stroke-dasharray="4 3"/>' % (x, x, alto - 4))
    msgs = [(1, 2, 'RREQ (broadcast) busca #3', '#555555'), (2, 3, 'RREQ reenviado (saltos = 2)', '#555555'),
            (3, 2, 'RREP (unicast, ruta inversa)', '#555555'), (2, 1, 'RREP → ruta a #3 vía #2', '#555555'),
            (1, 2, 'DATOS SUMA(1000)', '#000000'), (2, 3, 'DATOS reenviado por #2', '#000000'),
            (3, 2, 'RESULTADO(500500)', '#000000'), (2, 1, 'RESULTADO reenviado', '#000000')]
    y = 50
    for a, b, t, c in msgs:
        x1, x2 = xs[a], xs[b]
        s.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s" stroke-width="1.6" marker-end="url(#a)"/>' % (x1, x2 - (6 if x2 > x1 else -6), y, y + 14, c))
        s.append('<text x="%d" y="%d" text-anchor="middle" fill="#0b0b0b">%s</text>' % ((x1 + x2) / 2, y - 3, t))
        y += 34
        if t.startswith('DATOS reenviado'):
            s.append('<rect x="%d" y="%d" width="110" height="22" fill="#ffffff" stroke="#000000"/>' % (xs[3] - 55, y - 12))
            s.append('<text x="%d" y="%d" text-anchor="middle">calcula 1+…+1000</text>' % (xs[3], y + 3))
            y += 22
    s.append('</svg>')
    guardar('secuencia.svg', '\n'.join(s))
    # topologías
    def topologia(nodos, ancho_m, alto_m, nombre, alcance=100):
        esc = 600 / (ancho_m + 2 * alcance)
        W, H = 620, int((alto_m + 2 * alcance) * esc) + 20
        s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" font-family="Arial, Helvetica, sans-serif" font-size="10">' % (W, H, W, H)]
        pos = {i: (10 + (x + alcance) * esc, 10 + (y + alcance) * esc) for i, (m, x, y) in nodos.items()}
        for i, (m, x, y) in nodos.items():
            s.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="#e7e6e2"/>' % (pos[i] + (alcance * esc,)))
        ids = sorted(nodos)
        for k, i in enumerate(ids):
            for j in ids[k + 1:]:
                (_, xa, ya), (_, xb, yb) = nodos[i], nodos[j]
                if ((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5 <= alcance:
                    s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#8d8d8d" stroke-width="1.5"/>' % (pos[i] + pos[j]))
        idx = {'ANDES-64': 0, 'ORINOCO-32': 1, 'CARIBE-16': 2}
        for i, (m, x, y) in nodos.items():
            s.append('<circle cx="%.1f" cy="%.1f" r="12" fill="%s" stroke="#fcfcfb" stroke-width="2"/>' % (pos[i] + (G.SERIE[idx[m]],)))
            s.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#ffffff" font-weight="bold">%d</text>' % (pos[i][0], pos[i][1] + 4, i))
            s.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#0b0b0b">%s</text>' % (pos[i][0], pos[i][1] + 26, m))
        s.append('</svg>')
        guardar(nombre, '\n'.join(s))
    topologia({1: ('ANDES-64', 10, 30), 2: ('ORINOCO-32', 100, 30), 3: ('CARIBE-16', 190, 30)}, 250, 60, 'topo_e1.svg')
    topologia({i: (m, 20 + 80 * (i - 1), 30) for i, m in enumerate(['ANDES-64', 'ORINOCO-32', 'CARIBE-16', 'ANDES-64', 'ORINOCO-32'], 1)}, 400, 60, 'topo_e3.svg')
    topologia({1: ('ANDES-64', 100, 100), 2: ('ORINOCO-32', 160, 100), 3: ('CARIBE-16', 50, 60), 4: ('ANDES-64', 60, 150)}, 220, 180, 'topo_e4.svg')
    # clases
    guardar('clases.svg', G.cajas_uml({
        'manet (CLI)': (10, 10, 180, ['ESCENARIOS e1..e4'], ['ejecutar(nombre)', 'barrido()', 'tiempos_servicio()']),
        'visor (tkinter)': (230, 10, 170, ['lienzo, bitácora'], ['animar(escenario)']),
        'Red': (10, 160, 200, ['nodos, t, p, rnd', 'en_vuelo, eventos', 'm (métricas)'], ['paso()', 'correr(max, hasta)', '_transmitir()', '_recibir()', '_enviar_datos()', '_descubrir()', '_desde_nic()', '_mover()', 'resumen()']),
        'Nodo': (250, 160, 170, ['id, modelo, ipc', 'x, y, alcance, velocidad', 'rutas, pendientes', 'buscando, vistos', 'energia'], []),
        'Paquete': (460, 160, 170, ['clase: DATOS|RREQ|RREP', 'origen, destino, datos', 'saltos, t0, rid'], []),
        'arquitecturas': (250, 340, 170, ['MODELOS, IPC'], ['crear(modelo, prog)']),
        'Andes64': (10, 460, 150, ['cpu (Tarea 17)'], ['paso()', 'cargar_fuente()']),
        'Orinoco32': (240, 460, 150, ['mem 8 KB LE', 'pila[32], ret[16]'], ['paso()', 'ensamblar()']),
        'Caribe16': (460, 460, 150, ['mem 1024×16', 'acc, x, Z N C'], ['paso()', 'ensamblar()']),
    }, [('manet (CLI)', 'Red', 'construye'), ('visor (tkinter)', 'Red', 'anima'), ('Red', 'Nodo', '*'), ('Red', 'Paquete', 'crea'),
        ('Nodo', 'arquitecturas', 'cpu'), ('arquitecturas', 'Andes64', ''), ('arquitecturas', 'Orinoco32', ''),
        ('arquitecturas', 'Caribe16', '')], 650, 560))
    guardar('flujo_tick.svg', G.flujo([
        {'t': 'ini', 'x': 'Red.paso()   (t ← t + 1)'},
        {'t': 'proc', 'x': 'mover los nodos (random waypoint)'},
        {'t': 'proc', 'x': 'entregar los paquetes cuyo\ntiempo de llegada es t'},
        {'t': 'proc', 'x': 'para cada nodo no detenido: ejecutar\nIPC instrucciones de SU CPU'},
        {'t': 'dec', 'x': '¿la CPU ejecutó SEND?', 'si': '_desde_nic: armar Paquete DATOS\ny _enviar_datos'},
        {'t': 'proc', 'x': 'vencimientos: reintentar RREQ o\ndescartar pendientes'},
        {'t': 'fin', 'x': 'fin del tick'},
    ]))
    guardar('flujo_datos.svg', G.flujo([
        {'t': 'ini', 'x': '_enviar_datos(nodo, paquete)'},
        {'t': 'dec', 'x': '¿hay ruta vigente al destino?', 'si': 'encolar en pendientes;\nsi no se busca aún: RREQ'},
        {'t': 'proc', 'x': 'renovar tiempo de vida de la ruta'},
        {'t': 'proc', 'x': 'transmitir al siguiente salto\n(hasta 3 intentos MAC)'},
        {'t': 'dec', 'x': '¿falló (fuera de alcance o 3 pérdidas)?', 'si': 'ruptura: borrar rutas por ese vecino\ny reintentar (reparación local)'},
        {'t': 'fin', 'x': 'llegará al vecino en t + 1'},
    ]))


def main():
    resultados()
    isa_tablas()
    disenos()
    print('figuras generadas en', FIGS)


if __name__ == '__main__':
    main()
