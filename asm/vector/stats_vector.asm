; =============================================================
; stats_vector.asm
; Version VECTORIZADA (AVX2, 8 floats por iteracion) de los
; kernels de computo. Misma ABI que la version escalar.
;
; Antes de compilar/ejecutar en su maquina, confirme soporte AVX2:
;   lscpu | grep avx2
;   cat /proc/cpuinfo | grep avx2
; =============================================================

    global sum_array
    global compute_stats
    global normalize_array

    section .text

; ---------------------------------------------------------------
; float sum_array(const float *arr, int n)
;   rdi = arr, esi = n -> retorna la suma en xmm0
;
; IMPLEMENTADA COMO EJEMPLO. Fijense especialmente en:
;   (1) como se calcula cuantos elementos entran en bucles de 8
;       ("and ecx, ~7" redondea n hacia abajo al multiplo de 8),
;   (2) la REDUCCION HORIZONTAL para pasar de 8 sumas parciales
;       (un YMM) a un unico escalar,
;   (3) el BUCLE ESCALAR DE CIERRE para el remanente (n % 8 != 0).
; Reutilicen este mismo patron en compute_stats y normalize_array.
; ---------------------------------------------------------------
sum_array:
    xor     eax, eax               ; eax = i = 0
    vxorps  ymm0, ymm0, ymm0       ; ymm0 = acumulador vectorial (8 carriles) = 0

    mov     ecx, esi
    and     ecx, ~7                ; ecx = n redondeado hacia abajo, multiplo de 8
    test    ecx, ecx
    jle     .sum_reduce

.sum_vec_loop:
    cmp     eax, ecx
    jge     .sum_reduce
    vmovups ymm1, [rdi + rax*4]    ; carga 8 floats (unaligned: siempre valido)
    vaddps  ymm0, ymm0, ymm1       ; acumula por carril
    add     eax, 8
    jmp     .sum_vec_loop

.sum_reduce:
    ; --- reduccion horizontal: 8 carriles de ymm0 -> un escalar ---
    vextractf128 xmm2, ymm0, 1     ; xmm2 = mitad alta (carriles 4-7)
    vaddps  xmm0, xmm0, xmm2       ; xmm0 = 4 sumas parciales (carriles 0-3 + 4-7)
    vhaddps xmm0, xmm0, xmm0       ; suma horizontal dentro de 128 bits
    vhaddps xmm0, xmm0, xmm0       ; xmm0[0] = suma total de los 8 carriles originales

.sum_scalar_tail:
    ; --- elementos sobrantes (n % 8), uno a la vez ---
    cmp     eax, esi
    jge     .sum_done
    vmovss  xmm1, [rdi + rax*4]
    vaddss  xmm0, xmm0, xmm1
    inc     eax
    jmp     .sum_scalar_tail

.sum_done:
    vzeroupper                     ; evita penalizacion de transicion AVX/SSE
    ret

; ---------------------------------------------------------------
; void compute_stats(const float *arr, int n,
;                     float *mean, float *var, float *min, float *max)
;   rdi = arr, esi = n, rdx = mean*, rcx = var*, r8 = min*, r9 = max*
;
;   var = varianza POBLACIONAL = sum((x - mean)^2) / n
;   n <= 0 -> escribe 0.0 en mean/var/min/max.
;
; Registros callee-saved durante el cuerpo:
;   r12 = arr   r13 = n   r14 = mean*   r15 = var*   rbx = min*
;   [rsp] = max*   (6 valores, solo 5 callee-saved -> uno va a la pila)
;
; Pasada 2 (vectorial, 8 carriles):
;   ymm2 = acumulador de (x-mean)^2      ymm3 = mean en los 8 carriles
;   ymm4 = min parcial por carril        ymm5 = max parcial por carril
;   ymm6 = 8 floats cargados             ymm7 = temporal (x-mean)^2
;   xmm1 = (float)n     (no se toca en el bucle)
; ---------------------------------------------------------------
compute_stats:
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15                    ; 5 pushes: rsp queda alineado a 16

    test    esi, esi
    jle     .cs_zero               ; n <= 0 -> caso borde

    sub     rsp, 16                ; espacio para max* (y mantiene rsp alineado a 16)
    mov     [rsp], r9              ; [rsp] = max*
    mov     rbx, r8                ; rbx = min*
    mov     r12, rdi               ; r12 = arr
    mov     r13d, esi              ; r13 = n
    mov     r14, rdx               ; r14 = mean*
    mov     r15, rcx               ; r15 = var*

    ; --- mean = sum(arr) / n, con dos acumuladores vectoriales double ---
    vxorpd  ymm10, ymm10, ymm10
    vxorpd  ymm11, ymm11, ymm11
    xor     eax, eax
    mov     ecx, r13d
    and     ecx, ~7
