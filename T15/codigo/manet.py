# -*- coding: utf-8 -*-
"""Emulador de una MANET heterogénea de computadores von Neumann.

  python manet.py e1 [-v]                       cálculo distribuido multi-salto (3 fabricantes)
  python manet.py e2 [--velocidad 5] [--semilla 1] [-v]   movilidad (random waypoint)
  python manet.py e3 [--perdida 0.2] [-v]       enlaces con pérdidas, cadena de 4 saltos
  python manet.py e4 [-v]                       tiempo de servicio de cada arquitectura
  python manet.py visor e2 [...]                animación en tkinter (misma simulación)
  python manet.py barrido                       ejecuta todos los experimentos del informe
"""

import argparse
import json
import os
import statistics
import sys

from red import Nodo, Red


def e1(verboso=False, **_):
    """Cadena fija 1-2-3: cálculo distribuido multi-salto entre los tres fabricantes.
    El ANDES-64 (#1) no alcanza al CARIBE-16 (#3); el ORINOCO-32 (#2) hace de
    enrutador intermedio y a la vez atiende peticiones."""
    red = Red(ancho=250, alto=60, verboso=verboso)
    red.agregar(Nodo(1, 'ANDES-64', 'coordinador', 10, 30, entradas=[2, 2, 10, 3, 1000]))
    red.agregar(Nodo(2, 'ORINOCO-32', 'servidor', 100, 30))
    red.agregar(Nodo(3, 'CARIBE-16', 'servidor', 190, 30))
    return red, 1, 20000


def e2(velocidad=5.0, semilla=1, pings=40, verboso=False, **_):
    """Movilidad: 6 nodos (2 por fabricante), random waypoint en 300 m x 300 m.
    Alcance de 100 m. El ANDES-64 #1 hace PING al CARIBE-16 #6."""
    red = Red(ancho=300, alto=300, semilla=semilla, verboso=verboso)
    r = red.rnd
    modelos = ['ANDES-64', 'ORINOCO-32', 'CARIBE-16', 'ANDES-64', 'ORINOCO-32', 'CARIBE-16']
    for i, m in enumerate(modelos, 1):
        prog = 'cliente_ping' if i == 1 else 'servidor'
        ent = [6, pings, 160, 200] if i == 1 else None
        red.agregar(Nodo(i, m, prog, r.uniform(0, 300), r.uniform(0, 300), entradas=ent,
                         velocidad=velocidad, pausa=100))
    return red, 1, 60000


def e3(perdida=0.2, semilla=1, pings=30, verboso=False, **_):
    """Pérdidas: cadena de 5 nodos separados 80 m, 4 saltos de #1 a #5.
    Cada transmisión se pierde con probabilidad `perdida`."""
    red = Red(ancho=400, alto=60, p_perdida=perdida, semilla=semilla, verboso=verboso)
    modelos = ['ANDES-64', 'ORINOCO-32', 'CARIBE-16', 'ANDES-64', 'ORINOCO-32']
    for i, m in enumerate(modelos, 1):
        prog = 'cliente_ping' if i == 1 else 'servidor'
        ent = [5, pings, 160, 200] if i == 1 else None
        red.agregar(Nodo(i, m, prog, 20 + 80 * (i - 1), 30, entradas=ent))
    return red, 1, 60000


def e4(n=300, verboso=False, **_):
    """Heterogeneidad: la misma SUMA(n) a un servidor de cada fabricante, a un salto.
    Compara el tiempo de servicio de cada arquitectura."""
    red = Red(ancho=200, alto=200, verboso=verboso)
    red.agregar(Nodo(1, 'ANDES-64', 'coordinador', 100, 100, entradas=[3, 2, n, 3, n, 4, n]))
    red.agregar(Nodo(2, 'ORINOCO-32', 'servidor', 160, 100))
    red.agregar(Nodo(3, 'CARIBE-16', 'servidor', 50, 60))
    red.agregar(Nodo(4, 'ANDES-64', 'servidor', 60, 150))
    return red, 1, 40000


ESCENARIOS = {'e1': e1, 'e2': e2, 'e3': e3, 'e4': e4}


def tiempos_servicio(red):
    """Para cada SUMA entregada a un servidor, ticks hasta que ese servidor envía el RESULTADO."""
    res = {}
    for t_llega, origen, destino, tipo, valor, _, _ in red.entregas:
        if tipo != 1:
            continue
        for t_env, o, d, tp, v in red.envios:
            if o == destino and d == origen and tp == 2 and t_env >= t_llega:
                res[red.nodos[destino].nombre] = (t_env - t_llega, v)
                break
    return res


