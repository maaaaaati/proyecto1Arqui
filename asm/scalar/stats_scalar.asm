; =============================================================
; stats_scalar.asm
; Version ESCALAR (referencia) de los kernels de computo.
;
; Convencion de llamada: System V AMD64 ABI
;   enteros/punteros: rdi, rsi, rdx, rcx, r8, r9
;   flotantes:        xmm0, xmm1, xmm2, ...
;   retorno float:    xmm0
;   callee-saved:     rbx, rbp, r12-r15 (si los usa, debe preservarlos)
; =============================================================
    global sum_array
    global compute_stats
    global normalize_array

    section .text

; ---------------------------------------------------------------
; float sum_array(const float *arr, int n)
;   rdi = arr, esi = n
;   retorna la suma en xmm0
;
; IMPLEMENTADA COMO EJEMPLO: estudien este patron (recorrido,
; acumulador, condicion de salida) antes de escribir compute_stats
; y normalize_array.
; ---------------------------------------------------------------
sum_array:
    xor     eax, eax           ; eax = i = 0
    xorps   xmm0, xmm0         ; xmm0 = acumulador = 0.0

.sum_loop:
    cmp     eax, esi
    jge     .sum_done
    movss   xmm1, [rdi + rax*4]
    addss   xmm0, xmm1
    inc     eax
    jmp     .sum_loop

.sum_done:
    ret

; ---------------------------------------------------------------
; void compute_stats(const float *arr, int n,
;                     float *mean, float *var, float *min, float *max)
;   rdi = arr, esi = n, rdx = mean*, rcx = var*, r8 = min*, r9 = max*
;
;   var = varianza POBLACIONAL = sum((x - mean)^2) / n
;   Caso borde: si n == 0, escriba 0.0 en mean/var/min/max.
;
; TODO (estudiante):
;   1) Calcular mean = suma(arr) / n. Puede reutilizar sum_array con
;      'call sum_array', pero recuerde que eso destruye los
;      registros caller-saved (rax, rcx, rdx, rsi, rdi, r8-r11):
;      guarde arr/n/mean*/var*/min*/max* en registros callee-saved
;      (rbx, r12-r15) ANTES de llamar.
;   2) Recorrer el arreglo una segunda vez para acumular
;      sum((x - mean)^2) y obtener var = esa suma / n.
;   3) Recorrer el arreglo (puede combinarlo con el paso 1) llevando
;      min y max con comiss + saltos condicionales (ja/jb, etc.)
;      o con las instrucciones minss/maxss.
;   4) Guardar los resultados en las direcciones recibidas por
;      puntero: [rdx]=mean, [rcx]=var, [r8]=min, [r9]=max.
;   5) No olvide restaurar los registros callee-saved en el epilogo.
; ---------------------------------------------------------------
; ---------------------------------------------------------------
; void compute_stats(const float *arr, int n,
;                     float *mean, float *var, float *min, float *max)
;   rdi = arr, esi = n, rdx = mean*, rcx = var*, r8 = min*, r9 = max*
; ---------------------------------------------------------------
; ---------------------------------------------------------------
; void compute_stats(const float *arr, int n,
;                     float *mean, float *var, float *min, float *max)
;   rdi = arr, esi = n, rdx = mean*, rcx = var*, r8 = min*, r9 = max*
; ---------------------------------------------------------------
compute_stats:
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15
    push    r8              ; min*  -> queda en [rsp+8] tras el siguiente push
    push    r9              ; max*  -> queda en [rsp]

    test    esi, esi
    jz      .zero_case

    mov     r12, rdi         ; r12 = arr
    mov     r13, rsi         ; r13 = n
    mov     r14, rdx         ; r14 = mean*
    mov     r15, rcx         ; r15 = var*

    ; --- mean = sum_array(arr, n) / n ---
    mov     rdi, r12
    mov     esi, r13d
    call    sum_array        ; xmm0 = total

    cvtsi2ss xmm1, r13d
    divss    xmm0, xmm1      ; xmm0 = mean
    movss    [r14], xmm0     ; *mean = xmm0

    ; --- var, min, max en un solo recorrido ---
    xorps   xmm2, xmm2        ; sum_sq = 0.0
    movss   xmm4, [r12]       ; xmm4 = min, semilla con arr[0]
    movss   xmm5, [r12]       ; xmm5 = max, semilla con arr[0]
    xor     eax, eax          ; i = 0
