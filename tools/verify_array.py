#!/usr/bin/env python3
"""
Verifica el ARREGLO NORMALIZADO que el driver escribe en output_*.dat.

El script verify_reference.py del esqueleto solo compara los estadisticos
del resumen .stats.txt; la seccion 2.4.a del enunciado pide comparar
tambien el arreglo normalizado contra la referencia y ambas versiones
entre si. Este script cubre esa brecha.

Uso:
    # contra la referencia calculada en Python
    python3 verify_array.py <input.dat> <output.dat> [rtol] [atol]

    # escalar contra vectorial
    python3 verify_array.py --cmp <output_scalar.dat> <output_vector.dat>

Criterio de aceptacion (el mismo de numpy.allclose):

    |obtenido - esperado| <= atol + rtol * |esperado|

Se usa un criterio MIXTO y no puramente relativo porque los elementos
cuyo valor de entrada cae muy cerca de la media producen un z-score
practicamente nulo; ahi el error relativo se dispara aunque el error
absoluto sea despreciable. Con rtol=1e-4 puro, ~3 de cada 100000
elementos fallan por esta razon sin que haya ningun error real.
"""
import math
import struct
import sys


def leer_dat(path):
    """Lee el formato binario del proyecto: int32 n + n float32."""
    with open(path, "rb") as f:
        n = struct.unpack("<i", f.read(4))[0]
        if n <= 0:
            return n, []
        return n, list(struct.unpack(f"<{n}f", f.read(4 * n)))


def referencia_normalizada(valores):
    """Calcula el arreglo normalizado esperado en doble precision."""
    n = len(valores)
    if n == 0:
        return [], 0.0
    media = sum(valores) / n
    var = sum((x - media) ** 2 for x in valores) / n
    sigma = math.sqrt(var)
    if sigma == 0.0:
        # sigma == 0: el z-score no esta definido, se copia la entrada
        return list(valores), sigma
    return [(x - media) / sigma for x in valores], sigma


def comparar(esperado, obtenido, rtol, atol, etiqueta_ref, etiqueta_obt):
    """Compara dos arreglos y reporta el peor caso."""
    if len(esperado) != len(obtenido):
        print(f"FALLA: longitudes distintas ({len(esperado)} vs {len(obtenido)})")
        return False

    if not esperado:
        print("OK: n = 0, no hay elementos que comparar.")
        return True

    peor_abs = peor_rel = 0.0
    idx_abs = idx_rel = 0
    fallos = []

    for i, (esp, obt) in enumerate(zip(esperado, obtenido)):
        e_abs = abs(obt - esp)
        e_rel = e_abs / abs(esp) if abs(esp) > 0.0 else 0.0

        if e_abs > peor_abs:
            peor_abs, idx_abs = e_abs, i
        if e_rel > peor_rel:
            peor_rel, idx_rel = e_rel, i

        if e_abs > atol + rtol * abs(esp):
            if len(fallos) < 5:
                fallos.append((i, esp, obt, e_abs, e_rel))

    print(f"elementos           : {len(esperado)}")
    print(f"referencia          : {etiqueta_ref}")
    print(f"obtenido            : {etiqueta_obt}")
    print(f"criterio            : |dif| <= {atol:g} + {rtol:g} * |esperado|")
    print(f"peor error absoluto : {peor_abs:.6e}  (indice {idx_abs})")
    print(f"peor error relativo : {peor_rel:.6e}  (indice {idx_rel})")

    if fallos:
        print(f"\nelementos que incumplen el criterio (primeros {len(fallos)}):")
        print(f"{'indice':>10}{'esperado':>18}{'obtenido':>18}"
              f"{'err abs':>14}{'err rel':>14}")
        for i, esp, obt, ea, er in fallos:
            print(f"{i:>10}{esp:>18.8e}{obt:>18.8e}{ea:>14.3e}{er:>14.3e}")

    ok = not fallos
    print()
    print("RESULTADO ARREGLO:", "PASA" if ok else "FALLA")
    return ok


def main():
    args = sys.argv[1:]

    if args and args[0] == "--cmp":
        # Modo comparacion directa escalar vs vectorial
        if len(args) < 3:
            print(f"Uso: {sys.argv[0]} --cmp <a.dat> <b.dat> [rtol] [atol]")
            sys.exit(1)
        rtol = float(args[3]) if len(args) > 3 else 1e-4
        atol = float(args[4]) if len(args) > 4 else 1e-6
        na, va = leer_dat(args[1])
        nb, vb = leer_dat(args[2])
        if na != nb:
            print(f"FALLA: n distinto ({na} vs {nb})")
            sys.exit(1)
        ok = comparar(va, vb, rtol, atol, args[1], args[2])
        sys.exit(0 if ok else 1)

    if len(args) < 2:
        print(f"Uso: {sys.argv[0]} <input.dat> <output.dat> [rtol] [atol]")
        print(f"     {sys.argv[0]} --cmp <a.dat> <b.dat> [rtol] [atol]")
        sys.exit(1)

    rtol = float(args[2]) if len(args) > 2 else 1e-4
    atol = float(args[3]) if len(args) > 3 else 1e-6

    n_in, entrada = leer_dat(args[0])
    n_out, salida = leer_dat(args[1])

    if n_in != n_out:
        print(f"FALLA: n distinto entre entrada y salida ({n_in} vs {n_out})")
        sys.exit(1)

    esperado, sigma = referencia_normalizada(entrada)
    ruta = "COPIA (sigma == 0)" if sigma == 0.0 else "NORMALIZACION"
    print(f"sigma de referencia : {sigma:.9g}   -> ruta esperada: {ruta}")

    ok = comparar(esperado, salida, rtol, atol,
                  f"referencia Python de {args[0]}", args[1])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()