.mean_vec_loop:
    cmp     eax, ecx
    jge     .mean_reduce
    vmovaps ymm6, [r12 + rax*4]
    vcvtps2pd ymm8, xmm6
    vextractf128 xmm7, ymm6, 1
    vcvtps2pd ymm9, xmm7
    vaddpd  ymm10, ymm10, ymm8
    vaddpd  ymm11, ymm11, ymm9
    add     eax, 8
    jmp     .mean_vec_loop

.mean_reduce:
    vextractf128 xmm8, ymm10, 1
    vaddpd  xmm10, xmm10, xmm8
    vhaddpd xmm10, xmm10, xmm10
    vextractf128 xmm8, ymm11, 1
    vaddpd  xmm11, xmm11, xmm8
    vhaddpd xmm11, xmm11, xmm11
    vaddsd  xmm10, xmm10, xmm11
.mean_tail:
    cmp     eax, r13d
    jge     .mean_done
    vmovss  xmm6, [r12 + rax*4]
    vcvtss2sd xmm6, xmm6, xmm6
    vaddsd  xmm10, xmm10, xmm6
    inc     eax
    jmp     .mean_tail
.mean_done:
    vxorpd  xmm1, xmm1, xmm1
    vcvtsi2sd xmm1, xmm1, r13d
    vdivsd  xmm10, xmm10, xmm1
    vmovapd xmm15, xmm10         ; conservar mean double para la pasada 2
    vcvtsd2ss xmm0, xmm10, xmm10
    vmovss  [r14], xmm0            ; *mean = (float) mean

    ; --- inicializacion de la pasada 2 ---
    vbroadcastss ymm3, xmm0        ; ymm3 = [mean x8]
    vxorpd  ymm10, ymm10, ymm10    ; sum_sq parcial, 4 doubles bajos
    vxorpd  ymm11, ymm11, ymm11    ; sum_sq parcial, 4 doubles altos
    vbroadcastsd ymm14, xmm15      ; mean double en 4 carriles
    vbroadcastss ymm4, [r12]       ; min = arr[0] en los 8 carriles (n >= 1 aqui)
    vmovaps ymm5, ymm4             ; max = arr[0] en los 8 carriles
    xor     eax, eax               ; i = 0
    mov     ecx, r13d
    and     ecx, ~7                ; ecx = n redondeado hacia abajo a multiplo de 8

.cs_vec_loop:
    cmp     eax, ecx
    jge     .cs_reduce
    vmovaps ymm6, [r12 + rax*4]    ; 8 floats
    vextractf128 xmm7, ymm6, 1
    vcvtps2pd ymm8, xmm6           ; cuatro x en double
    vcvtps2pd ymm9, xmm7           ; cuatro x en double
    vsubpd  ymm8, ymm8, ymm14
    vsubpd  ymm9, ymm9, ymm14
    vmulpd  ymm8, ymm8, ymm8
    vmulpd  ymm9, ymm9, ymm9
    vaddpd  ymm10, ymm10, ymm8
    vaddpd  ymm11, ymm11, ymm9
    vminps  ymm4, ymm4, ymm6       ; min por carril
    vmaxps  ymm5, ymm5, ymm6       ; max por carril
    add     eax, 8
    jmp     .cs_vec_loop

.cs_reduce:
    ; --- reduccion horizontal de los dos acumuladores double ---
    vextractf128 xmm8, ymm10, 1
    vaddpd  xmm10, xmm10, xmm8
    vhaddpd xmm10, xmm10, xmm10
    vextractf128 xmm8, ymm11, 1
    vaddpd  xmm11, xmm11, xmm8
    vhaddpd xmm11, xmm11, xmm11
    vaddsd  xmm10, xmm10, xmm11

    ; --- reduccion horizontal de min: 8 -> 4 -> 2 -> 1 ---
    vextractf128 xmm8, ymm4, 1
    vminps  xmm4, xmm4, xmm8       ; 4 minimos parciales
    vpermilps xmm8, xmm4, 0x0E     ; xmm8[0..1] = xmm4[2..3]
    vminps  xmm4, xmm4, xmm8       ; 2 minimos parciales (carriles 0-1)
    vpermilps xmm8, xmm4, 0x01     ; xmm8[0] = xmm4[1]
    vminps  xmm4, xmm4, xmm8       ; xmm4[0] = min de los 8 carriles

    ; --- reduccion horizontal de max (mismo esquema) ---
    vextractf128 xmm8, ymm5, 1
    vmaxps  xmm5, xmm5, xmm8
    vpermilps xmm8, xmm5, 0x0E
    vmaxps  xmm5, xmm5, xmm8
    vpermilps xmm8, xmm5, 0x01
    vmaxps  xmm5, xmm5, xmm8       ; xmm5[0] = max de los 8 carriles
    vmovaps xmm12, xmm4             ; min escalar para el tail
    vmovaps xmm13, xmm5             ; max escalar para el tail

