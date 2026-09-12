#include <pxr/pxr.h>
#include <pxr/base/tf/token.h>
#include <pxr/base/vt/dictionary.h>
#include <pxr/base/vt/value.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/sdf/types.h>

#include <dlfcn.h>

#include <filesystem>
#include <iostream>
#include <string>

#define AECO_STRINGIFY_IMPL(value) #value
#define AECO_STRINGIFY(value) AECO_STRINGIFY_IMPL(value)

PXR_NAMESPACE_USING_DIRECTIVE

namespace {

using ProbeFn = int (*)(const char*);
using NamespaceFn = const char* (*)(void);

bool
AuthorHostLayer(const std::filesystem::path& path)
{
    const SdfLayerRefPtr layer = SdfLayer::CreateAnonymous(".usda");
    if (!layer) {
        return false;
    }

    const SdfPrimSpecHandle prim =
        SdfCreatePrimInLayer(layer, SdfPath("/HostProbe"));
    if (!prim) {
        return false;
    }
    prim->SetSpecifier(SdfSpecifierDef);
    prim->SetTypeName(TfToken("Scope"));

    VtDictionary customData;
    customData["aeco:producer"] = VtValue(std::string("usd-dev"));
    customData["aeco:namespace"] =
        VtValue(std::string(AECO_STRINGIFY(PXR_INTERNAL_NS)));
    layer->SetCustomLayerData(customData);

    return layer->Export(path.string());
}

bool
VerifyLayer(const std::filesystem::path& path,
            const SdfPath& primPath,
            const std::string& producer)
{
    const SdfLayerRefPtr layer = SdfLayer::FindOrOpen(path.string());
    if (!layer || !layer->GetPrimAtPath(primPath)) {
        std::cerr << "failed to parse expected prim " << primPath
                  << " from " << path << '\n';
        return false;
    }

    const VtDictionary customData = layer->GetCustomLayerData();
    const auto producerIt = customData.find("aeco:producer");
    if (producerIt == customData.end() ||
        !producerIt->second.IsHolding<std::string>() ||
        producerIt->second.UncheckedGet<std::string>() != producer) {
        std::cerr << "missing expected customLayerData in " << path << '\n';
        return false;
    }
    return true;
}

} // namespace

int
main(int argc, char** argv)
{
    if (argc != 3) {
        std::cerr << "usage: " << argv[0] << " SHIM_DYLIB OUTPUT_DIRECTORY\n";
        return 64;
    }

    const std::filesystem::path shimPath = argv[1];
    const std::filesystem::path outputDir = argv[2];
    std::filesystem::create_directories(outputDir);

    const std::filesystem::path hostLayer = outputDir / "host.usda";
    const std::filesystem::path embedLayer = outputDir / "embed.usda";
    if (!AuthorHostLayer(hostLayer)) {
        std::cerr << "host USD failed to author " << hostLayer << '\n';
        return 1;
    }

    void* shim = dlopen(shimPath.c_str(), RTLD_NOW | RTLD_LOCAL);
    if (!shim) {
        std::cerr << "dlopen failed: " << dlerror() << '\n';
        return 2;
    }

    dlerror();
    const auto probe = reinterpret_cast<ProbeFn>(
        dlsym(shim, "aeco_embed_probe"));
    const auto embedNamespace = reinterpret_cast<NamespaceFn>(
        dlsym(shim, "aeco_embed_namespace"));
    if (const char* error = dlerror(); error || !probe || !embedNamespace) {
        std::cerr << "dlsym failed: " << (error ? error : "missing symbol")
                  << '\n';
        return 3;
    }

    const int probeResult = probe(embedLayer.c_str());
    if (probeResult != 0) {
        std::cerr << "embedded probe failed with status " << probeResult << '\n';
        return 4;
    }

    const std::string hostNamespace = AECO_STRINGIFY(PXR_INTERNAL_NS);
    const std::string shimNamespace = embedNamespace();
    std::cout << "host internal namespace: " << hostNamespace << '\n'
              << "shim internal namespace: " << shimNamespace << '\n';
    if (hostNamespace == shimNamespace) {
        std::cerr << "host and shim namespaces must differ\n";
        return 5;
    }

    // Both files are deliberately reopened through the host's shared USD.
    const bool hostOk = VerifyLayer(hostLayer, SdfPath("/HostProbe"), "usd-dev");
    const bool embedOk =
        VerifyLayer(embedLayer, SdfPath("/EmbeddedProbe"), "usd-embed");

    // OpenUSD's Darwin Arch layer registers process-lifetime dyld callbacks;
    // intentionally keep the shim loaded until process exit.

    if (!hostOk || !embedOk) {
        return 6;
    }

    std::cout << "embed coexistence spike OK\n";
    return 0;
}
