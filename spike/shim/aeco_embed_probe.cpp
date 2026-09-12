#include "aeco_embed_probe.h"

#include <pxr/pxr.h>
#include <pxr/base/tf/token.h>
#include <pxr/base/vt/dictionary.h>
#include <pxr/base/vt/value.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/sdf/types.h>

#include <exception>
#include <string>

#define AECO_STRINGIFY_IMPL(value) #value
#define AECO_STRINGIFY(value) AECO_STRINGIFY_IMPL(value)

PXR_NAMESPACE_USING_DIRECTIVE

extern "C" AECO_EMBED_API int
aeco_embed_probe(const char* out_path)
{
    if (!out_path || !*out_path) {
        return 1;
    }

    try {
        const SdfLayerRefPtr layer = SdfLayer::CreateAnonymous(".usda");
        if (!layer) {
            return 2;
        }

        const SdfPrimSpecHandle prim =
            SdfCreatePrimInLayer(layer, SdfPath("/EmbeddedProbe"));
        if (!prim) {
            return 3;
        }
        prim->SetSpecifier(SdfSpecifierDef);
        prim->SetTypeName(TfToken("Scope"));

        VtDictionary customData;
        customData["aeco:producer"] = VtValue(std::string("usd-embed"));
        customData["aeco:namespace"] =
            VtValue(std::string(aeco_embed_namespace()));
        layer->SetCustomLayerData(customData);

        return layer->Export(out_path) ? 0 : 4;
    } catch (const std::exception&) {
        return 5;
    } catch (...) {
        return 6;
    }
}

extern "C" AECO_EMBED_API const char*
aeco_embed_namespace(void)
{
    return AECO_STRINGIFY(PXR_INTERNAL_NS);
}
