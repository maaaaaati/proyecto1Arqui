#!/usr/bin/env python3
"""
Genera archivos de entrada binarios para el proyecto de normalizacion
estadistica vectorizada.

Formato del archivo (little endian):
    int32   n
    float32 arr[n]

Uso:
    python3 gen_input.py <n> <salida.dat> [modo] [semilla]

    modo:
        random    (por defecto) valores aleatorios en [-100, 100]
        constant  todos los valores iguales a 5.0 (var = 0, caso borde)
        edge      mezcla de valores extremos, negativos y muy pequenos

Usa NumPy porque el enunciado exige el tamano N = 5e7: con listas de
Python puro ese caso necesita ~1.6 GB de RAM y decenas de segundos,
mientras que con un arreglo de NumPy son 200 MB y menos de un segundo.
La generacion de datos de prueba no forma parte del kernel evaluado.
"""
import sys

import numpy as np


def gen_random(n, rng):
    return rng.uniform(-100.0, 100.0, n).astype(np.float32)


def gen_constant(n):
    return np.full(n, 5.0, dtype=np.float32)


def gen_edge(n):
    base = np.array([-1e6, 1e6, 0.0, -0.0001, 0.0001, -1.0, 1.0],
                    dtype=np.float32)
    return base[np.arange(n) % len(base)]


def main():
    if len(sys.argv) < 3:
        print(f"Uso: {sys.argv[0]} <n> <salida.dat> [random|constant|edge] [semilla]")
        sys.exit(1)

    n = int(sys.argv[1])
    out_path = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "random"
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else None
    rng = np.random.default_rng(seed)

    if mode == "random":
        values = gen_random(n, rng)
    elif mode == "constant":
        values = gen_constant(n)
    elif mode == "edge":
        values = gen_edge(n)
    else:
        print(f"Modo desconocido: {mode}")
        sys.exit(1)

    with open(out_path, "wb") as f:
        # '<i4' fuerza little endian explicitamente, independientemente
        # de la arquitectura donde corra el script
        f.write(np.array([n], dtype="<i4").tobytes())
        if n > 0:
            f.write(values.astype("<f4").tobytes())

    print(f"Generado '{out_path}' con N={n}, modo={mode}")


if __name__ == "__main__":
    main()