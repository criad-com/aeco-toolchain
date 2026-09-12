//
// Copyright 2026 AECO
//
// © AECO — all rights reserved. See the NOTICE file.
//
#ifndef AECO_BASE_FIXBASE_API_H
#define AECO_BASE_FIXBASE_API_H

#include "pxr/base/arch/export.h"

#if defined(PXR_STATIC)
#   define FIXBASE_API
#   define FIXBASE_API_TEMPLATE_CLASS(...)
#   define FIXBASE_API_TEMPLATE_STRUCT(...)
#   define FIXBASE_LOCAL
#else
#   if defined(FIXBASE_EXPORTS)
#       define FIXBASE_API ARCH_EXPORT
#       define FIXBASE_API_TEMPLATE_CLASS(...) ARCH_EXPORT_TEMPLATE(class, __VA_ARGS__)
#       define FIXBASE_API_TEMPLATE_STRUCT(...) ARCH_EXPORT_TEMPLATE(struct, __VA_ARGS__)
#   else
#       define FIXBASE_API ARCH_IMPORT
#       define FIXBASE_API_TEMPLATE_CLASS(...) ARCH_IMPORT_TEMPLATE(class, __VA_ARGS__)
#       define FIXBASE_API_TEMPLATE_STRUCT(...) ARCH_IMPORT_TEMPLATE(struct, __VA_ARGS__)
#   endif
#   define FIXBASE_LOCAL ARCH_HIDDEN
#endif

#endif // AECO_BASE_FIXBASE_API_H
