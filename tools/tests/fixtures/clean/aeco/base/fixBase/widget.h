//
// Copyright 2026 AECO
//
// © AECO — all rights reserved. See the NOTICE file.
//
#ifndef AECO_BASE_FIXBASE_WIDGET_H
#define AECO_BASE_FIXBASE_WIDGET_H

/// \file fixBase/widget.h

#include "pxr/pxr.h"
#include "aeco/base/fixBase/api.h"

#include <string>

PXR_NAMESPACE_OPEN_SCOPE

/// \class AecoWidget
///
/// A tiny public class used by the linter's clean fixture.
class AecoWidget
{
public:
    /// Return the widget's label.
    FIXBASE_API
    static std::string GetLabel();
};

PXR_NAMESPACE_CLOSE_SCOPE

#endif // AECO_BASE_FIXBASE_WIDGET_H
