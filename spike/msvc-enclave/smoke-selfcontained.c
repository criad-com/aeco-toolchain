/* smoke-selfcontained.c — standalone proof that AecoLandingC.dll is
 * self-contained: LoadLibrary it from a directory with NO OpenUSD/python on
 * PATH, resolve every one of the 19 aeco_landing_* symbols, and exercise the
 * ABI v2 guard (aeco_landing_abi_version() == 2) plus aeco_landing_version().
 *
 * This is the enclave-side analogue of the spike host's dlopen check, reduced
 * to the self-containment claim. Build with `cl /O2 smoke-selfcontained.c`,
 * then run from an isolated dir holding only AecoLandingC.dll (+ tbb.dll until
 * the static-TBB follow-up lands) with PATH scrubbed of C:\OpenUSD — see the
 * "Standalone self-containment smoke" section of README.md.
 *
 *   smoke-selfcontained.exe [path-to-AecoLandingC.dll]
 *
 * Exit 0 = loaded + 19/19 resolved + ABI guard passed.
 *
 * ABI history: v1 = 18 symbols; v2 (aeco-meta #96) adds aeco_landing_set_mesh
 * (the 19th) for polygon-mesh authoring and bumps AECO_LANDING_C_ABI_VERSION
 * to 2. The managed interop enforces v2 at load, so v1 DLLs are refused.
 */
#include <windows.h>
#include <stdio.h>

#define EXPECTED_ABI 2

typedef int (*fn_abi)(void);
typedef const char *(*fn_ver)(void);

static const char *SYMS[] = {
    "aeco_landing_version", "aeco_landing_abi_version", "aeco_landing_last_error",
    "aeco_landing_create", "aeco_landing_destroy", "aeco_landing_is_valid",
    "aeco_landing_def_prim", "aeco_landing_def_prim_kv", "aeco_landing_minted_id",
    "aeco_landing_over_prim", "aeco_landing_apply_api",
    "aeco_landing_set_semantic_attr_string", "aeco_landing_set_semantic_attr_token",
    "aeco_landing_set_semantic_attr_int", "aeco_landing_set_quarantined_prop",
    "aeco_landing_set_extent", "aeco_landing_set_mesh",
    "aeco_landing_add_relationship_by_id", "aeco_landing_export"};

int main(int argc, char **argv)
{
    const char *dll = (argc > 1) ? argv[1] : "AecoLandingC.dll";
    HMODULE h = LoadLibraryA(dll);
    if (!h) {
        printf("LOAD_FAIL err=%lu (%s)\n", (unsigned long)GetLastError(), dll);
        return 2;
    }
    printf("LOADED %s\n", dll);

    int missing = 0;
    int n = (int)(sizeof(SYMS) / sizeof(SYMS[0]));
    for (int i = 0; i < n; i++) {
        if (!GetProcAddress(h, SYMS[i])) {
            printf("MISSING %s\n", SYMS[i]);
            missing++;
        }
    }
    printf("RESOLVED %d/%d symbols\n", n - missing, n);

    fn_abi abi = (fn_abi)GetProcAddress(h, "aeco_landing_abi_version");
    fn_ver ver = (fn_ver)GetProcAddress(h, "aeco_landing_version");
    if (!abi) { printf("NO_ABI_FN\n"); return 3; }
    int a = abi();
    printf("ABI_VERSION=%d\n", a);
    if (a != EXPECTED_ABI) { printf("ABI_GUARD_FAIL expected %d\n", EXPECTED_ABI); return 3; }
    if (ver) { const char *v = ver(); printf("VERSION=%s\n", v ? v : "(null)"); }

    if (missing) { printf("SMOKE_FAIL missing=%d\n", missing); return 1; }
    printf("SMOKE_OK self-contained load + 19 symbols + ABI v%d guard passed\n", EXPECTED_ABI);
    return 0;
}