.cs_tail:
    ; --- remanente (n % 8), un elemento por iteracion ---
    cmp     eax, r13d
    jge     .cs_finish
    vmovss  xmm6, [r12 + rax*4]    ; x
    vminss  xmm12, xmm12, xmm6
    vmaxss  xmm13, xmm13, xmm6
    vcvtss2sd xmm6, xmm6, xmm6
    vsubsd  xmm6, xmm6, xmm15      ; x - mean (xmm15[0] = mean double)
    vmulsd  xmm6, xmm6, xmm6
    vaddsd  xmm10, xmm10, xmm6
    inc     eax
    jmp     .cs_tail

.cs_finish:
    vcvtsi2sd xmm1, xmm1, r13d
    vdivsd  xmm10, xmm10, xmm1     ; var = sum_sq / n
    vcvtsd2ss xmm2, xmm10, xmm10
    vmovss  [r15], xmm2            ; *var
    vmovss  [rbx], xmm12           ; *min
    mov     rax, [rsp]             ; rax = max*
    vmovss  [rax], xmm13           ; *max
    add     rsp, 16
    jmp     .cs_done

.cs_zero:
    vxorps  xmm0, xmm0, xmm0
    vmovss  [rdx], xmm0
    vmovss  [rcx], xmm0
    vmovss  [r8], xmm0
    vmovss  [r9], xmm0

.cs_done:
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    vzeroupper
    ret

; ---------------------------------------------------------------
; void normalize_array(const float *in, float *out, int n,
;                       float mean, float stddev)
;   rdi = in, rsi = out, edx = n, xmm0 = mean, xmm1 = stddev
;
;   out[i] = (in[i] - mean) / stddev
;   Caso borde stddev == 0.0: out[i] = in[i]. Se logra sin un segundo
;   bucle usando mean = 0.0 y stddev = 1.0, porque (x - 0) / 1 == x
;   exactamente en IEEE-754.
;
;   ymm8 = mean x8   ymm9 = stddev x8   ymm2 = temporal
; ---------------------------------------------------------------
normalize_array:
    vxorps  xmm2, xmm2, xmm2
    vucomiss xmm1, xmm2            ; stddev vs 0.0
    jne     .norm_setup            ; stddev != 0 -> usar mean/stddev recibidos
    vxorps  xmm0, xmm0, xmm0       ; mean   = 0.0
    mov     eax, 0x3F800000        ; 1.0f en IEEE-754
    vmovd   xmm1, eax              ; stddev = 1.0

.norm_setup:
    vbroadcastss ymm8, xmm0        ; ymm8 = [mean x8]
    vbroadcastss ymm9, xmm1        ; ymm9 = [stddev x8]
    xor     eax, eax               ; i = 0
    mov     ecx, edx
    and     ecx, ~7                ; ecx = n redondeado hacia abajo a multiplo de 8

.norm_vec_loop:
    cmp     eax, ecx
    jge     .norm_tail
    vmovaps ymm2, [rdi + rax*4]    ; 8 floats de entrada
    vsubps  ymm2, ymm2, ymm8       ; x - mean
    vdivps  ymm2, ymm2, ymm9       ; (x - mean) / stddev
    vmovaps [rsi + rax*4], ymm2    ; 8 floats de salida
    add     eax, 8
    jmp     .norm_vec_loop

.norm_tail:
    cmp     eax, edx
    jge     .norm_done
    vmovss  xmm2, [rdi + rax*4]
    vsubss  xmm2, xmm2, xmm8       ; xmm8[0] = mean
    vdivss  xmm2, xmm2, xmm9       ; xmm9[0] = stddev
    vmovss  [rsi + rax*4], xmm2
    inc     eax
    jmp     .norm_tail

.norm_done:
    vzeroupper
    ret

; Declara explicitamente que este objeto NO requiere pila ejecutable.
; NASM no emite esta seccion por defecto (GCC si), y sin ella el
; enlazador desactiva la proteccion NX del ejecutable completo.
section .note.GNU-stack noalloc noexec nowrite progbits