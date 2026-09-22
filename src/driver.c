#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <time.h>

#include "stats.h"

#define VEC_ALIGN 32 /* bytes: alineacion requerida por AVX2 (256 bits) */

static double elapsed_ms(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) * 1000.0 +
           (end.tv_nsec - start.tv_nsec) / 1e6;
}

/*
 * Lee el contador de marcas de tiempo del procesador (Time-Stamp Counter).
 *
 * Se usa ENSAMBLADOR EN LINEA y no el intrinseco __rdtsc() de
 * <x86intrin.h>, para que el proyecto no contenga ningun intrinseco de
 * compilador en ninguna parte.
 *
 * Sintaxis de GCC:  asm( instrucciones : salidas : entradas : clobbers )
 *   "=a"(lo)   -> al terminar, copiar EAX  a la variable lo
 *   "=d"(hi)   -> al terminar, copiar EDX  a la variable hi
 *   "memory"   -> avisa al compilador que la memoria pudo cambiar, para
 *                 que no reordene accesos alrededor de este bloque
 *   volatile   -> prohibe al compilador eliminar o mover el bloque
 *
 * RDTSC deja el contador de 64 bits repartido en EDX:EAX (parte alta y
 * parte baja), por eso se recombina con el desplazamiento.
 *
 * Las dos LFENCE son barreras de ejecucion: el procesador ejecuta fuera
 * de orden, y sin ellas podria adelantar el RDTSC antes de que el kernel
 * termine, dando una medicion corta.
 *
 * NOTA para el informe: en procesadores modernos el TSC avanza a una
 * frecuencia FIJA de referencia ("constant TSC"), no a la frecuencia real
 * del nucleo, que varia con turbo y ahorro de energia. El valor es un
 * conteo de ciclos DE REFERENCIA: sirve para comparar ambas versiones
 * entre si, pero no es identico a los ciclos de nucleo que reporta
 * 'perf stat -e cycles'.
 */
static inline uint64_t leer_ciclos(void) {
    uint32_t lo, hi;
    __asm__ __volatile__ (
        "lfence\n\t"
        "rdtsc\n\t"
        "lfence"
        : "=a"(lo), "=d"(hi)
        :
        : "memory");
    return ((uint64_t)hi << 32) | lo;
}

/* Media aritmetica de un arreglo de muestras. */
static double media(const double *v, int n) {
    double s = 0.0;
    for (int i = 0; i < n; i++) s += v[i];
    return s / n;
}

/*
 * Desviacion estandar MUESTRAL (divisor n-1, correccion de Bessel).
 * Se usa la muestral y no la poblacional porque las repeticiones son
 * una muestra de las ejecuciones posibles, no la poblacion completa.
 * Con una sola repeticion no esta definida y se devuelve 0.
 */
static double desv_std(const double *v, int n, double m) {
    if (n < 2) return 0.0;
    double s = 0.0;
    for (int i = 0; i < n; i++) {
        double d = v[i] - m;
        s += d * d;
    }
    return sqrt(s / (n - 1));
}

/* Reserva 'count' floats alineados a VEC_ALIGN bytes (aligned_alloc
 * exige que el tamano solicitado sea multiplo del alineamiento, por
 * eso se redondea hacia arriba). */
static float *alloc_aligned_floats(size_t count) {
    size_t bytes = count * sizeof(float);
    size_t padded = ((bytes + VEC_ALIGN - 1) / VEC_ALIGN) * VEC_ALIGN;
    if (padded == 0) padded = VEC_ALIGN;

    float *p = aligned_alloc(VEC_ALIGN, padded);
    if (!p) {
        fprintf(stderr, "Error: no se pudo reservar memoria alineada.\n");
        exit(EXIT_FAILURE);
    }
    memset(p, 0, padded);
    return p;
}

/*
 * Formato de input.dat (little endian):
 *   int32_t n
 *   float   arr[n]
 */
