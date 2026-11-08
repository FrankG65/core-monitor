; ============================================================================================================
; mandel4_asm - hand-written Mandelbrot kernel in x64 assembler (MASM, AVX2)
;
; Computes 4 pixels at once: each 256-bit register (ymm) holds 4 floating-point numbers (double).
; Per step:     zr2 = zr*zr,  zi2 = zi*zi,  |z|^2 = zr2 + zi2
;               if |z|^2 > 256: the point has "escaped" -> remember step number and |z|^2
;               zi  = (2*zr)*zi + ci
;               zr  = (zr2 - zi2) + cr
; Same operations in the same order as C#, Rust, numba - deliberately WITHOUT FMA (fused multiply-add),
; so that every result matches bit for bit. The color is computed afterwards by the C program.
;
; Called from C (Windows x64 calling convention):
;   void mandel4_asm(const double* cr, const double* ci, int max_iter, int64_t* esc_it, double* esc_r2, unsigned active)
;   rcx = cr (4 values)   rdx = ci (4 values)   r8d = max_iter   r9 = esc_it (4 results)
;   [stack] = esc_r2 (5th argument) and active (6th argument: bit mask of the lanes to compute; the others are
;   certainly inside the set, e.g. in the cardioid - the C program checks that beforehand)
;   esc_it[l] = step in which lane l escaped, or -1 (inside the set); esc_r2[l] = |z|^2 at that moment
;
; Register usage in the loop:
;   ymm0 = cr        ymm1 = ci        ymm2 = zr        ymm3 = zi
;   ymm4 = 256.0     ymm5 = 2.0       ymm6 = zr2       ymm7 = zi2      ymm8 = |z|^2    ymm9 = comparison/temporary
;   eax  = step counter    r11d = mask of the lanes still active (bit l = lane l)    r10 = pointer esc_r2
; xmm6-xmm9 must be preserved per the Windows convention -> they are saved on the stack.
; ============================================================================================================

        .data
        align 8
LIMIT   real8   256.0           ; escape radius 16, squared
TWO     real8   2.0

        .code
mandel4_asm PROC
        ; ---- prologue: room for 4 saved xmm registers (64 bytes) + 32 bytes scratch + alignment ----
        sub     rsp, 104
        vmovdqu xmmword ptr [rsp+0],  xmm6
        vmovdqu xmmword ptr [rsp+16], xmm7
        vmovdqu xmmword ptr [rsp+32], xmm8
        vmovdqu xmmword ptr [rsp+48], xmm9
        mov     r10, qword ptr [rsp+104+40]     ; 5th argument (esc_r2) lies after return address and shadow space

        ; ---- initial values ----
        vmovupd ymm0, ymmword ptr [rcx]         ; cr  (4 values)
        vmovupd ymm1, ymmword ptr [rdx]         ; ci  (4 values)
        vxorpd  ymm2, ymm2, ymm2                ; zr = 0
        vxorpd  ymm3, ymm3, ymm3                ; zi = 0
        vbroadcastsd ymm4, LIMIT                ; 256.0 into all 4 lanes
        vbroadcastsd ymm5, TWO                  ; 2.0   into all 4 lanes
        mov     rax, -1
        mov     qword ptr [r9],    rax          ; esc_it[0..3] = -1 ("not escaped yet")
        mov     qword ptr [r9+8],  rax
        mov     qword ptr [r9+16], rax
        mov     qword ptr [r9+24], rax
        mov     r11d, dword ptr [rsp+104+48]    ; 6th argument: active lanes (normally 0Fh = all 4)
        and     r11d, 0Fh
        jz      done                          ; no lane to compute (all certainly inside the set)
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
        vmovupd ymmword ptr [rsp+64], ymm8      ; store |z|^2 of all 4 lanes temporarily
        xor     ecx, ecx                        ; lane l = 0
lane_loop:
        bt      edx, ecx                        ; did lane l just escape?
        jnc     next_lane
        mov     qword ptr [r9+rcx*8], rax       ; esc_it[l] = step
        vmovsd  xmm9, qword ptr [rsp+64+rcx*8]
        vmovsd  qword ptr [r10+rcx*8], xmm9     ; esc_r2[l] = |z|^2
next_lane:
        inc     ecx
        cmp     ecx, 4
        jb      lane_loop
        not     edx
        and     r11d, edx                       ; remove escaped lanes from the active mask
        jnz     continue_iter                          ; lanes still active -> keep computing

done:
        ; ---- epilogue: clear upper register halves (avoids SSE transition penalties), restore registers ----
        vzeroupper
        vmovdqu xmm6, xmmword ptr [rsp+0]
        vmovdqu xmm7, xmmword ptr [rsp+16]
        vmovdqu xmm8, xmmword ptr [rsp+32]
        vmovdqu xmm9, xmmword ptr [rsp+48]
        add     rsp, 104
        ret
mandel4_asm ENDP
        END
