//
// Copyright 2026 AECO
//
// © AECO — all rights reserved. See the NOTICE file.
//
#include "pxr/pxr.h"
#include "aeco/base/fixBase/debugCodes.h"

#include "pxr/base/tf/debug.h"
#include "pxr/base/tf/registryManager.h"

PXR_NAMESPACE_OPEN_SCOPE

TF_REGISTRY_FUNCTION(TfDebug)
{
    TF_DEBUG_ENVIRONMENT_SYMBOL(FIXBASE_INIT, "fixBase initialization");
}

PXR_NAMESPACE_CLOSE_SCOPE
