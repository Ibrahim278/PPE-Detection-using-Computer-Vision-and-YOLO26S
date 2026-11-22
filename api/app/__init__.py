"""PPE compliance API."""

import os

# Ultralytics sets OMP_NUM_THREADS=1 on import when it's unset (meant for training dataloaders),
# which makes CPU inference single-threaded. Use the available cores unless the operator chose a
# number (PPE_CPU_THREADS, or OMP_NUM_THREADS itself). Must run before torch/ultralytics import.
if not os.environ.get("OMP_NUM_THREADS"):
    _n = os.environ.get("PPE_CPU_THREADS") or str(getattr(os, "process_cpu_count", os.cpu_count)() or 1)
    os.environ["OMP_NUM_THREADS"] = _n
