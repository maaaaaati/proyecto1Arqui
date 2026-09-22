# Esqueleto de proyecto: Normalizador estadistico vectorizado (NASM + C)

Este es el punto de partida para el proyecto "Programacion Vectorial en
Ensamblador x86-64 (NASM/Linux)". **Aqui no esta la solucion**: contiene
la estructura, las firmas de las funciones y **un** ejemplo completo por
version (`sum_array`) que sirve de patron. El resto de las funciones
(`compute_stats`, `normalize_array`) estan marcadas con `TODO` y deben
ser implementadas por el estudiante, tanto en la version escalar como
en la vectorial.

## Estructura

```
.
├── Makefile
├── include/
│   └── stats.h                # Firmas compartidas por ambas versiones
├── src/
│   └── driver.c                # Programa principal (E/S, timing, impresion)
├── asm/
│   ├── scalar/
│   │   └── stats_scalar.asm    # Version escalar (SSE escalar)
│   └── vector/
│       └── stats_vector.asm    # Version vectorial (AVX2)
├── tools/
│   ├── gen_input.py            # Genera archivos de entrada de prueba
│   └── verify_reference.py     # Verifica resultados contra referencia en Python puro
└── data/                        # Se crea al compilar: entradas/salidas .dat
```

## Requisitos

- Linux con CPU compatible con AVX2 (verificar con `lscpu | grep avx2`).
- `nasm`, `gcc`, `make`, `python3`.
- `gdb` y, opcionalmente, `perf` (paquete `linux-tools`) para las partes
  de verificacion y medicion de rendimiento del proyecto.

## Compilar

```bash
make
```

Genera `bin/norm_scalar` y `bin/norm_vector`: dos ejecutables que
comparten el mismo `driver.c` pero enlazan con kernels distintos
(`obj/stats_scalar.o` u `obj/stats_vector.o`).

## Generar datos de prueba

```bash
python3 tools/gen_input.py 1000000 data/input.dat random
python3 tools/gen_input.py 8       data/input_small.dat random
python3 tools/gen_input.py 1000    data/input_constant.dat constant
python3 tools/gen_input.py 0       data/input_empty.dat random
```

Genere tambien casos con `N` no multiplo de 8 (por ejemplo 7, 15, 1001)
para probar el manejo del remanente.

## Ejecutar

```bash
./bin/norm_scalar data/input.dat data/output_scalar.dat 30
./bin/norm_vector data/input.dat data/output_vector.dat 30
```

El tercer argumento es el numero de repeticiones del kernel, usado para
promediar el tiempo medido con `clock_gettime` (util para sus mediciones
de rendimiento con distintos tamanos de `N`).

Cada corrida tambien escribe `data/output_scalar.dat.stats.txt` (o
`_vector.dat.stats.txt`) con un resumen en texto plano de los
estadisticos y el tiempo del kernel.

## Verificar correctud

```bash
python3 tools/verify_reference.py data/input.dat data/output_scalar.dat.stats.txt
python3 tools/verify_reference.py data/input.dat data/output_vector.dat.stats.txt
```

## Lo que debe implementar el estudiante

1. **`asm/scalar/stats_scalar.asm`**: completar `compute_stats` y
   `normalize_array` con instrucciones escalares (`movss`, `addss`,
   `subss`, `mulss`, `divss`, `sqrtss`, `comiss`, etc.).
2. **`asm/vector/stats_vector.asm`**: completar `compute_stats` y
   `normalize_array` con AVX2 (`vmovaps`/`vmovups`, `vaddps`, `vsubps`,
   `vmulps`, `vdivps`, `vminps`, `vmaxps`, `vbroadcastss`, reduccion
   horizontal), **manejando el remanente** igual que en el `sum_array`
   de ejemplo.
3. Generar sus propios archivos de prueba con `gen_input.py` para los
   casos borde exigidos en la propuesta (N=0, N=1, N no multiplo de 8,
   valores constantes, valores negativos/extremos).
4. Usar GDB para inspeccionar registros YMM y memoria en un caso
   pequeno, como se pide en la propuesta (ver ejemplo mas abajo).
