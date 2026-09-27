# -*- coding: utf-8 -*-
"""Visor gráfico (tkinter, biblioteca estándar) de la simulación de la MANET.

Dibuja cada nodo con el color de su fabricante, su alcance de radio, los enlaces vigentes,
los paquetes en vuelo y las rutas activas hacia el destino de los PING; a la derecha
muestra la bitácora de eventos y la salida del nodo principal.
"""

import tkinter as tk

import manet

COLORES = {'ANDES-64': '#2a78d6', 'ORINOCO-32': '#eb6834', 'CARIBE-16': '#1baf7a'}
CLASES = {'DATOS': '#d62828', 'RREQ': '#8d8d8d', 'RREP': '#7b2cbf'}


def animar(nombre, ticks_por_cuadro=4, **kw):
    red, principal, limite = manet.ESCENARIOS[nombre](**kw)
    raiz = tk.Tk()
    raiz.title('MANET heterogénea - escenario %s' % nombre)
    escala = min(640 / red.ancho, 480 / max(red.alto, 120))
    ancho, alto = int(red.ancho * escala) + 40, int(max(red.alto, 120) * escala) + 40
    lienzo = tk.Canvas(raiz, width=ancho, height=alto, bg='white')
    lienzo.grid(row=0, column=0, rowspan=2)
    bitacora = tk.Text(raiz, width=62, height=26, font=('Consolas', 8))
    bitacora.grid(row=0, column=1, sticky='nsew')
    estado = tk.Label(raiz, anchor='w', justify='left', font=('Consolas', 9))
    estado.grid(row=1, column=1, sticky='nsew')
    visto = [0]
    pausa = [False]

    def xy(n):
        return 20 + n.x * escala, 20 + n.y * escala

    def dibujar():
        lienzo.delete('all')
        for n in red.nodos.values():
            x, y = xy(n)
            r = n.alcance * escala
            lienzo.create_oval(x - r, y - r, x + r, y + r, outline='#e6e6e6')
        for i, j in red.enlaces():
            a, b = xy(red.nodos[i]), xy(red.nodos[j])
            lienzo.create_line(*a, *b, fill='#b0b0b0')
        for n in red.nodos.values():                 # rutas activas (siguiente salto)
            for destino, (sig, saltos, expira) in n.rutas.items():
                if expira >= red.t and sig in red.nodos:
                    a, b = xy(n), xy(red.nodos[sig])
                    lienzo.create_line(*a, *b, fill='#c9a0dc', width=2, arrow='last')
        for _, rid, eid, p in red.en_vuelo:
            a, b = xy(red.nodos[eid]), xy(red.nodos[rid])
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            lienzo.create_rectangle(mx - 4, my - 4, mx + 4, my + 4, fill=CLASES[p.clase], outline='')
        for n in red.nodos.values():
            x, y = xy(n)
            borde = 'black' if not n.cpu.detenida else '#aaaaaa'
            lienzo.create_oval(x - 11, y - 11, x + 11, y + 11, fill=COLORES[n.modelo], outline=borde, width=2)
            lienzo.create_text(x, y, text=str(n.id), fill='white', font=('Arial', 9, 'bold'))
            lienzo.create_text(x, y + 19, text=n.modelo, font=('Arial', 7))
        y0 = 12
        for m, c in COLORES.items():
            lienzo.create_oval(ancho - 120, y0 - 5, ancho - 110, y0 + 5, fill=c, outline='')
            lienzo.create_text(ancho - 105, y0, text=m, anchor='w', font=('Arial', 8))
            y0 += 14
        for k, c in CLASES.items():
            lienzo.create_rectangle(ancho - 120, y0 - 4, ancho - 112, y0 + 4, fill=c, outline='')
            lienzo.create_text(ancho - 105, y0, text=k, anchor='w', font=('Arial', 8))
            y0 += 14
        for linea in red.eventos[visto[0]:]:
            bitacora.insert('end', linea + '\n')
        visto[0] = len(red.eventos)
        bitacora.see('end')
        s = red.resumen()
        estado.config(text='t = %d ticks (%.2f s)   datos: %d enviados, %d entregados (PDR %.2f)\n'
                           'RREQ tx=%d  RREP tx=%d  rupturas=%d  retransmisiones=%d\n'
                           'salida #%d: %s\n[espacio] pausa'
                      % (red.t, red.t * 0.01, s['datos_app'], s['entregados'], s['pdr'],
                         s['tx_rreq'], s['tx_rrep'], s['rupturas'], s['retransmisiones'], principal,
                         ''.join(red.nodos[principal].cpu.salida).strip()[-60:]))

    def cuadro():
        if not pausa[0] and red.t < limite and not red.nodos[principal].cpu.detenida:
            for _ in range(ticks_por_cuadro):
                red.paso()
            dibujar()
        raiz.after(30, cuadro)

    raiz.bind('<space>', lambda e: pausa.__setitem__(0, not pausa[0]))
    dibujar()
    cuadro()
    raiz.mainloop()
