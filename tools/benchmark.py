#!/usr/bin/env python3
"""
Banco de pruebas de rendimiento: cubre los puntos 2.4.b.2, 2.4.b.3 y
2.4.b.4 del enunciado.

  - Corre los 4 tamanos grandes exigidos: 10^3, 10^5, 10^6, 5x10^7
  - Al menos 30 repeticiones por tamano (el driver promedia y calcula
    la desviacion estandar)
  - Calcula Speedup = tiempo_escalar / tiempo_vectorial por tamano
  - Grafica N (eje X, escala logaritmica) vs Speedup (eje Y)
  - Escribe los resultados crudos en CSV para el informe

Uso:
    python3 tools/benchmark.py                 # los 4 tamanos, 30 rep.
    python3 tools/benchmark.py --rapido        # omite N = 5x10^7
    python3 tools/benchmark.py --reps 50
    python3 tools/benchmark.py --mantener      # no borra los .dat grandes

Salidas:
    data/benchmark.csv        resultados crudos (una fila por tamano/version)
    data/speedup.png          grafico de speedup vs N
    (y la tabla por consola)

ADVERTENCIA DE ESPACIO: N = 5x10^7 genera un input.dat de ~191 MB y dos
archivos de salida del mismo tamano. Necesita ~600 MB libres en disco y
~500 MB de RAM. Con --rapido se omite ese caso.
"""
import argparse
import csv
import os
import subprocess
import sys

TAMANOS = [1000, 100000, 1000000, 50000000]
DATA = "data"
TOOLS = "tools"


def leer_resumen(path):
    """Lee el archivo <output>.stats.txt en formato clave=valor."""
    d = {}
    with open(path) as f:
        for linea in f:
            linea = linea.strip()
            if "=" in linea:
                k, v = linea.split("=", 1)
                try:
                    d[k] = float(v)
                except ValueError:
                    pass
    return d


