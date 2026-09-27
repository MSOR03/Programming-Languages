# -*- coding: utf-8 -*-
"""Gráficas SVG estáticas (solo biblioteca estándar) para los informes en PDF.
Paleta categórica validada: azul, naranja, aguamarina (en ese orden fijo)."""

import math

SERIE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
TINTA, TINTA2, REJILLA, EJE = '#000000', '#333333', '#e0e0e0', '#000000'


def _esc(t):
    return str(t).replace('&', '&amp;').replace('<', '&lt;')


def _ticks(lo, hi, n=5):
    if hi == lo:
        return [lo]
    paso = 10 ** math.floor(math.log10((hi - lo) / n))
    for m in (1, 2, 2.5, 5, 10):
        if (hi - lo) / (paso * m) <= n:
            paso *= m
            break
    t = math.ceil(lo / paso) * paso
    salida = []
    while t <= hi + 1e-12 * abs(hi):
        salida.append(round(t, 12))
        t += paso
    return salida


def _fmt(v):
    if v == 0:
        return '0'
    if abs(v) >= 1e5 or abs(v) < 1e-3:
        e = int(math.floor(math.log10(abs(v))))
        m = v / 10 ** e
        return ('10^%d' % e) if abs(m - 1) < 1e-9 else '%g·10^%d' % (m, e)
    return ('%g' % v).replace('.', ',')


def lineas(series, xlab, ylab, logx=False, logy=False, ancho=660, alto=300, ymin=None, ymax=None,
           referencia=None, etiquetas_directas=True):
    """series: [(nombre, [(x, y), ...])]. referencia: (valor_y, texto) línea horizontal."""
    ml, mr, mt, mb = 70, 150 if etiquetas_directas else 20, 18, 46
    W, H = ancho - ml - mr, alto - mt - mb
    fx = (lambda v: math.log10(v)) if logx else (lambda v: v)
    fy = (lambda v: math.log10(v)) if logy else (lambda v: v)
    xs = [fx(x) for _, p in series for x, _ in p]
    ys = [fy(y) for _, p in series for _, y in p]
    if referencia:
        ys.append(fy(referencia[0]))
    x0, x1 = min(xs), max(xs)
    y0 = fy(ymin) if ymin is not None else min(ys)
    y1 = fy(ymax) if ymax is not None else max(ys)
    if not logy and ymin is None:
        pad = (y1 - y0) * 0.08 or 1
        y0, y1 = y0 - pad, y1 + pad
    if x1 == x0:
        x1 = x0 + 1
    px = lambda v: ml + (fx(v) - x0) / (x1 - x0) * W
    py = lambda v: mt + H - (fy(v) - y0) / (y1 - y0) * H
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="Arial, Helvetica, sans-serif" font-size="11">' % (ancho, alto, ancho, alto)]
    paso_log = max(1, math.ceil((y1 - y0) / 7))
    yt = [10 ** k for k in range(math.ceil(y0), math.floor(y1) + 1) if k % paso_log == 0] if logy else _ticks(y0, y1)
    for t in yt:
        y = py(t)
        s.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s"/>' % (ml, ml + W, y, y, REJILLA))
        s.append('<text x="%d" y="%.1f" text-anchor="end" fill="%s">%s</text>'
                 % (ml - 6, y + 4, TINTA2, ('10^%d' % round(math.log10(t))) if logy else _fmt(t)))
    xt = [10 ** k for k in range(math.ceil(x0), math.floor(x1) + 1)] if logx else _ticks(x0, x1)
    for t in xt:
        x = px(t)
        s.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s"/>' % (x, x, mt + H, mt + H + 4, EJE))
        s.append('<text x="%.1f" y="%d" text-anchor="middle" fill="%s">%s</text>'
                 % (x, mt + H + 17, TINTA2, ('10^%d' % round(math.log10(t))) if logx else _fmt(t)))
    s.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s"/>' % (ml, ml + W, mt + H, mt + H, EJE))
    s.append('<text x="%.1f" y="%d" text-anchor="middle" fill="%s">%s</text>' % (ml + W / 2, alto - 6, TINTA2, _esc(xlab)))
    s.append('<text transform="translate(14 %.1f) rotate(-90)" text-anchor="middle" fill="%s">%s</text>'
             % (mt + H / 2, TINTA2, _esc(ylab)))
    if referencia:
        y = py(referencia[0])
        s.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s" stroke-dasharray="5 4"/>' % (ml, ml + W, y, y, TINTA2))
        s.append('<text x="%d" y="%.1f" fill="%s">%s</text>' % (ml + 6, y - 6, TINTA2, _esc(referencia[1])))
    usados = []
    for i, (nombre, pts) in enumerate(series):
        c = SERIE[i % len(SERIE)]
        d = ' '.join('%s%.1f,%.1f' % ('M' if k == 0 else 'L', px(x), py(y)) for k, (x, y) in enumerate(pts))
        s.append('<path d="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round"/>' % (d, c))
        for x, y in pts:
            s.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s" stroke="#fcfcfb" stroke-width="2"/>' % (px(x), py(y), c))
        if etiquetas_directas and pts:
            ly = py(pts[-1][1]) + 4
            while any(abs(ly - u) < 13 for u in usados):
                ly += 13
            usados.append(ly)
            s.append('<circle cx="%d" cy="%.1f" r="4" fill="%s"/>' % (ml + W + 10, ly - 4, c))
            s.append('<text x="%d" y="%.1f" fill="%s">%s</text>' % (ml + W + 18, ly, TINTA, _esc(nombre)))
    s.append('</svg>')
    return '\n'.join(s)