def ejecutar(nombre, **kw):
    red, principal, limite = ESCENARIOS[nombre](**kw)
    red.log('escenario %s: %s' % (nombre, (ESCENARIOS[nombre].__doc__ or '').strip().split('\n')[0]))
    for n in red.nodos.values():
        red.log('  %-12s %-38s programa=%-13s pos=(%.0f, %.0f) %d instr/tick'
                % (n.nombre, n.cpu.FABRICANTE, n.programa, n.x, n.y, n.ipc))
    red.correr(limite, hasta=principal)
    return red


def imprimir_resumen(red, principal=1):
    s = red.resumen()
    print('\n=== salida del programa del nodo #%d ===' % principal)
    print(''.join(red.nodos[principal].cpu.salida).rstrip())
    print('\n=== métricas de la red ===')
    for k, v in s.items():
        if isinstance(v, float):
            v = round(v, 3)
        print('  %-16s %s' % (k, v))
    ts = tiempos_servicio(red)
    if ts:
        print('\n=== tiempo de servicio de SUMA ===')
        for nombre, (t, v) in ts.items():
            print('  %-12s %6d ticks  resultado=%d' % (nombre, t, v))
    errores = [n for n in red.nodos.values() if n.error]
    for n in errores:
        print('  ERROR en %s: %s' % (n.nombre, n.error))


def barrido(salida):
    """Experimentos del informe (varias semillas por punto)."""
    res = {}
    red = ejecutar('e1')
    res['e1'] = {'salida': ''.join(red.nodos[1].cpu.salida), 'resumen': red.resumen(),
                 'eventos': red.eventos}
    print('e1 listo')
    res['e2'] = []
    for v in (0.0, 2.0, 5.0, 10.0, 20.0):
        filas = []
        for semilla in range(1, 6):
            red = ejecutar('e2', velocidad=v, semilla=semilla)
            filas.append(dict(red.resumen(), salida=''.join(red.nodos[1].cpu.salida).strip()))
        res['e2'].append({'velocidad': v, 'corridas': filas})
        print('e2 v=%s: PDR media %.3f' % (v, statistics.mean(f['pdr'] for f in filas)))
    res['e3'] = []
    for p in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        filas = []
        for semilla in range(1, 6):
            red = ejecutar('e3', perdida=p, semilla=semilla)
            filas.append(dict(red.resumen(), salida=''.join(red.nodos[1].cpu.salida).strip()))
        res['e3'].append({'perdida': p, 'corridas': filas})
        print('e3 p=%s: PDR media %.3f' % (p, statistics.mean(f['pdr'] for f in filas)))
    res['e4'] = []
    for n in (10, 100, 300, 1000):
        red = ejecutar('e4', n=n)
        res['e4'].append({'n': n, 'servicio': tiempos_servicio(red),
                          'salida': ''.join(red.nodos[1].cpu.salida)})
        print('e4 n=%d listo' % n)
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    print('resultados guardados en', salida)


def main():
    p = argparse.ArgumentParser(description='Emulador de MANET heterogénea')
    p.add_argument('escenario', choices=list(ESCENARIOS) + ['visor', 'barrido'])
    p.add_argument('extra', nargs='?', help='escenario a animar (con "visor")')
    p.add_argument('-v', '--verboso', action='store_true', help='muestra la bitácora de eventos')
    p.add_argument('--velocidad', type=float, default=5.0, help='m/s (e2)')
    p.add_argument('--perdida', type=float, default=0.2, help='probabilidad de pérdida (e3)')
    p.add_argument('--semilla', type=int, default=1)
    p.add_argument('--n', type=int, default=300, help='n de SUMA(n) (e4)')
    p.add_argument('--salida', default=os.path.join('resultados', 'resultados.json'))
    a = p.parse_args()
    kw = dict(velocidad=a.velocidad, perdida=a.perdida, semilla=a.semilla, n=a.n)
    if a.escenario == 'barrido':
        os.makedirs(os.path.dirname(a.salida) or '.', exist_ok=True)
        return barrido(a.salida)
    if a.escenario == 'visor':
        import visor
        return visor.animar(a.extra or 'e2', **kw)
    red = ejecutar(a.escenario, verboso=a.verboso, **kw)
    print(red.mapa())
    imprimir_resumen(red)
    return 0


if __name__ == '__main__':
    sys.exit(main())