5. Medir tiempos con distintos tamanos de `N` (use el argumento de
   repeticiones del driver) y, opcionalmente, `perf stat`.

## Notas de depuracion con GDB

Los binarios se compilan con simbolos de depuracion (`-g` en gcc y
`-g -F dwarf` en nasm), por lo que se puede poner breakpoints
directamente en las etiquetas del ensamblador:

```bash
gdb --args ./bin/norm_vector data/input_small.dat data/out.dat 1
(gdb) break normalize_array
(gdb) run
(gdb) info registers ymm0
(gdb) stepi
(gdb) x/8fw &out[0]
```

(La sintaxis exacta para imprimir un YMM completo como 8 floats
depende de la version de GDB instalada: pruebe `info registers ymm0`,
`print $ymm0.v8_float`, o `p/x $ymm0` segun lo que este disponible en
su laboratorio.)


## Para correr el programa

mkdir -p build
nasm -f elf64 -g -F dwarf asm/scalar/stats_scalar.asm -o build/stats_scalar.o
nasm -f elf64 -g -F dwarf asm/vector/stats_vector.asm -o build/stats_vector.o
gcc -O2 -g -Iinclude src/driver.c build/stats_scalar.o -o build/prog_scalar -lm
gcc -O2 -g -Iinclude src/driver.c build/stats_vector.o -o build/prog_vector -lm

python3 tools/gen_input.py 1000 input.dat random 42
./build/prog_scalar input.dat output_scalar.dat 30
./build/prog_vector input.dat output_vector.dat 30
python3 tools/verify_reference.py input.dat output_scalar.dat.stats.txt
python3 tools/verify_reference.py input.dat output_vector.dat.stats.txt

---

# Driver y herramientas de verificación

## Requisitos extra

```bash
sudo apt install -y python3-numpy python3-matplotlib linux-tools-generic
```

NumPy es **obligatorio**: con Python puro, el caso N = 5×10⁷ que exige el
enunciado necesita ~1.6 GB de RAM por lista. matplotlib solo hace falta
para el gráfico. `linux-tools-generic` trae `perf`.

## Qué cambió en `src/driver.c`

| Cambio | Motivo |
|---|---|
| Mide cada función por separado (4 marcas de tiempo por repetición) | Sección 2.4.b.1 pide medir "alrededor de cada llamada NASM" |
| Reporta ciclos de reloj (RDTSC en ensamblador en línea, **sin intrínsecos**) | Sección 2.2 |
| Reporta desviación estándar de las repeticiones | Sección 2.4.b.2 |
| Ejecuta una iteración de calentamiento que **no** mide | Sin ella la desviación salía del doble de la media |
| `N = 0` avisa por `stderr` y no ejecuta el kernel | Sección 2.3 (error controlado) |

Salida nueva:

```
Repeticiones = 30  (mas 1 de calentamiento, no medida)
fase                  ms (media)    ms (desv)  ciclos (media) ciclos (desv)
sum_array               1.627629     0.012000       4117976.0       30000.0
compute_stats           5.232078     0.041000      13059138.0      102000.0
normalize_array         1.609615     0.019000       4017580.0       47000.0
TOTAL                   8.469322     0.058000      21194694.0      145000.0
```

El archivo `<output>.dat.stats.txt` mantiene el formato `clave=valor` y
agrega: `reps`, `kernel_ms_desv`, `kernel_ciclos`, `kernel_ciclos_desv`,
`ms_<fase>`, `ms_<fase>_desv` y `ciclos_<fase>`.

## Herramientas

Todas devuelven código de salida 0 si pasan y 1 si fallan.

### `gen_input.py` — generar datos

```bash
python3 tools/gen_input.py <n> <salida.dat> [random|constant|edge] [semilla]
```

`random` = uniformes en [−100, 100] · `constant` = todos 5.0 (σ = 0) ·
`edge` = ±10⁶, ±0.0001, ±1.0, 0.0. Con la misma semilla se obtiene el
mismo archivo, así que las corridas son reproducibles entre máquinas.