def barras(categorias, grupos, ylab, ancho=660, alto=300):
    """Barras agrupadas. categorias: etiquetas del eje x; grupos: [(nombre, [valores])]."""
    ml, mr, mt, mb = 70, 20, 30, 46
    W, H = ancho - ml - mr, alto - mt - mb
    vmax = max(v for _, vals in grupos for v in vals) * 1.1
    py = lambda v: mt + H - v / vmax * H
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="Arial, Helvetica, sans-serif" font-size="11">' % (ancho, alto, ancho, alto)]
    for t in _ticks(0, vmax):
        y = py(t)
        s.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s"/>' % (ml, ml + W, y, y, REJILLA))
        s.append('<text x="%d" y="%.1f" text-anchor="end" fill="%s">%s</text>' % (ml - 6, y + 4, TINTA2, _fmt(t)))
    ancho_cat = W / len(categorias)
    bw = min(28, (ancho_cat - 16) / len(grupos) - 2)
    for i, cat in enumerate(categorias):
        cx = ml + ancho_cat * (i + 0.5)
        x = cx - (bw + 2) * len(grupos) / 2
        for g, (nombre, vals) in enumerate(grupos):
            v = vals[i]
            y = py(v)
            r = 0
            s.append('<path d="M%.1f,%.1f V%.1f Q%.1f,%.1f %.1f,%.1f H%.1f Q%.1f,%.1f %.1f,%.1f V%.1f Z" fill="%s"/>'
                     % (x, mt + H, y + r, x, y, x + r, y, x + bw - r, x + bw, y, x + bw, y + r, mt + H, SERIE[g]))
            s.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-size="9">%s</text>'
                     % (x + bw / 2, y - 4, TINTA2, _fmt(v)))
            x += bw + 2
        s.append('<text x="%.1f" y="%d" text-anchor="middle" fill="%s">%s</text>' % (cx, mt + H + 17, TINTA2, _esc(cat)))
    s.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s"/>' % (ml, ml + W, mt + H, mt + H, EJE))
    s.append('<text transform="translate(14 %.1f) rotate(-90)" text-anchor="middle" fill="%s">%s</text>'
             % (mt + H / 2, TINTA2, _esc(ylab)))
    lx = ml
    for g, (nombre, _) in enumerate(grupos if len(grupos) > 1 else []):
        s.append('<rect x="%d" y="8" width="10" height="10" rx="2" fill="%s"/>' % (lx, SERIE[g]))
        s.append('<text x="%d" y="17" fill="%s">%s</text>' % (lx + 14, TINTA, _esc(nombre)))
        lx += 20 + 7 * len(nombre)
    s.append('</svg>')
    return '\n'.join(s)