.var_loop:
    cmp     eax, r13d
    jge     .var_done

    movss   xmm3, [r12 + rax*4]   ; xmm3 = arr[i]

    movss   xmm6, xmm3
    subss   xmm6, xmm0            ; xmm6 = arr[i] - mean
    mulss   xmm6, xmm6            ; xmm6 = (arr[i]-mean)^2
    addss   xmm2, xmm6            ; sum_sq += xmm6

    minss   xmm4, xmm3            ; min = min(min, arr[i])
    maxss   xmm5, xmm3            ; max = max(max, arr[i])

    inc     eax
    jmp     .var_loop

.var_done:
    cvtsi2ss xmm1, r13d
    divss    xmm2, xmm1
    movss    [r15], xmm2          ; *var = xmm2

    mov     rax, [rsp]            ; recuperar max* del tope de la pila
    mov     rcx, [rsp + 8]        ; recuperar min*
    movss   [rcx], xmm4           ; *min = xmm4
    movss   [rax], xmm5           ; *max = xmm5

    jmp     .done

.zero_case:
    xorps   xmm0, xmm0
    movss   [rdx], xmm0
    movss   [rcx], xmm0
    movss   [r8], xmm0
    movss   [r9], xmm0

.done:
    pop     r9
    pop     r8
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    ret
; ---------------------------------------------------------------
; void normalize_array(const float *in, float *out, int n,
;                       float mean, float stddev)
;   rdi = in, rsi = out, edx = n, xmm0 = mean, xmm1 = stddev
;
;   out[i] = (in[i] - mean) / stddev
;   Caso borde: si stddev == 0.0, copie in[i] en out[i] tal cual
;   (evite division por cero).
;
; TODO (estudiante): implementar el bucle escalar.
; Sugerencia: guarde mean (xmm0) y stddev (xmm1) en registros que no
; se sobrescriban dentro del bucle (por ejemplo xmm8/xmm9, que en
; System V no se usan para pasar argumentos), o vuelva a cargarlos
; en cada iteracion desde una copia guardada en la pila.
; ---------------------------------------------------------------
; ---------------------------------------------------------------
; void normalize_array(const float *in, float *out, int n,
;                       float mean, float stddev)
;   rdi = in, rsi = out, edx = n, xmm0 = mean, xmm1 = stddev
; ---------------------------------------------------------------
normalize_array:
    movss   xmm8, xmm0        ; mean guardado en xmm8 (no lo pisa el loop)
    movss   xmm9, xmm1        ; stddev guardado en xmm9

    xorps   xmm10, xmm10
    ucomiss xmm9, xmm10        ; comparar stddev contra 0.0
    je      .copy_loop         ; si stddev == 0.0, salto al camino "copiar tal cual"

    xor     eax, eax           ; i = 0
.norm_loop:
    cmp     eax, edx
    jge     .norm_done

    movss   xmm2, [rdi + rax*4]  ; xmm2 = in[i]
    subss   xmm2, xmm8            ; xmm2 = in[i] - mean
    divss   xmm2, xmm9            ; xmm2 = (in[i]-mean) / stddev
    movss   [rsi + rax*4], xmm2   ; out[i] = xmm2

    inc     eax
    jmp     .norm_loop

.copy_loop:
    xor     eax, eax
.copy_loop_body:
    cmp     eax, edx
    jge     .norm_done

    movss   xmm2, [rdi + rax*4]
    movss   [rsi + rax*4], xmm2   ; out[i] = in[i], sin normalizar

    inc     eax
    jmp     .copy_loop_body

.norm_done:
    ret