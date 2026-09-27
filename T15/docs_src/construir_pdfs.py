# -*- coding: utf-8 -*-
"""Genera el PDF ÚNICO de la entrega a partir de los HTML de docs_src/.

  python docs_src/construir_pdfs.py

Lineamientos operativos, sección 3.1.1, observación (a): se entrega un único archivo que
contiene todos los literales, estructurado de manera que sea clara la inclusión de cada uno:
  (a) marco teórico, (b) descripción y justificación, (c) diseño, (d) código fuente,
  (e) manual de usuario y técnico, (f) experimentación y análisis de resultados.

1. Lee los autores de ../autores.txt (una persona por línea) para la portada y la cabecera.
2. Regenera las figuras (generar_figuras.py) a partir de los resultados de los experimentos.
3. Une los capítulos, agrega el código fuente completo como literal (d) y lo imprime a PDF
   con Microsoft Edge o Google Chrome en modo sin interfaz.
"""

import glob
import html
import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
TAREA = os.path.dirname(AQUI)
CODIGO = os.path.join(TAREA, 'codigo')
CONFIG = {
    'curso': 'Lenguajes de Programación',
    'universidad': 'Universidad Nacional de Colombia',
    'depto': 'Ingeniería de Sistemas y Computación',
    'profesor': 'Jorge Eduardo Ortiz Triviño',
}
NAVEGADORES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/microsoft-edge',
]
# archivos de código que no se transcriben en el PDF (datos generados)
EXCLUIR = ('.json', '.obj', '.pyc')
EXTENSIONES = ('.py', '.asm', '.a64', '.o32', '.c16')


def autores():
    ruta = os.path.join(TAREA, 'autores.txt')
    with open(ruta, encoding='utf-8') as f:
        lineas = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    return lineas or ['(escriba los autores en autores.txt)']


def capitulos():
    """[(literal, nombre, subtitulo, meta, cuerpo_html)] en el orden de los archivos."""
    res = []
    for fuente in sorted(glob.glob(os.path.join(AQUI, '0*.html'))):
        with open(fuente, encoding='utf-8') as f:
            doc = f.read()
        ini = doc.index('<!--PORTADA|')
        fin = doc.index('-->', ini)
        _, titulo, sub, meta = doc[ini:fin].split('|')
        literal = re.search(r'Entregable \((\w)\)', meta).group(1)
        tarea, nombre = [x.strip() for x in titulo.split('—', 1)]
        cuerpo = doc[fin + 3:doc.rindex('</body>')].replace('{{CABECERA}}', '')
        cuerpo = re.sub(r'\{\{INCLUIR:([^}]+)\}\}',
                        lambda m: open(os.path.join(AQUI, m.group(1)), encoding='utf-8').read(), cuerpo)
        # los capítulos usan h1 para sus partes: pasan a ser subtítulos del capítulo
        cuerpo = re.sub(r'<h1( class="salto")?>', lambda m: '<h2 class="parte%s">' % (' salto' if m.group(1) else ''), cuerpo)
        cuerpo = cuerpo.replace('</h1>', '</h2>')
        res.append((literal, nombre, tarea, sub, re.sub(r'Entregable \(\w\) · ', '', meta), cuerpo))
    return res


def codigo_fuente():
    archivos = []
    for raiz, dirs, nombres in os.walk(CODIGO):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for n in sorted(nombres):
            if n.endswith(EXTENSIONES) and not n.endswith(EXCLUIR):
                archivos.append(os.path.join(raiz, n))
    rel = [os.path.relpath(a, TAREA).replace('\\', '/') for a in archivos]
    partes = ['<p>Se transcribe a continuación el código fuente completo de la herramienta construida. '
              'Todo está escrito en Python 3 usando únicamente la biblioteca estándar (no hay librerías '
              'externas ni versiones adicionales que declarar) y en los lenguajes ensambladores de las '
              'máquinas. Los mismos archivos se entregan en la carpeta <code>codigo/</code>; los datos '
              'generados por los experimentos (<code>resultados/*.json</code>) no se transcriben.</p>',
              '<h3>Estructura de archivos</h3><pre>%s</pre>' % '\n'.join(
                  '%-58s %6d líneas' % (r, sum(1 for _ in open(a, encoding='utf-8'))) for r, a in zip(rel, archivos))]
    for r, a in zip(rel, archivos):
        with open(a, encoding='utf-8') as f:
            texto = f.read()
        partes.append('<h3 class="archivo">%s</h3><pre class="codigo">%s</pre>' % (html.escape(r), html.escape(texto)))
    return ('d', 'Código fuente completo', None, None, None, '\n'.join(partes))


def documento():
    caps = capitulos()
    caps.append(codigo_fuente())
    caps.sort(key=lambda c: c[0])
    tarea, sub, meta = caps[0][2], caps[0][3], caps[0][4]
    a = '<br>'.join(html.escape(x) for x in autores())
    indice = ''.join('<tr><td class="lit">(%s)</td><td>%s</td></tr>' % (c[0], c[1]) for c in caps)
    salida = ['<!doctype html><html lang="es"><head><meta charset="utf-8"><title>%s</title>'
              '<link rel="stylesheet" href="../estilo.css"></head><body>' % html.escape(tarea),
              '<section class="portada"><div class="inst">%s<br>%s</div><div><h1>%s</h1><div class="sub">%s</div></div>'
              '<div class="autores">Presentado por:<br>%s</div><div class="datos">%s<br>Presentado a: %s</div></section>'
              % (CONFIG['universidad'], CONFIG['depto'], tarea, sub, a, CONFIG['curso'], CONFIG['profesor']),
              '<section class="indice"><h1>Contenido de la entrega</h1>'
              '<p>Documento único con todos los entregables exigidos a una tarea obligatoria automatizada '
              '(Lineamientos operativos del curso, sección 3.1.1). Cada literal corresponde a un capítulo:</p>'
              '<table class="indice">%s</table></section>' % indice]
    for literal, nombre, _, _, _, cuerpo in caps:
        salida.append('<section class="capitulo"><div class="cabecera">%s · Autores: %s · %s</div>'
                      '<h1 class="cap">(%s) %s</h1>%s</section>'
                      % (html.escape(tarea), html.escape(', '.join(autores())), CONFIG['curso'], literal, nombre, cuerpo))
    salida.append('</body></html>')
    return tarea, '\n'.join(salida)


def main():
    sys.path.insert(0, AQUI)
    import generar_figuras
    generar_figuras.main()
    nav = next((n for n in NAVEGADORES if os.path.exists(n)), None) or shutil.which('msedge') or shutil.which('chrome')
    if not nav:
        sys.exit('No se encontró Edge ni Chrome para imprimir a PDF.')
    tmp_dir = os.path.join(AQUI, '_construccion')
    os.makedirs(tmp_dir, exist_ok=True)
    tarea, doc = documento()
    tmp = os.path.join(tmp_dir, 'entrega.html')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(doc)
    nombre = re.sub(r'\W+', '_', tarea).strip('_') + '_Entrega.pdf'
    pdf = os.path.join(TAREA, nombre)
    subprocess.run([nav, '--headless', '--disable-gpu', '--no-pdf-header-footer',
                    '--print-to-pdf=' + pdf, 'file:///' + tmp.replace('\\', '/')],
                   check=True, capture_output=True, timeout=180)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print('PDF generado:', nombre)


if __name__ == '__main__':
    main()
