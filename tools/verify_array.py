#!/usr/bin/env python3
"""
Verifica el ARREGLO NORMALIZADO que el driver escribe en output_*.dat.

El verify_reference.py solo compara los estadisticos del resumen en
texto; la seccion 2.4.a del enunciado pide comparar tambien el arreglo
normalizado contra la referencia y ambas versiones entre si. Este script
cubre esa brecha.

Uso:
    python3 verify_array.py <input.dat> <output.dat> [rtol] [atol]
    python3 verify_array.py --cmp <output_scalar.dat> <output_vector.dat> [rtol] [atol]

Criterio de aceptacion (el mismo de numpy.allclose):

    |obtenido - esperado| <= atol + rtol * |esperado|

Se usa un criterio MIXTO y no puramente relativo porque los elementos
cuyo valor de entrada cae muy cerca de la media producen un z-score
practicamente nulo; ahi el error relativo se dispara aunque el error
absoluto sea despreciable. Con rtol=1e-4 puro, ~3 de cada 100000
elementos fallan por esta razon sin que exista ningun error real.

Usa NumPy: con N = 5e7 el enfoque de listas de Python necesitaria ~5 GB
de RAM (tres listas simultaneas) frente a 600 MB con arreglos.
"""
import sys

import numpy as np


def leer_dat(path):
    """Lee el formato binario del proyecto: int32 n + n float32."""
    with open(path, "rb") as f:
        n = int(np.frombuffer(f.read(4), dtype="<i4")[0])
        if n <= 0:
            return n, np.array([], dtype=np.float32)
        return n, np.frombuffer(f.read(4 * n), dtype="<f4")


def referencia_normalizada(valores):
    """Arreglo normalizado esperado, calculado en doble precision."""
    n = len(valores)
    if n == 0:
        return np.array([], dtype=np.float64), 0.0
    v = valores.astype(np.float64)
    media = float(np.mean(v))
    sigma = float(np.sqrt(np.mean((v - media) ** 2)))
    if sigma == 0.0:
        # sigma == 0: el z-score no esta definido, se copia la entrada
        return v, sigma
    return (v - media) / sigma, sigma


def comparar(esperado, obtenido, rtol, atol, etiqueta_ref, etiqueta_obt):
    if len(esperado) != len(obtenido):
        print(f"FALLA: longitudes distintas ({len(esperado)} vs {len(obtenido)})")
        return False

    if len(esperado) == 0:
        print("OK: n = 0, no hay elementos que comparar.")
        return True

    esp = np.asarray(esperado, dtype=np.float64)
    obt = np.asarray(obtenido, dtype=np.float64)

    err_abs = np.abs(obt - esp)
    with np.errstate(divide="ignore", invalid="ignore"):
        err_rel = np.where(np.abs(esp) > 0.0, err_abs / np.abs(esp), 0.0)

    idx_abs = int(np.argmax(err_abs))
    idx_rel = int(np.argmax(err_rel))
    fallos = np.nonzero(err_abs > atol + rtol * np.abs(esp))[0]

    print(f"elementos           : {len(esp)}")
    print(f"referencia          : {etiqueta_ref}")
    print(f"obtenido            : {etiqueta_obt}")
    print(f"criterio            : |dif| <= {atol:g} + {rtol:g} * |esperado|")
    print(f"peor error absoluto : {err_abs[idx_abs]:.6e}  (indice {idx_abs})")
    print(f"peor error relativo : {err_rel[idx_rel]:.6e}  (indice {idx_rel})")

    if fallos.size:
        print(f"\nelementos que incumplen el criterio: {fallos.size} de {len(esp)}")
        print(f"{'indice':>12}{'esperado':>18}{'obtenido':>18}"
              f"{'err abs':>14}{'err rel':>14}")
        for i in fallos[:5]:
            print(f"{i:>12}{esp[i]:>18.8e}{obt[i]:>18.8e}"
                  f"{err_abs[i]:>14.3e}{err_rel[i]:>14.3e}")

    ok = fallos.size == 0
    print()
    print("RESULTADO ARREGLO:", "PASA" if ok else "FALLA")
    return ok


def main():
    args = [a for a in sys.argv[1:] if a != "--cmp"]
    modo_cmp = "--cmp" in sys.argv

    if len(args) < 2:
        print(f"Uso: {sys.argv[0]} <input.dat> <output.dat> [rtol] [atol]")
        print(f"     {sys.argv[0]} --cmp <a.dat> <b.dat> [rtol] [atol]")
        sys.exit(1)

    rtol = float(args[2]) if len(args) > 2 else 1e-4
    atol = float(args[3]) if len(args) > 3 else 1e-6

    if modo_cmp:
        na, va = leer_dat(args[0])
        nb, vb = leer_dat(args[1])
        if na != nb:
            print(f"FALLA: n distinto ({na} vs {nb})")
            sys.exit(1)
        ok = comparar(va, vb, rtol, atol, args[0], args[1])
        sys.exit(0 if ok else 1)

    n_in, entrada = leer_dat(args[0])
    n_out, salida = leer_dat(args[1])
    if n_in != n_out:
        print(f"FALLA: n distinto entre entrada y salida ({n_in} vs {n_out})")
        sys.exit(1)

    esperado, sigma = referencia_normalizada(entrada)
    ruta = "COPIA (sigma == 0)" if sigma == 0.0 else "NORMALIZACION"
    print(f"sigma de referencia : {sigma:.9g}   -> ruta esperada: {ruta}")

    ok = comparar(esperado, salida, rtol, atol,
                  f"referencia NumPy de {args[0]}", args[1])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()