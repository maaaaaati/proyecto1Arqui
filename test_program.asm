global _start
extern compute_stats

section .data
arr:   dd 1.0, 2.0, 3.0, 4.0, 5.0
n:     dd 5

mean:  dd 0.0
var:   dd 0.0
minv:  dd 0.0
maxv:  dd 0.0

section .text
_start:
    lea rdi, [arr]
    mov esi, dword [n]

    lea rdx, [mean]
    lea rcx, [var]
    lea r8,  [minv]
    lea r9,  [maxv]

    call compute_stats

    ; exit
    mov eax, 60
    xor edi, edi
    syscall