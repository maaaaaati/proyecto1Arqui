#!/usr/bin/env python3
"""
Calcula estadisticos de referencia con NumPy para un archivo input.dat y
los compara contra el resumen que el driver en C escribe en
'<output>.stats.txt'.

Uso:
    python3 verify_reference.py <input.dat> <output.stats.txt> [tolerancia]

La referencia se calcula en float64 (doble precision), no en float32,
para que sirva como patron independiente contra el cual medir el error
de acumulacion de las dos implementaciones en ensamblador. NumPy usa
ademas suma por pares (pairwise summation), cuyo error crece como
O(log n) en lugar de O(n), asi que la referencia sigue siendo confiable
en los tamanos grandes que exige el enunciado.
"""
import sys

import numpy as np


def read_input(path):
    with open(path, "rb") as f:
        n = int(np.frombuffer(f.read(4), dtype="<i4")[0])
        if n <= 0:
            return n, np.array([], dtype=np.float64)
        v = np.frombuffer(f.read(4 * n), dtype="<f4")
    return n, v.astype(np.float64)


def read_summary(path):
    result = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            try:
                result[key] = float(val)
            except ValueError:
                pass
    return result


def reference_stats(values):
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    total = float(np.sum(values))
    mean = total / n
    var = float(np.mean((values - mean) ** 2))   # varianza POBLACIONAL
    stddev = float(np.sqrt(var))
    return total, mean, var, stddev, float(np.min(values)), float(np.max(values))


def rel_error(a, b):
    if abs(b) < 1e-12:
        return abs(a - b)
    return abs(a - b) / abs(b)


def main():
    if len(sys.argv) < 3:
        print(f"Uso: {sys.argv[0]} <input.dat> <output.stats.txt> [tolerancia]")
        sys.exit(1)

    input_path = sys.argv[1]
    summary_path = sys.argv[2]
    tol = float(sys.argv[3]) if len(sys.argv) > 3 else 1e-4

    n, values = read_input(input_path)
    ref_sum, ref_mean, ref_var, ref_std, ref_min, ref_max = reference_stats(values)
    got = read_summary(summary_path)

    checks = [
        ("n", float(n), got.get("n", float("nan"))),
        ("sum", ref_sum, got.get("sum", float("nan"))),
        ("mean", ref_mean, got.get("mean", float("nan"))),
        ("var", ref_var, got.get("var", float("nan"))),
        ("stddev", ref_std, got.get("stddev", float("nan"))),
        ("min", ref_min, got.get("min", float("nan"))),
        ("max", ref_max, got.get("max", float("nan"))),
    ]

    all_ok = True
    print(f"{'campo':<10}{'referencia':>15}{'obtenido':>15}{'error rel.':>15}  resultado")
    for name, ref, val in checks:
        err = abs(val - ref) if name == "n" else rel_error(val, ref)
        ok = (err == 0) if name == "n" else (err <= tol)
        all_ok = all_ok and ok
        status = "OK" if ok else "FALLA"
        print(f"{name:<10}{ref:>15.6f}{val:>15.6f}{err:>15.6g}  {status}")

    print()
    print("RESULTADO GENERAL:", "PASA" if all_ok else "FALLA")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()