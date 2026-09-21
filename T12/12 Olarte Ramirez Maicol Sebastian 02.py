"""
Algoritmo de busqueda de Grover (Qiskit).

Busca un elemento marcado dentro de una "base de datos" no ordenada de N = 2^n
elementos. Clasicamente se necesitan ~N/2 consultas; Grover lo logra en ~sqrt(N).

Rodriguez Rodriguez Daniel Santiago, Olarte Ramirez Maicol Sebastian
"""

import sys
from math import floor, pi, sqrt

from qiskit import QuantumCircuit, transpile

N = 3           # numero de qubits  ->  2^3 = 8 elementos
OBJETIVO = "101"  # el elemento que queremos encontrar
SHOTS = 1024


def oraculo(objetivo):
    """Marca el estado buscado invirtiendo su fase:  |x> -> -|x>  si x == objetivo."""
    qc = QuantumCircuit(N, name="Oraculo")
    # Qiskit numera los qubits al reves que la cadena de bits -> reversed()
    ceros = [i for i, bit in enumerate(reversed(objetivo)) if bit == "0"]
    if ceros:
        qc.x(ceros)                              # convierte el objetivo en |111>
    qc.h(N - 1)
    qc.mcx(list(range(N - 1)), N - 1)            # Toffoli generalizada = Z multicontrolada
    qc.h(N - 1)
    if ceros:
        qc.x(ceros)                              # deshace el cambio
    return qc


def difusor():
    """Inversion sobre el promedio: amplifica la amplitud del estado marcado."""
    qc = QuantumCircuit(N, name="Difusor")
    qc.h(range(N))
    qc.x(range(N))
    qc.h(N - 1)
    qc.mcx(list(range(N - 1)), N - 1)
    qc.h(N - 1)
    qc.x(range(N))
    qc.h(range(N))
    return qc


def circuito_grover():
    iteraciones = floor(pi / 4 * sqrt(2 ** N))   # numero optimo de repeticiones
    qc = QuantumCircuit(N, N)
    qc.h(range(N))                               # superposicion uniforme
    for _ in range(iteraciones):
        qc.compose(oraculo(OBJETIVO), inplace=True)
        qc.compose(difusor(), inplace=True)
    qc.measure(range(N), range(N))
    print(f"Elementos: {2 ** N} | Objetivo: |{OBJETIVO}> | Iteraciones: {iteraciones}\n")
    return qc


def mostrar(counts, titulo):
    print(f"--- {titulo} ---")
    total = sum(counts.values())
    for estado, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        marca = "  <-- objetivo" if estado == OBJETIVO else ""
        print(f"  |{estado}>  {n:5d}  {100 * n / total:5.1f}%  {'#' * (50 * n // total)}{marca}")
    print(f"  Exito: {100 * counts.get(OBJETIVO, 0) / total:.1f}%\n")


def correr_simulador(qc):
    from qiskit_aer import AerSimulator
    sim = AerSimulator()
    counts = sim.run(transpile(qc, sim), shots=SHOTS).result().get_counts()
    mostrar(counts, "Simulador ideal (Aer)")


def correr_con_ruido(qc):
    """Mismo circuito, pero con el modelo de ruido real de un chip IBM (sin usar cuota)."""
    from qiskit_aer import AerSimulator
    from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
    sim = AerSimulator.from_backend(FakeSherbrooke())
    counts = sim.run(transpile(qc, sim, optimization_level=3), shots=SHOTS).result().get_counts()
    mostrar(counts, "Simulador con ruido de ibm_sherbrooke")


def correr_ibm(qc):
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    service = QiskitRuntimeService()                      # usa la cuenta guardada
    backend = service.least_busy(operational=True, simulator=False)
    print(f"Backend: {backend.name} ({backend.num_qubits} qubits)\n")
    qc_hw = transpile(qc, backend, optimization_level=3)  # adapta a la topologia real
    job = SamplerV2(mode=backend).run([qc_hw], shots=SHOTS)
    print(f"Job enviado: {job.job_id()}  (esperando resultados...)")
    counts = job.result()[0].data.c.get_counts()
    mostrar(counts, f"Hardware real ({backend.name})")


if __name__ == "__main__":
    qc = circuito_grover()
    print(qc.draw(fold=120))
    print()
    if "--ibm" in sys.argv:
        correr_ibm(qc)
    elif "--ruido" in sys.argv:
        correr_con_ruido(qc)
    else:
        correr_simulador(qc)