def correr(binario, entrada, salida, reps):
    r = subprocess.run([f"./bin/norm_{binario}", entrada, salida, str(reps)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERROR al ejecutar norm_{binario}:\n{r.stderr}")
        return None
    return leer_resumen(f"{salida}.stats.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--rapido", action="store_true",
                    help="omite N = 5x10^7")
    ap.add_argument("--mantener", action="store_true",
                    help="no borra los .dat grandes al terminar")
    ap.add_argument("--semilla", type=int, default=7)
    args = ap.parse_args()

    if args.reps < 30:
        print(f"Aviso: el enunciado pide al menos 30 repeticiones "
              f"(se pidieron {args.reps}).")

    tamanos = TAMANOS[:-1] if args.rapido else TAMANOS
    os.makedirs(DATA, exist_ok=True)

    for b in ("scalar", "vector"):
        if not os.path.exists(f"./bin/norm_{b}"):
            print(f"No existe ./bin/norm_{b}. Corra 'make' primero.")
            sys.exit(1)

    filas = []
    temporales = []

    for n in tamanos:
        entrada = f"{DATA}/bench_{n}.dat"
        print(f"\n===== N = {n:,} ({args.reps} repeticiones) =====")

        print("  generando entrada...", end="", flush=True)
        subprocess.run(["python3", f"{TOOLS}/gen_input.py", str(n), entrada,
                        "random", str(args.semilla)], capture_output=True)
        print(" listo")
        temporales.append(entrada)

        res = {}
        for b in ("scalar", "vector"):
            salida = f"{DATA}/bench_{n}_{b}.dat"
            temporales += [salida, f"{salida}.stats.txt"]
            print(f"  corriendo norm_{b}...", end="", flush=True)
            d = correr(b, entrada, salida, args.reps)
            if d is None:
                sys.exit(1)
            res[b] = d
            print(f" {d['kernel_ms']:.4f} ms")

        s, v = res["scalar"], res["vector"]
        speedup = s["kernel_ms"] / v["kernel_ms"] if v["kernel_ms"] > 0 else 0.0

        # Speedup por fase: revela cual funcion limita el total
        sp_fase = {}
        for fase in ("sum_array", "compute_stats", "normalize_array"):
            ks, kv = s.get(f"ms_{fase}", 0.0), v.get(f"ms_{fase}", 0.0)
            sp_fase[fase] = ks / kv if kv > 0 else 0.0

        filas.append({
            "n": n,
            "reps": args.reps,
            "escalar_ms": s["kernel_ms"],
            "escalar_ms_desv": s.get("kernel_ms_desv", 0.0),
            "escalar_ciclos": s.get("kernel_ciclos", 0.0),
            "vector_ms": v["kernel_ms"],
            "vector_ms_desv": v.get("kernel_ms_desv", 0.0),
            "vector_ciclos": v.get("kernel_ciclos", 0.0),
            "speedup": speedup,
            "speedup_sum_array": sp_fase["sum_array"],
            "speedup_compute_stats": sp_fase["compute_stats"],
            "speedup_normalize_array": sp_fase["normalize_array"],
            "ciclos_elem_escalar": s.get("kernel_ciclos", 0.0) / n,
            "ciclos_elem_vector": v.get("kernel_ciclos", 0.0) / n,
        })
        print(f"  SPEEDUP = {speedup:.2f}x")

    # ---------- tabla por consola ----------
    print("\n" + "=" * 78)
    print(f"{'N':>12} {'escalar (ms)':>18} {'vectorial (ms)':>18} {'speedup':>10}")
    print("-" * 78)
    for f in filas:
        print(f"{f['n']:>12,} "
              f"{f['escalar_ms']:>10.4f} +/- {f['escalar_ms_desv']:<5.4f} "
              f"{f['vector_ms']:>10.4f} +/- {f['vector_ms_desv']:<5.4f} "
              f"{f['speedup']:>9.2f}x")

    print("\nSpeedup por fase:")
    print(f"{'N':>12} {'sum_array':>12} {'compute_stats':>15} {'normalize_array':>17}")
    print("-" * 78)
    for f in filas:
        print(f"{f['n']:>12,} {f['speedup_sum_array']:>11.2f}x "
              f"{f['speedup_compute_stats']:>14.2f}x "
              f"{f['speedup_normalize_array']:>16.2f}x")

    print("\nCiclos por elemento (crece cuando el arreglo sale de cache):")
    print(f"{'N':>12} {'escalar':>12} {'vectorial':>12}")
    print("-" * 78)
    for f in filas:
        print(f"{f['n']:>12,} {f['ciclos_elem_escalar']:>12.3f} "
              f"{f['ciclos_elem_vector']:>12.3f}")

    # ---------- CSV ----------
    csv_path = f"{DATA}/benchmark.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"\nCSV escrito en {csv_path}")

    # ---------- grafico ----------
    try:
        import matplotlib
        matplotlib.use("Agg")   # backend sin ventana: no necesita entorno grafico
        import matplotlib.pyplot as plt

        ns = [f["n"] for f in filas]
        sp = [f["speedup"] for f in filas]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.semilogx(ns, sp, "o-", linewidth=2, markersize=8, label="Speedup medido")
        ax.axhline(8.0, color="red", linestyle="--", linewidth=1.2,
                   label="Limite teorico AVX2 (8x)")
        for f in filas:
            ax.annotate(f"{f['speedup']:.2f}x", (f["n"], f["speedup"]),
                        textcoords="offset points", xytext=(0, 10), ha="center")
        ax.set_xlabel("N (escala logaritmica)")
        ax.set_ylabel("Speedup = tiempo_escalar / tiempo_vectorial")
        ax.set_title("Speedup de la version AVX2 frente a la escalar")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend()
        ax.set_ylim(bottom=0)
        fig.tight_layout()
        png = f"{DATA}/speedup.png"
        fig.savefig(png, dpi=150)
        print(f"Grafico escrito en {png}")
    except ImportError:
        print("\nmatplotlib no esta instalado; no se genero el grafico.")
        print("  sudo apt install -y python3-matplotlib")
        print(f"  (los datos quedaron en {csv_path} para graficarlos aparte)")

    # ---------- limpieza ----------
    if not args.mantener:
        borrados = 0
        for p in temporales:
            if os.path.exists(p) and os.path.getsize(p) > 10_000_000:
                os.remove(p)
                borrados += 1
        if borrados:
            print(f"\nSe borraron {borrados} archivos .dat grandes "
                  f"(use --mantener para conservarlos).")


if __name__ == "__main__":
    main()