#include "../../firmware/motor/WindingHardwareAdapter.h"
#include <assert.h>

using namespace WindingHardware;

int main() {
    DisabledAdapter adapter;
    PulseRequest request = {10};

    assert(adapter.status() == ADAPTER_DISABLED);
    assert(adapter.requestInjection(request) == ADAPTER_REFUSED);
    assert(adapter.status() == ADAPTER_REFUSED);

    // OFF cannot be claimed verified when this stub has no physical readback.
    assert(!adapter.forceOutputsOff());
    assert(adapter.status() == ADAPTER_DISABLED);

    // Invalid and oversized requests are also refused; the stub has no
    // activation path under any input.
    request.durationMs = 0;
    assert(adapter.requestInjection(request) == ADAPTER_REFUSED);
    request.durationMs = 1000;
    assert(adapter.requestInjection(request) == ADAPTER_REFUSED);
    return 0;
}