### `verify_reference.py` — verificar estadísticos

```bash
python3 tools/verify_reference.py <input.dat> <output.dat.stats.txt> [tol]
```

Compara contra una referencia calculada con NumPy en float64. Tolerancia
relativa por defecto 1×10⁻⁴.

### `verify_array.py` — verificar el arreglo normalizado

Cubre lo que `verify_reference.py` no revisa: el contenido de
`output_*.dat` (sección 2.4.a).

```bash
python3 tools/verify_array.py <input.dat> <output.dat>              # vs referencia
python3 tools/verify_array.py --cmp <out_scalar.dat> <out_vector.dat>
```

Criterio mixto, igual que `numpy.allclose`:
`|dif| <= atol + rtol·|esperado|` con `rtol=1e-4`, `atol=1e-6`. El
criterio puramente relativo da falsos negativos en elementos cuyo z-score
es casi nulo.

### `run_tests.py` — los 11 casos borde

```bash
python3 tools/run_tests.py            # ambos binarios + comparación entre sí
python3 tools/run_tests.py scalar     # solo uno
python3 tools/run_tests.py -v         # detalle de los fallos
```

Casos: N = 0, 1, 7, 8, 15, 16, 1000 y 100000 en `random`; 1000 en
`constant`; 16 y 1000 en `edge`. Esperado: `RESULTADO GLOBAL: TODO PASA`.

### `benchmark.py` — rendimiento (secciones 2.4.b.2, .3 y .4)

```bash
python3 tools/benchmark.py            # 4 tamaños, 30 repeticiones
python3 tools/benchmark.py --rapido   # omite N = 5×10⁷
python3 tools/benchmark.py --reps 50
```

Genera `data/benchmark.csv` y `data/speedup.png` (eje X logarítmico, con
la línea del límite teórico 8×), más tres tablas por consola: speedup
total, speedup por fase y ciclos por elemento.

**Necesita ~600 MB libres** en disco para N = 5×10⁷ (`df -h .`).
Antes de correrlo, cerrar navegador y editor: **si la desviación estándar
pasa del 5 % de la media, la medición hay que repetirla.**

## Secuencia recomendada

```bash
make clean && make                     # debe salir sin advertencias
python3 tools/run_tests.py             # correctud
python3 tools/benchmark.py             # rendimiento + gráfico

# contadores de hardware (sección 2.4.b.5)
sudo sysctl -w kernel.perf_event_paranoid=1
python3 tools/gen_input.py 1000000 data/perf.dat random 7
perf stat -e cycles,instructions,cache-misses,cache-references \
    ./bin/norm_scalar data/perf.dat data/ps.dat 30
perf stat -e cycles,instructions,cache-misses,cache-references \
    ./bin/norm_vector data/perf.dat data/pv.dat 30
```

## Estado y tareas pendientes en los kernels

Los 11 casos borde pasan en ambas versiones y entre sí. Las dos tareas prioritarias:

**1. Acumuladores parciales en el `.var_loop` escalar.** Con N = 10⁶ el
escalar da 3.55×10⁻⁴ de error relativo en `var` (falla la tolerancia de
la sección 2.3) y el vectorial 1.93×10⁻⁵. La diferencia de `stddev` entre
ambos es 1.68×10⁻⁴ y se propaga **idéntica** a cada z-score, así que los
991 546 de 1 000 000 elementos que fallan son **un solo error**. Causa:
el escalar usa un único acumulador que llega a ~3.3×10⁹, magnitud donde
el espaciado entre `float32` consecutivos es ~400 mientras cada término
vale ~3300. El vectorial no sufre porque sus 8 carriles son 8
acumuladores independientes.

**2. Recíproco en lugar de `vdivps` en `normalize_array`.** Es el cuello
de botella: su speedup cae de 6.91× a 2.02× y arrastra el total.
`vdivps` tiene throughput recíproco de ~5 ciclos frente a 0.5 de
`vmulps`, y además es la única fase que escribe (doble tráfico de
memoria). El enunciado contempla explícitamente esta optimización.

Mediciones completas en `data/benchmark.csv`.