def flujo(nodos, ancho=560):
    """Diagrama de flujo vertical.
    nodos: lista de dicts {t: 'ini'|'proc'|'dec'|'fin'|'es', x: texto, si: texto_lateral,
                           vuelve: indice_destino (lazo), etq: 'sí'/'no' para el lazo}
    En una decisión, la rama 'sí' sale a la derecha hacia una caja con `si`; la rama 'no'
    continúa hacia abajo (o, si tiene `vuelve`, la rama 'sí' regresa al nodo indicado)."""
    cx, bw, bh, gap = 200, 250, 34, 22
    ys, y = [], 14
    for n in nodos:
        ys.append(y)
        y += (bh + 14 if n['t'] == 'dec' else bh) + gap
    alto = y
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="Arial, Helvetica, sans-serif" font-size="10.5">' % (ancho, alto, ancho, alto),
         '<defs><marker id="f" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
         'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="%s"/></marker></defs>' % TINTA2]

    def texto(x, y, t, anchor='middle'):
        partes = t.split('\n')
        y0 = y - (len(partes) - 1) * 6.5
        for i, p in enumerate(partes):
            s.append('<text x="%.1f" y="%.1f" text-anchor="%s" fill="%s">%s</text>' % (x, y0 + 13 * i + 4, anchor, TINTA, _esc(p)))

    for i, n in enumerate(nodos):
        y = ys[i]
        h = bh + 14 if n['t'] == 'dec' else bh
        if n['t'] in ('ini', 'fin'):
            s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="17" fill="#ffffff" stroke="%s"/>' % (cx - bw / 2 + 10, y, bw - 20, h, TINTA))
        elif n['t'] == 'dec':
            s.append('<path d="M%d,%d L%d,%d L%d,%d L%d,%d Z" fill="#ffffff" stroke="%s"/>'
                     % (cx, y, cx + bw / 2, y + h / 2, cx, y + h, cx - bw / 2, y + h / 2, TINTA))
        elif n['t'] == 'es':
            s.append('<path d="M%d,%d H%d L%d,%d H%d Z" fill="#ffffff" stroke="%s"/>'
                     % (cx - bw / 2 + 10, y, cx + bw / 2, cx + bw / 2 - 10, y + h, cx - bw / 2, TINTA))
        else:
            s.append('<rect x="%d" y="%d" width="%d" height="%d" rx="0" fill="#ffffff" stroke="%s"/>' % (cx - bw / 2, y, bw, h, TINTA))
        texto(cx, y + h / 2, n['x'])
        if i + 1 < len(nodos) and n['t'] != 'fin' and not n.get('corta'):
            s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" marker-end="url(#f)"/>' % (cx, y + h, cx, ys[i + 1] - 1, TINTA2))
            if n['t'] == 'dec':
                s.append('<text x="%d" y="%d" fill="%s">no</text>' % (cx + 5, y + h + 13, TINTA2))
        if n['t'] == 'dec' and n.get('si'):
            bx = cx + bw / 2 + 24
            s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" marker-end="url(#f)"/>' % (cx + bw / 2, y + h / 2, bx - 1, y + h / 2, TINTA2))
            s.append('<text x="%d" y="%.1f" fill="%s">sí</text>' % (cx + bw / 2 + 4, y + h / 2 - 4, TINTA2))
            s.append('<rect x="%d" y="%.1f" width="%d" height="%d" rx="0" fill="#ffffff" stroke="%s" stroke-dasharray="4 2"/>' % (bx, y + h / 2 - 17, ancho - bx - 4, 34, TINTA))
            texto(bx + (ancho - bx - 4) / 2, y + h / 2, n['si'])
        if n.get('vuelve') is not None:
            j = n['vuelve']
            yd = ys[j] + (bh + 14 if nodos[j]['t'] == 'dec' else bh) / 2
            xl = cx - bw / 2 - 18 - 8 * (n.get('nivel', 0))
            ysal = y + h / 2
            x_ini = cx - bw / 2
            s.append('<path d="M%d,%.1f H%d V%.1f H%d" fill="none" stroke="%s" marker-end="url(#f)"/>'
                     % (x_ini, ysal, xl, yd, cx - bw / 2 - 1, TINTA2))
            if n.get('etq'):
                s.append('<text x="%d" y="%.1f" text-anchor="end" fill="%s">%s</text>' % (x_ini - 3, ysal - 4, TINTA2, n['etq']))
    s.append('</svg>')
    return '\n'.join(s)


def cajas_uml(cajas, relaciones, ancho, alto):
    """cajas: {nombre: (x, y, w, [atributos], [metodos])}; relaciones: [(a, b, etiqueta)]"""
    geo = {}
    for nombre, (x, y, w, at, me) in cajas.items():
        h = 22 + 13 * len(at) + 6 + 13 * len(me) + 6
        geo[nombre] = (x, y, w, h)
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="Arial, Helvetica, sans-serif" font-size="10">' % (ancho, alto, ancho, alto),
         '<defs><marker id="u" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
         'orient="auto"><path d="M0,0 L10,5 L0,10" fill="none" stroke="%s"/></marker></defs>' % TINTA2]
    for a, b, et in relaciones:
        xa, ya, wa, ha = geo[a]
        xb, yb, wb, hb = geo[b]
        ca, cb = (xa + wa / 2, ya + ha / 2), (xb + wb / 2, yb + hb / 2)
        # punto de salida/llegada en el borde de cada caja
        def borde(c, g, otro):
            x, y, w, h = g
            dx, dy = otro[0] - c[0], otro[1] - c[1]
            if dx == 0 and dy == 0:
                return c
            tx = (w / 2) / abs(dx) if dx else 1e9
            ty = (h / 2) / abs(dy) if dy else 1e9
            t = min(tx, ty)
            return c[0] + dx * t, c[1] + dy * t
        pa, pb = borde(ca, geo[a], cb), borde(cb, geo[b], ca)
        s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" marker-end="url(#u)"/>' % (pa + pb + (TINTA2,)))
        if et:
            s.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-style="italic">%s</text>'
                     % (pa[0] + 0.3 * (pb[0] - pa[0]) + 4, pa[1] + 0.3 * (pb[1] - pa[1]) - 3, TINTA2, _esc(et)))
    for nombre, (x, y, w, at, me) in cajas.items():
        h = geo[nombre][3]
        s.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#ffffff" stroke="%s"/>' % (x, y, w, h, TINTA))
        s.append('<rect x="%d" y="%d" width="%d" height="20" fill="#ffffff" stroke="%s"/>' % (x, y, w, TINTA))
        s.append('<text x="%.1f" y="%d" text-anchor="middle" font-weight="bold" fill="%s">%s</text>' % (x + w / 2, y + 14, TINTA, _esc(nombre)))
        yy = y + 33
        for t in at:
            s.append('<text x="%d" y="%d" fill="%s">%s</text>' % (x + 5, yy, TINTA2, _esc(t)))
            yy += 13
        s.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s"/>' % (x, x + w, yy - 7, yy - 7, EJE))
        yy += 3
        for t in me:
            s.append('<text x="%d" y="%d" fill="%s">%s</text>' % (x + 5, yy, TINTA, _esc(t)))
            yy += 13
    s.append('</svg>')
    return '\n'.join(s)


def capas(filas, ancho=640):
    """Diagrama de capas: filas = [(texto, subtitulo, color_indice)] de arriba abajo."""
    h, gap = 40, 8
    alto = len(filas) * (h + gap) + 4
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="Arial, Helvetica, sans-serif" font-size="11">' % (ancho, alto, ancho, alto)]
    fondos = ['#ffffff'] * 5
    for i, (t, sub, c) in enumerate(filas):
        y = 2 + i * (h + gap)
        s.append('<rect x="2" y="%d" width="%d" height="%d" rx="0" fill="%s" stroke="%s"/>' % (y, ancho - 4, h, fondos[c % 5], TINTA))
        s.append('<text x="12" y="%d" font-weight="bold" fill="%s">%s</text>' % (y + 17, TINTA, _esc(t)))
        s.append('<text x="12" y="%d" fill="%s">%s</text>' % (y + 32, TINTA2, _esc(sub)))
    s.append('</svg>')
    return '\n'.join(s)


def campos_bits(formatos, total=40, ancho=660):
    """formatos: [(nombre, [(campo, bits), ...])] -> filas de cajas proporcionales a los bits."""
    ml, fila = 150, 34
    esc = (ancho - ml - 10) / total
    alto = len(formatos) * fila + 26
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="Arial, Helvetica, sans-serif" font-size="10">' % (ancho, alto, ancho, alto)]
    colores = {'opcode': '#d9d9d9', 'relleno': '#f2f2f2'}
    for k in range(0, total + 1, 8):
        x = ml + k * esc
        s.append('<text x="%.1f" y="10" text-anchor="middle" fill="%s">%d</text>' % (x, TINTA2, k))
        s.append('<line x1="%.1f" x2="%.1f" y1="13" y2="%d" stroke="%s" stroke-dasharray="2 3"/>' % (x, x, alto, REJILLA))
    for i, (nombre, campos) in enumerate(formatos):
        y = 18 + i * fila
        s.append('<text x="4" y="%d" fill="%s">%s</text>' % (y + 17, TINTA, _esc(nombre)))
        x = ml
        for campo, b in campos:
            w = b * esc
            base = campo.split(' ')[0]
            fondo = colores.get(base, '#ffffff')
            s.append('<rect x="%.1f" y="%d" width="%.1f" height="24" fill="%s" stroke="%s"/>' % (x, y, w, fondo, TINTA2))
            s.append('<text x="%.1f" y="%d" text-anchor="middle" fill="%s">%s</text>' % (x + w / 2, y + 16, TINTA, _esc('%s·%d' % (campo, b) if w > 40 else str(b))))
            x += w
    s.append('</svg>')
    return '\n'.join(s)


def mapa_memoria(regiones, total=4096, ancho=660):
    """regiones: [(inicio, fin, etiqueta)] -> barra horizontal proporcional."""
    ml, y, h = 10, 30, 36
    W = ancho - 2 * ml
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d 110" width="%d" height="110" '
         'font-family="Arial, Helvetica, sans-serif" font-size="10">' % (ancho, ancho)]
    fondos = ['#d9d9d9', '#bfbfbf', '#ececec', '#ffffff', '#ffffff']
    for i, (a, b, et) in enumerate(regiones):
        x0, x1 = ml + a / total * W, ml + b / total * W
        s.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s" stroke="%s"/>' % (x0, y, x1 - x0, h, fondos[i % 5], TINTA2))
        s.append('<text x="%.1f" y="%d" text-anchor="middle" fill="%s">%s</text>' % ((x0 + x1) / 2, y + h / 2 + 4, TINTA, _esc(et)))
        s.append('<text x="%.1f" y="%d" text-anchor="start" fill="%s">0x%03X</text>' % (x0 + 1, y - 5 - 11 * (i % 2), TINTA2, a))
    s.append('<text x="%.1f" y="%d" text-anchor="end" fill="%s">0x1000 (tope, SP inicial)</text>' % (ml + W, y + h + 16, TINTA2))
    s.append('</svg>')
    return '\n'.join(s)