static float *read_input(const char *path, int *out_n) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "Error: no se pudo abrir '%s'\n", path);
        exit(EXIT_FAILURE);
    }

    int32_t n = 0;
    if (fread(&n, sizeof(int32_t), 1, f) != 1) {
        fprintf(stderr, "Error: archivo de entrada invalido (falta N)\n");
        fclose(f);
        exit(EXIT_FAILURE);
    }
    if (n < 0) {
        fprintf(stderr, "Error: N invalido (%d)\n", n);
        fclose(f);
        exit(EXIT_FAILURE);
    }

    float *arr = alloc_aligned_floats((size_t)(n > 0 ? n : 1));
    if (n > 0 && fread(arr, sizeof(float), (size_t)n, f) != (size_t)n) {
        fprintf(stderr, "Error: archivo de entrada truncado\n");
        fclose(f);
        exit(EXIT_FAILURE);
    }

    fclose(f);
    *out_n = n;
    return arr;
}

static void write_output(const char *path, const float *arr, int n) {
    FILE *f = fopen(path, "wb");
    if (!f) {
        fprintf(stderr, "Error: no se pudo crear '%s'\n", path);
        exit(EXIT_FAILURE);
    }
    fwrite(&n, sizeof(int32_t), 1, f);
    if (n > 0) fwrite(arr, sizeof(float), (size_t)n, f);
    fclose(f);
}

/* Resumen en texto plano (para que las herramientas de verificacion no
 * tengan que parsear el binario de salida). Formato clave=valor: se
 * pueden agregar claves nuevas sin romper los scripts existentes. */
static void write_stats_summary(const char *path, int n, float sum,
                                 float mean, float var, float stddev,
                                 float min, float max, int reps,
                                 double m_sum,  double d_sum,
                                 double m_stat, double d_stat,
                                 double m_norm, double d_norm,
                                 double m_tot,  double d_tot,
                                 double c_sum,  double c_stat,
                                 double c_norm, double c_tot,
                                 double cd_tot) {
    FILE *f = fopen(path, "w");
    if (!f) {
        fprintf(stderr, "Aviso: no se pudo crear el resumen '%s'\n", path);
        return;
    }
    fprintf(f, "n=%d\n", n);
    fprintf(f, "sum=%.9g\n", sum);
    fprintf(f, "mean=%.9g\n", mean);
    fprintf(f, "var=%.9g\n", var);
    fprintf(f, "stddev=%.9g\n", stddev);
    fprintf(f, "min=%.9g\n", min);
    fprintf(f, "max=%.9g\n", max);
    fprintf(f, "reps=%d\n", reps);
    /* kernel_ms conserva su nombre original por compatibilidad con
     * tools/verify_reference.py; equivale al total de las tres fases. */
    fprintf(f, "kernel_ms=%.6f\n", m_tot);
    fprintf(f, "kernel_ms_desv=%.6f\n", d_tot);
    fprintf(f, "kernel_ciclos=%.1f\n", c_tot);
    fprintf(f, "kernel_ciclos_desv=%.1f\n", cd_tot);
    fprintf(f, "ms_sum_array=%.6f\n", m_sum);
    fprintf(f, "ms_sum_array_desv=%.6f\n", d_sum);
    fprintf(f, "ms_compute_stats=%.6f\n", m_stat);
    fprintf(f, "ms_compute_stats_desv=%.6f\n", d_stat);
    fprintf(f, "ms_normalize_array=%.6f\n", m_norm);
    fprintf(f, "ms_normalize_array_desv=%.6f\n", d_norm);
    fprintf(f, "ciclos_sum_array=%.1f\n", c_sum);
    fprintf(f, "ciclos_compute_stats=%.1f\n", c_stat);
    fprintf(f, "ciclos_normalize_array=%.1f\n", c_norm);
    fclose(f);
}

