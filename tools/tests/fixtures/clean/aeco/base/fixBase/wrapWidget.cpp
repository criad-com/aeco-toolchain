//
// Copyright 2026 AECO
//
// © AECO — all rights reserved. See the NOTICE file.
//
#include "pxr/pxr.h"
#include "aeco/base/fixBase/widget.h"

#include "pxr/external/boost/python.hpp"

PXR_NAMESPACE_USING_DIRECTIVE

using namespace pxr_boost::python;

void wrapWidget()
{
    typedef AecoWidget This;

    class_<This>("Widget", no_init)
        .def("GetLabel", &This::GetLabel)
        .staticmethod("GetLabel")
        ;
}
