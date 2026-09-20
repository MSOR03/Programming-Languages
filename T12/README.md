# Algoritmo de búsqueda de Grover — Qiskit + IBM Quantum

Implementación del algoritmo de Grover para buscar un elemento marcado en una lista
desordenada de 8 elementos (3 qubits), ejecutada en simulador y en hardware real de IBM.

## Archivos

| Archivo | Contenido |
|---|---|
| `Grover’s search algorithm.ipynb` | Notebook con la explicación, los diagramas de circuito y los histogramas |
| `grover.py` | El mismo algoritmo como script de consola |

## Cómo ejecutarlo

```bash
python3 -m venv .venv
.venv/bin/pip install qiskit qiskit-aer qiskit-ibm-runtime matplotlib pylatexenc

.venv/bin/python grover.py            # simulador ideal
.venv/bin/python grover.py --ruido    # simulador con el ruido real de ibm_sherbrooke
.venv/bin/python grover.py --ibm      # computador cuántico real de IBM
```

Para el modo `--ibm` hay que guardar una sola vez el token de [quantum.ibm.com](https://quantum.ibm.com):

```python
from qiskit_ibm_runtime import QiskitRuntimeService
QiskitRuntimeService.save_account(channel="ibm_quantum_platform", token="TU_TOKEN", overwrite=True)
```

## Cómo funciona

Con `n = 3` qubits el espacio de búsqueda es de `2³ = 8` elementos. El objetivo es `|101⟩`.

1. **Superposición.** Una `H` en cada qubit pone los 8 elementos en juego a la vez, cada uno con
   amplitud `1/√8`.
2. **Oráculo.** Invierte el signo de la amplitud del elemento buscado: `|101⟩ → -|101⟩`.
   Se construye con una `Z` multicontrolada (`H · MCX · H`) rodeada de puertas `X` en las
   posiciones donde el objetivo tiene un `0`.
3. **Difusor.** Refleja todas las amplitudes respecto a su promedio. Como la del objetivo quedó
   negativa, el promedio baja y esa amplitud salta muy por encima de las demás.
4. **Repetir.** Cada pasada (oráculo + difusor) gira el estado un ángulo fijo hacia la solución.
   El óptimo es `⌊(π/4)·√N⌋ = 2` iteraciones.
5. **Medir.**

**Ventaja:** 2 consultas al oráculo frente a las ~4 de una búsqueda clásica promedio — el
speedup cuadrático `O(√N)` vs `O(N)`.

## Resultados (1024 shots)

| Ejecución | Acierto en `|101⟩` |
|---|---|
| Simulador ideal (Aer) | **93.8 %** (teórico: 94.5 %) |
| Simulador con ruido de `ibm_sherbrooke` (Eagle) | **73.5 %** |
| **Hardware real: `ibm_marrakesh` (Heron r2, 156 qubits)** | **61.2 %** |
| Azar / clásico sin información | 12.5 % |

Ejecución real — job `danneplr85ps73fea9v0`, backend `ibm_marrakesh`:

```
|101>   627   61.2%   <-- objetivo
|100>    96    9.4%
|000>    58    5.7%
|110>    58    5.7%
|010>    49    4.8%
|011>    49    4.8%
|001>    46    4.5%
|111>    41    4.0%
```

## Análisis

**El algoritmo funciona en hardware real.** `|101⟩` sale 627 de 1024 veces: 6.5 veces más que el
segundo estado más frecuente y casi 5 veces por encima del 12.5 % que daría el azar. Con **2 consultas
al oráculo** frente a las ~4 de una búsqueda clásica promedio, la respuesta es inequívoca.

**Por qué el simulador ideal no da 100 %.** Grover es probabilístico. Cada iteración rota el vector de
estado un ángulo fijo hacia el eje de la solución, y con `N = 8` dos iteraciones lo dejan *casi* —pero no
exactamente— encima. La probabilidad teórica es 94.5 %, justo lo que devuelve Aer. Hacer **más**
iteraciones empeora el resultado: el estado se pasa de largo y vuelve a alejarse (*sobre-rotación*).
Es un algoritmo donde "más vueltas" no es mejor.

**Por qué el hardware pierde 33 puntos.** La causa principal se ve en la transpilación:

| | Profundidad | Puertas | Composición |
|---|---|---|---|
| Circuito lógico | 22 | 46 | `h`×23, `x`×16, `ccx`×4 |
| Transpilado a `ibm_marrakesh` | **139** | **187** | `sx`×74, `rz`×62, **`cz`×39**, `x`×9 |

1. **Descomposición al conjunto nativo.** Heron sólo ejecuta `rz`, `sx`, `x` y `cz`. Las 4 puertas
   Toffoli (`ccx`) del oráculo y el difusor no existen físicamente: cada una se descompone en ~6 `cz`
   más rotaciones. De 46 puertas lógicas se pasa a 187 físicas y la profundidad se multiplica por 6.
2. **Error por puerta de dos qubits.** Esas 39 `cz` son el cuello de botella: con un error típico de
   ~3×10⁻³ cada una, sólo por ellas se acumula ya alrededor de un 10 % de error, y se compone
   multiplicativamente con el resto.
3. **Decoherencia y error de lectura.** Un circuito de profundidad 139 tarda lo suficiente como para
   que `T₁`/`T₂` degraden el estado, y la medición final añade su propio 1–2 %.

El efecto neto es que **la distribución se aplana**: el pico del objetivo baja de 94 % a 61 % y los otros
siete estados suben desde casi cero hasta un 4–9 % cada uno. Nótese que `|100⟩` (9.4 %) destaca sobre
el resto — difiere del objetivo en un solo bit, la firma típica de un error de un qubit al final del circuito.

**Conclusión.** Grover demuestra la ventaja cuadrática de forma tangible, pero también deja ver el límite
de la era NISQ: con apenas 3 qubits y 2 iteraciones el ruido ya cuesta un tercio del acierto. Escalar a
espacios de búsqueda grandes —donde la ventaja `√N` sería realmente útil— exige muchas más
iteraciones y, por tanto, circuitos aún más profundos de los que el hardware actual tolera sin corrección
de errores. Ahí es donde entran las generaciones nuevas de IBM: **Heron** (el chip que usamos: puertas
`cz` sintonizables con mucho menos *crosstalk* que Eagle) y **Nighthawk**, cuya mayor conectividad
—cada qubit con más vecinos— reduce los `SWAP` que el transpilador debe insertar y con ellos la
profundidad efectiva. Menos profundidad y menos error por `cz` es exactamente lo que Grover necesita
para escalar.
