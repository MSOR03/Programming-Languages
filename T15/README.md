# Tarea 15 — Diseño de un computador von Neumann sobre una MANET

Tarea obligatoria **automatizada** · Lenguajes de Programación · Ingeniería de Sistemas y Computación · Universidad Nacional de Colombia · Entrega: 28 de septiembre de 2026
Autores: Rodríguez Rodríguez Daniel Santiago · Olarte Ramírez Maicol Sebastián

Se resuelve el punto 1 (obligatorio): diseño **e implementación** de un emulador de una MANET heterogénea
con tres computadores von Neumann de fabricantes distintos (registros, memoria, banderas, buses, CPU,
código binario y lenguaje ensamblador diferentes):

| Modelo | Fabricante (ficticio) | Tipo | Palabra | Memoria | Ensamblador |
|---|---|---|---|---|---|
| ANDES-64 | Industrias Andinas de Cómputo | registros (el computador de la Tarea 9) | 64 bits | 4 KB, big-endian | `.a64` |
| ORINOCO-32 | Orinoco Systems S.A. | pila | 32 bits | 8 KB, little-endian | `.o32` |
| CARIBE-16 | Compañía Caribeña de Calculadoras | acumulador | 16 bits | 1024 palabras | `.c16` |

Los puntos 2 y 3 (opcionales, dificultad 2) no se abordan.

## Entrega

Según los lineamientos operativos del curso (sección 3.1.1, observación a), todos los entregables
de la tarea automatizada van en **un único PDF**: `Tarea_15_Entrega.pdf`, organizado por literales:

| Literal | Contenido |
|---|---|
| a | Marco teórico |
| b | Descripción y justificación del problema |
| c | Diseño de la solución |
| d | Código fuente completo (también en la carpeta `codigo/`) |
| e | Manual de usuario y manual técnico |
| f | Experimentación y análisis de resultados |

## Uso rápido (desde `codigo/`)

```
python manet.py e1 -v                    # cálculo distribuido multi-salto entre los 3 fabricantes
python manet.py e2 --velocidad 10        # movilidad (random waypoint)
python manet.py e3 --perdida 0.3         # enlaces con pérdidas, 4 saltos
python manet.py e4 --n 1000              # tiempo de servicio de cada arquitectura
python manet.py visor e2 --velocidad 10  # animación (tkinter)
python manet.py barrido                  # todos los experimentos del informe
```

## Regenerar el PDF

Escriba los autores en `autores.txt` (uno por línea) y ejecute `python docs_src/construir_pdfs.py`
(une los capítulos de `docs_src/` y el código fuente, y los imprime con Microsoft Edge o Google Chrome sin interfaz).
