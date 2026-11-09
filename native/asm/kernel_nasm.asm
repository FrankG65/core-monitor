; ============================================================================================================
; mandel4_asm - hand-written Mandelbrot kernel in x64 assembler (NASM, AVX2) for Linux
;
; Same algorithm and the same instructions in the same order as kernel.asm (MASM, Windows) - only the
; calling convention differs. See kernel.asm for the explanation of the computation.
;
; Called from C (System V AMD64 calling convention, Linux):
;   void mandel4_asm(const double* cr, const double* ci, int max_iter, int64_t* esc_it, double* esc_r2, unsigned active)
;   rdi = cr   rsi = ci   edx = max_iter   rcx = esc_it   r8 = esc_r2   r9d = active
; To keep the loop identical to the Windows version, the arguments are first moved into the same registers:
;   r8d = max_iter   r9 = esc_it   r10 = esc_r2   r11d = active
; All ymm registers are "volatile" under System V - nothing has to be saved. The 32 bytes of scratch space for
; |z|^2 lie in the "red zone" below the stack pointer (allowed for functions that call nothing else).
; ============================================================================================================

        default rel
        section .rodata
        align 8
LIMIT:  dq      256.0           ; escape radius 16, squared
TWO:    dq      2.0

        section .text
        global  mandel4_asm
mandel4_asm:
        mov     r10, r8                         ; esc_r2
        mov     r11d, r9d                       ; active lanes
        mov     r9, rcx                         ; esc_it
        mov     r8d, edx                        ; max_iter

        ; ---- initial values ----
        vmovupd ymm0, [rdi]                     ; cr  (4 values)
        vmovupd ymm1, [rsi]                     ; ci  (4 values)
        vxorpd  ymm2, ymm2, ymm2                ; zr = 0
        vxorpd  ymm3, ymm3, ymm3                ; zi = 0
        vbroadcastsd ymm4, [LIMIT]              ; 256.0 into all 4 lanes
        vbroadcastsd ymm5, [TWO]                ; 2.0   into all 4 lanes
        mov     rax, -1
        mov     qword [r9],    rax              ; esc_it[0..3] = -1 ("not escaped yet")
        mov     qword [r9+8],  rax
        mov     qword [r9+16], rax
        mov     qword [r9+24], rax
        and     r11d, 0Fh
        jz      done                            ; no lane to compute (all certainly inside the set)
        xor     eax, eax                        ; step = 0

iter_loop:
        cmp     eax, r8d                        ; max_iter reached? -> remaining lanes belong to the set
        jge     done
        vmulpd  ymm6, ymm2, ymm2                ; zr2 = zr*zr
        vmulpd  ymm7, ymm3, ymm3                ; zi2 = zi*zi
        vaddpd  ymm8, ymm6, ymm7                ; |z|^2 = zr2 + zi2
        vcmppd  ymm9, ymm8, ymm4, 1Eh           ; compare |z|^2 > 256  (predicate 1Eh = GT_OQ)
        vmovmskpd edx, ymm9                     ; one bit per lane: 1 = escaped
        and     edx, r11d                       ; only lanes that were active so far
        jnz     escaped
continue_iter:
        vmulpd  ymm9, ymm5, ymm2                ; 2*zr
        vmulpd  ymm9, ymm9, ymm3                ; (2*zr)*zi
        vaddpd  ymm3, ymm9, ymm1                ; zi = (2*zr)*zi + ci
        vsubpd  ymm2, ymm6, ymm7                ; zr2 - zi2
        vaddpd  ymm2, ymm2, ymm0                ; zr = (zr2 - zi2) + cr
        inc     eax
        jmp     iter_loop

escaped:
        ; record step and |z|^2 for each lane that just escaped
        vmovupd [rsp-32], ymm8                  ; store |z|^2 of all 4 lanes temporarily (red zone)
        xor     ecx, ecx                        ; lane l = 0
lane_loop:
        bt      edx, ecx                        ; did lane l just escape?
        jnc     next_lane
        mov     qword [r9+rcx*8], rax           ; esc_it[l] = step
        vmovsd  xmm9, [rsp-32+rcx*8]
        vmovsd  qword [r10+rcx*8], xmm9         ; esc_r2[l] = |z|^2
next_lane:
        inc     ecx
        cmp     ecx, 4
        jb      lane_loop
        not     edx
        and     r11d, edx                       ; remove escaped lanes from the active mask
        jnz     continue_iter                   ; lanes still active -> keep computing

done:
        vzeroupper                              ; clear upper register halves (avoids SSE transition penalties)
        ret

        section .note.GNU-stack noalloc noexec nowrite progbits   ; stack need not be executable
