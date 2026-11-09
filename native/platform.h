/* Small portability layer for the C and C++ variants: threads, atomic counter, lock, timer,
 * pinning a thread to one logical processor, current processor number, lower priority, binary stdout.
 * Windows: Win32 API (as before). Linux: POSIX threads, sched_setaffinity / sched_getcpu, setpriority.
 */
#pragma once
#if !defined(_WIN32) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE   /* CPU_SET, sched_getcpu, pthread_setaffinity_np; must come before the first system header */
#endif
#include <stdint.h>
#include <stdio.h>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <io.h>
#include <fcntl.h>

typedef HANDLE km_thread;
typedef CRITICAL_SECTION km_lock;
typedef volatile LONG km_counter;
#define KM_THREAD_FN DWORD WINAPI
#define KM_THREAD_ARG LPVOID
#define KM_THREAD_RET 0
static void km_thread_start(km_thread *t, LPTHREAD_START_ROUTINE fn, void *arg) { *t = CreateThread(NULL, 0, fn, arg, 0, NULL); }
static void km_thread_join(km_thread t) { WaitForSingleObject(t, INFINITE); CloseHandle(t); }
static void km_lock_init(km_lock *l) { InitializeCriticalSection(l); }
static void km_lock_enter(km_lock *l) { EnterCriticalSection(l); }
static void km_lock_leave(km_lock *l) { LeaveCriticalSection(l); }
static long km_increment(km_counter *c) { return InterlockedIncrement(c); }   /* returns the new value */
static double km_now(void) {
    static LARGE_INTEGER freq;
    LARGE_INTEGER t;
    if (!freq.QuadPart) QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&t);
    return (double)t.QuadPart / freq.QuadPart;
}
static void km_pin_thread(int cpu) { SetThreadAffinityMask(GetCurrentThread(), (DWORD_PTR)1 << cpu); }
static unsigned long km_current_cpu(void) { return GetCurrentProcessorNumber(); }
static void km_below_normal(void) { SetPriorityClass(GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS); }
static void km_binary_stdout(void) { _setmode(_fileno(stdout), _O_BINARY); }   /* no \n -> \r\n */

#else   /* Linux and other POSIX systems */
#include <pthread.h>
#include <sched.h>
#include <time.h>
#include <sys/resource.h>

typedef pthread_t km_thread;
typedef pthread_mutex_t km_lock;
typedef volatile long km_counter;
#define KM_THREAD_FN void *
#define KM_THREAD_ARG void *
#define KM_THREAD_RET NULL
static void km_thread_start(km_thread *t, void *(*fn)(void *), void *arg) { pthread_create(t, NULL, fn, arg); }
static void km_thread_join(km_thread t) { pthread_join(t, NULL); }
static void km_lock_init(km_lock *l) { pthread_mutex_init(l, NULL); }
static void km_lock_enter(km_lock *l) { pthread_mutex_lock(l); }
static void km_lock_leave(km_lock *l) { pthread_mutex_unlock(l); }
static long km_increment(km_counter *c) { return __atomic_add_fetch(c, 1, __ATOMIC_RELAXED); }
static double km_now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}
static void km_pin_thread(int cpu) {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    pthread_setaffinity_np(pthread_self(), sizeof set, &set);   /* fails silently if the CPU is not allowed */
}
static unsigned long km_current_cpu(void) { int c = sched_getcpu(); return c < 0 ? 0 : (unsigned long)c; }
/* nice 5 for the whole process (all threads), like "below normal" on Windows */
static void km_below_normal(void) { setpriority(PRIO_PROCESS, 0, 5); }
static void km_binary_stdout(void) {}   /* POSIX makes no difference between text and binary */
#endif