static void usage(const char *prog) {
    fprintf(stderr,
        "Uso: %s <input.dat> <output.dat> [repeticiones]\n"
        "  input.dat      archivo binario de entrada (int32 N + N floats)\n"
        "  output.dat     archivo binario de salida (arreglo normalizado)\n"
        "  repeticiones   veces que se repite el kernel para promediar\n"
        "                 el tiempo medido (por defecto: 1)\n",
        prog);
}

int main(int argc, char **argv) {
    if (argc < 3) {
        usage(argv[0]);
        return EXIT_FAILURE;
    }

    const char *input_path  = argv[1];
    const char *output_path = argv[2];
    int reps = (argc >= 4) ? atoi(argv[3]) : 1;
    if (reps < 1) reps = 1;

    int n = 0;
    float *in  = read_input(input_path, &n);
    float *out = alloc_aligned_floats((size_t)(n > 0 ? n : 1));

    /* --- Caso borde N == 0: error controlado --- */
    /* Se avisa por stderr y NO se ejecuta el kernel (no hay nada que
     * calcular). Los estadisticos quedan en 0.0 y se escriben los
     * archivos de salida vacios, de modo que las herramientas de
     * verificacion siguen funcionando sin casos especiales. */
    if (n == 0) {
        fprintf(stderr,
                "Error controlado: N = 0. No hay datos que procesar.\n"
                "  Se reportan estadisticos en 0.0 y no se ejecuta el kernel\n"
                "  (se evita cualquier division por cero).\n");
    }

    float sum = 0.0f, mean = 0.0f, var = 0.0f, min = 0.0f, max = 0.0f;

    /* Muestras individuales de cada fase. Se necesitan guardadas para
     * poder calcular la desviacion estandar, que el promedio acumulado
     * por si solo no permite obtener. */
    double *ms_sum  = malloc((size_t)reps * sizeof(double));
    double *ms_stat = malloc((size_t)reps * sizeof(double));
    double *ms_norm = malloc((size_t)reps * sizeof(double));
    double *ms_tot  = malloc((size_t)reps * sizeof(double));
    double *ci_sum  = malloc((size_t)reps * sizeof(double));
    double *ci_stat = malloc((size_t)reps * sizeof(double));
    double *ci_norm = malloc((size_t)reps * sizeof(double));
    double *ci_tot  = malloc((size_t)reps * sizeof(double));
    if (!ms_sum || !ms_stat || !ms_norm || !ms_tot ||
        !ci_sum || !ci_stat || !ci_norm || !ci_tot) {
        fprintf(stderr, "Error: no se pudo reservar memoria para las muestras.\n");
        return EXIT_FAILURE;
    }

    /* --- Calentamiento (NO se mide) ---
     * La primera ejecucion paga el costo de traer el arreglo a la cache
     * desde memoria principal y de resolver los primeros fallos de TLB y
     * de prediccion de saltos. Incluirla entre las muestras infla la
     * desviacion estandar sin aportar informacion sobre el rendimiento en
     * regimen estable, que es lo que se quiere comparar entre versiones. */
    if (n > 0) {
        float m_w, v_w, mn_w, mx_w;
        sum_array(in, n);
        compute_stats(in, n, &m_w, &v_w, &mn_w, &mx_w);
        normalize_array(in, out, n, m_w, sqrtf(v_w));
    }

    /* --- Seccion medida ---
     * La seccion 2.4.b.1 pide medir "alrededor de cada llamada a la
     * funcion NASM", asi que se toman CUATRO marcas de tiempo por
     * repeticion y cada fase se obtiene por diferencia. Usar 4 marcas en
     * lugar de 3 pares independientes reduce a la mitad el sobrecosto de
     * clock_gettime y hace que el total sea exactamente la suma de las
     * partes, sin huecos ni solapes. */
    for (int r = 0; r < reps; r++) {
        struct timespec ta, tb, tc, td;
        uint64_t ca, cb, cc, cd;

        ca = leer_ciclos();  clock_gettime(CLOCK_MONOTONIC, &ta);
        if (n > 0) sum = sum_array(in, n);
        clock_gettime(CLOCK_MONOTONIC, &tb);  cb = leer_ciclos();

        if (n > 0) compute_stats(in, n, &mean, &var, &min, &max);
        clock_gettime(CLOCK_MONOTONIC, &tc);  cc = leer_ciclos();

        if (n > 0) normalize_array(in, out, n, mean, sqrtf(var));
        clock_gettime(CLOCK_MONOTONIC, &td);  cd = leer_ciclos();

        ms_sum[r]  = elapsed_ms(ta, tb);
        ms_stat[r] = elapsed_ms(tb, tc);
        ms_norm[r] = elapsed_ms(tc, td);
        ms_tot[r]  = elapsed_ms(ta, td);
        ci_sum[r]  = (double)(cb - ca);
        ci_stat[r] = (double)(cc - cb);
        ci_norm[r] = (double)(cd - cc);
        ci_tot[r]  = (double)(cd - ca);
    }

    double m_sum  = media(ms_sum,  reps), d_sum  = desv_std(ms_sum,  reps, m_sum);
    double m_stat = media(ms_stat, reps), d_stat = desv_std(ms_stat, reps, m_stat);
    double m_norm = media(ms_norm, reps), d_norm = desv_std(ms_norm, reps, m_norm);
    double m_tot  = media(ms_tot,  reps), d_tot  = desv_std(ms_tot,  reps, m_tot);

    double c_sum  = media(ci_sum,  reps), cd_sum  = desv_std(ci_sum,  reps, c_sum);
    double c_stat = media(ci_stat, reps), cd_stat = desv_std(ci_stat, reps, c_stat);
    double c_norm = media(ci_norm, reps), cd_norm = desv_std(ci_norm, reps, c_norm);
    double c_tot  = media(ci_tot,  reps), cd_tot  = desv_std(ci_tot,  reps, c_tot);

    float stddev = sqrtf(var);

    printf("N        = %d\n", n);
    printf("Suma     = %.6f\n", sum);
    printf("Media    = %.6f\n", mean);
    printf("Varianza = %.6f\n", var);
    printf("StdDev   = %.6f\n", stddev);
    printf("Minimo   = %.6f\n", min);
    printf("Maximo   = %.6f\n", max);
    printf("\n");
    printf("Repeticiones = %d  (mas 1 de calentamiento, no medida)\n", reps);
    printf("%-18s %13s %12s %15s %13s\n",
           "fase", "ms (media)", "ms (desv)", "ciclos (media)", "ciclos (desv)");
    printf("%-18s %13.6f %12.6f %15.1f %13.1f\n",
           "sum_array",       m_sum,  d_sum,  c_sum,  cd_sum);
    printf("%-18s %13.6f %12.6f %15.1f %13.1f\n",
           "compute_stats",   m_stat, d_stat, c_stat, cd_stat);
    printf("%-18s %13.6f %12.6f %15.1f %13.1f\n",
           "normalize_array", m_norm, d_norm, c_norm, cd_norm);
    printf("%-18s %13.6f %12.6f %15.1f %13.1f\n",
           "TOTAL",           m_tot,  d_tot,  c_tot,  cd_tot);
    if (n > 0) {
        printf("\nCiclos por elemento (total) = %.3f\n", c_tot / n);
    }

    write_output(output_path, out, n);

    char summary_path[1024];
    snprintf(summary_path, sizeof(summary_path), "%s.stats.txt", output_path);
    write_stats_summary(summary_path, n, sum, mean, var, stddev, min, max, reps,
                        m_sum, d_sum, m_stat, d_stat, m_norm, d_norm, m_tot, d_tot,
                        c_sum, c_stat, c_norm, c_tot, cd_tot);

    free(ms_sum); free(ms_stat); free(ms_norm); free(ms_tot);
    free(ci_sum); free(ci_stat); free(ci_norm); free(ci_tot);
    free(in);
    free(out);
    return EXIT_SUCCESS;
}