#pragma once

#if defined(_WIN32)
#  define AECO_EMBED_API __declspec(dllexport)
#else
#  define AECO_EMBED_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

AECO_EMBED_API int aeco_embed_probe(const char* out_path);
AECO_EMBED_API const char* aeco_embed_namespace(void);

#ifdef __cplusplus
}
#endif
