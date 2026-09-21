#!/usr/bin/env python3
"""
Arnes de pruebas del proyecto: corre la bateria de casos borde contra
uno o ambos binarios y produce la tabla de resultados que pide la
seccion 3.b.5 del enunciado.

A diferencia de un bucle de shell con grep, aqui el veredicto se toma
del CODIGO DE SALIDA de cada verificador, no de buscar palabras en su
salida de texto. Eso elimina los falsos positivos/negativos por
coincidencias parciales.

Uso:
    python3 tools/run_tests.py                      # ambos binarios
    python3 tools/run_tests.py scalar               # solo escalar
    python3 tools/run_tests.py vector               # solo vectorial
    python3 tools/run_tests.py --cmp                # escalar vs vectorial
    python3 tools/run_tests.py -v                   # muestra el detalle de los fallos
"""
import os
import subprocess
import sys

# (N, modo) de los casos exigidos en la seccion 2.3 del enunciado
CASOS = [
    (0,      "random"),    # error controlado, sin division por cero
    (1,      "random"),    # var = 0
    (7,      "random"),    # N < 8: solo bucle remanente
    (8,      "random"),    # N == 8: exactamente un vector
    (15,     "random"),    # N no multiplo de 8
    (16,     "random"),    # N multiplo de 8, dos vectores
    (1000,   "random"),    # caso general
    (1000,   "constant"),  # sigma = 0, ruta de copia
    (16,     "edge"),      # valores extremos y negativos
    (1000,   "edge"),
    (100000, "random"),    # tamano medio
]

SEMILLA = 7
DATA = "data"
TOOLS = "tools"


def sh(cmd):
    """Ejecuta un comando y devuelve (codigo_salida, stdout+stderr)."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def probar(binario, n, modo, verbose):
    """Corre un caso y devuelve (ok_stats, ok_arreglo, detalle)."""
    entrada = f"{DATA}/test_{n}_{modo}.dat"
    salida = f"{DATA}/out_{binario}_{n}_{modo}.dat"

    rc, out = sh(["python3", f"{TOOLS}/gen_input.py",
                  str(n), entrada, modo, str(SEMILLA)])
    if rc != 0:
        return False, False, f"gen_input fallo: {out}"

    rc, out = sh([f"./bin/norm_{binario}", entrada, salida, "1"])
    if rc != 0:
        return False, False, f"el binario fallo: {out}"

    # El veredicto es el CODIGO DE SALIDA, no una busqueda de texto
    rc_stats, det_stats = sh(["python3", f"{TOOLS}/verify_reference.py",
                              entrada, f"{salida}.stats.txt"])
    rc_arr, det_arr = sh(["python3", f"{TOOLS}/verify_array.py",
                          entrada, salida])

    detalle = ""
    if verbose and (rc_stats != 0 or rc_arr != 0):
        if rc_stats != 0:
            detalle += "\n  --- estadisticos ---\n" + det_stats
        if rc_arr != 0:
            detalle += "\n  --- arreglo ---\n" + det_arr

    return rc_stats == 0, rc_arr == 0, detalle


def comparar_versiones(verbose):
    """Compara output_scalar.dat contra output_vector.dat en cada caso."""
    print(f"\n{'N':>8}  {'modo':<10}  {'escalar vs vectorial':<22}")
    print("-" * 46)
    todo_ok = True
    for n, modo in CASOS:
        a = f"{DATA}/out_scalar_{n}_{modo}.dat"
        b = f"{DATA}/out_vector_{n}_{modo}.dat"
        if not (os.path.exists(a) and os.path.exists(b)):
            print(f"{n:>8}  {modo:<10}  (falta una de las dos salidas)")
            todo_ok = False
            continue
        rc, det = sh(["python3", f"{TOOLS}/verify_array.py", "--cmp", a, b])
        print(f"{n:>8}  {modo:<10}  {'PASA' if rc == 0 else 'FALLA':<22}")
        if rc != 0:
            todo_ok = False
            if verbose:
                print(det)
    return todo_ok


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    solo_cmp = "--cmp" in sys.argv

    binarios = args if args else ["scalar", "vector"]
    binarios = [b for b in binarios
                if os.path.exists(f"./bin/norm_{b}")]
    if not binarios:
        print("No se encontro ningun binario en bin/. Corra 'make' primero.")
        sys.exit(1)

    os.makedirs(DATA, exist_ok=True)
    todo_ok = True

    for binario in binarios:
        print(f"\n===== bin/norm_{binario} =====")
        print(f"{'N':>8}  {'modo':<10}  {'estadisticos':<14}  {'arreglo':<10}")
        print("-" * 48)
        for n, modo in CASOS:
            ok_s, ok_a, detalle = probar(binario, n, modo, verbose)
            todo_ok = todo_ok and ok_s and ok_a
            print(f"{n:>8}  {modo:<10}  "
                  f"{'PASA' if ok_s else 'FALLA':<14}  "
                  f"{'PASA' if ok_a else 'FALLA':<10}")
            if detalle:
                print(detalle)

    if solo_cmp or len(binarios) == 2:
        todo_ok = comparar_versiones(verbose) and todo_ok

    print()
    print("=" * 48)
    print("RESULTADO GLOBAL:", "TODO PASA" if todo_ok else "HAY FALLOS")
    print("=" * 48)
    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()