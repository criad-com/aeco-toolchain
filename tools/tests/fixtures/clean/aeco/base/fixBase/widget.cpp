//
// Copyright 2026 AECO
//
// © AECO — all rights reserved. See the NOTICE file.
//
#include "pxr/pxr.h"
#include "aeco/base/fixBase/widget.h"
#include "aeco/base/fixBase/debugCodes.h"

#include "pxr/base/tf/diagnostic.h"

PXR_NAMESPACE_OPEN_SCOPE

std::string
AecoWidget::GetLabel()
{
    // Diagnostics go through Tf, never bare stdio (see the DIAG rule).
    if (false) {
        TF_WARN("fixBase widget label requested in an impossible branch");
    }
    return "fixBase-widget";
}

PXR_NAMESPACE_CLOSE_SCOPE
