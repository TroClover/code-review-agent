# BRT Coding Standard

This document defines the coding standard for the BRT (Better Release Testing) department. It serves as the initial seed for the knowledge base and applies to all Python and C++ code submitted to BRT repositories.

---

## Python Coding Standards

### 1. Naming Conventions

**Variables and functions** use `snake_case`:
```python
# Good
def calculate_latency(sensor_data, threshold_ms):
    processing_start = time.monotonic()
    ...

# Bad
def CalculateLatency(SensorData, ThresholdMs):
    ProcessingStart = time.monotonic()
    ...
```

**Classes** use `PascalCase`:
```python
# Good
class SensorDataProcessor:
    pass

# Bad
class sensor_data_processor:
    pass
```

**Constants** use `UPPER_SNAKE_CASE`:
```python
# Good
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT_MS = 5000
SENSOR_TYPES = ["lidar", "camera", "radar"]

# Bad
maxRetryCount = 3
default_timeout = 5000
```

**Private attributes** use leading underscore:
```python
class DataPipeline:
    def __init__(self):
        self._internal_buffer = []
        self.__secret_key = "..."  # Avoid name mangling, use single underscore
```

### 2. Type Hints

All public functions must have type hints. Use `from __future__ import annotations` for forward references:
```python
from __future__ import annotations
from typing import Optional, Sequence

def process_frame(
    frame: SensorFrame,
    config: ProcessingConfig,
    timeout_ms: Optional[int] = None,
) -> ProcessedResult:
    """Process a single sensor frame."""
    ...
```

Use `Optional` instead of `Union[X, None]`. Use built-in types for generics (`list`, `dict`, `tuple`) in Python 3.9+.

### 3. Imports

Order imports as follows, separated by blank lines:
```python
# 1. Standard library
import os
import sys
from pathlib import Path

# 2. Third-party packages
import numpy as np
import pandas as pd

# 3. Internal modules
from breview.models import Issue
from breview.config import load_config
```

No wildcard imports (`from module import *`). No circular imports.

### 4. Error Handling

**Never use bare `except`**. Always catch specific exceptions:
```python
# Good
try:
    result = parse_sensor_data(raw_bytes)
except (ValueError, struct.error) as e:
    logger.error(f"Failed to parse sensor data: {e}")
    raise DataParsingError(f"Invalid sensor data format: {e}") from e

# Bad
try:
    result = parse_sensor_data(raw_bytes)
except:
    pass
```

**Always log before re-raising** in BRT scripts. Use structured logging:
```python
import logging

logger = logging.getLogger(__name__)

try:
    config = load_simulation_config(path)
except FileNotFoundError:
    logger.error("Simulation config not found", extra={"path": str(path)})
    raise
```

**Use custom exceptions** for domain-specific errors:
```python
class BRTError(Exception):
    """Base exception for BRT errors."""
    pass

class SensorDataError(BRTError):
    """Error in sensor data processing."""
    pass

class SimulationConfigError(BRTError):
    """Error in simulation configuration."""
    pass
```

### 5. Functions and Methods

**Keep functions focused**. If a function does more than one thing, split it:
```python
# Good
def validate_frame(frame: SensorFrame) -> bool:
    return _check_timestamp(frame) and _check_dimensions(frame)

def process_frame(frame: SensorFrame) -> ProcessedResult:
    if not validate_frame(frame):
        raise SensorDataError("Invalid frame")
    return _transform(frame)

# Bad
def handle_frame(frame: SensorFrame) -> ProcessedResult:
    # 50 lines doing validation, transformation, logging, saving...
```

**Default parameter values** must be immutable:
```python
# Good
def create_pipeline(config: Config, sensors: list[str] | None = None) -> Pipeline:
    sensors = sensors or []
    ...

# Bad
def create_pipeline(config: Config, sensors: list[str] = []) -> Pipeline:
    ...
```

### 6. Classes

**Use `__slots__`** for data-heavy classes to reduce memory:
```python
class SensorReading:
    __slots__ = ("timestamp", "sensor_id", "data", "quality")

    def __init__(self, timestamp: float, sensor_id: str, data: bytes, quality: float):
        self.timestamp = timestamp
        self.sensor_id = sensor_id
        self.data = data
        self.quality = quality
```

**Prefer composition over inheritance**. Use inheritance only for genuine "is-a" relationships.

### 7. Comments and Docstrings

**Public APIs** must have docstrings (Google style):
```python
def calibrate_sensor(
    raw_data: np.ndarray,
    calibration_matrix: np.ndarray,
    offset: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Calibrate raw sensor data using a calibration matrix.

    Args:
        raw_data: Raw sensor readings, shape (N, 3).
        calibration_matrix: 3x3 calibration matrix.
        offset: Optional offset vector, shape (3,).

    Returns:
        Calibrated sensor data with same shape as raw_data.

    Raises:
        ValueError: If matrix dimensions are incompatible.
    """
```

**Inline comments** explain "why", not "what":
```python
# Good
# Use double buffering to avoid race condition with sensor thread
buffer = DoubleBuffer(capacity=frame_count)

# Bad
# Create a double buffer
buffer = DoubleBuffer(capacity=frame_count)
```

### 8. Testing

**Every module** must have corresponding tests in `tests/`:
```
breview/
  diff/
    parser.py
tests/
  test_diff_parser.py
```

**Test names** describe the behavior:
```python
# Good
def test_parser_handles_empty_diff():
    ...

def test_parser_detects_binary_files():
    ...

# Bad
def test_parser():
    ...

def test_diff():
    ...
```

### 9. Performance

**Avoid repeated computation** in loops:
```python
# Good
len_data = len(data)
for i in range(len_data):
    process(data[i], len_data)

# Bad
for i in range(len(data)):
    process(data[i], len(data))
```

**Use generators** for large data streams:
```python
def read_sensor_stream(path: Path) -> Iterator[SensorFrame]:
    """Yield sensor frames one at a time instead of loading all into memory."""
    with open(path, "rb") as f:
        while frame := _read_next_frame(f):
            yield frame
```

---

## C++ Coding Standards

### 1. Naming Conventions

**Variables and functions** use `snake_case`:
```cpp
// Good
int processing_count = 0;
double calculate_latency(const SensorData& data, double threshold_ms);

// Bad
int ProcessingCount = 0;
double CalculateLatency(const SensorData& data, double threshold_ms);
```

**Classes and structs** use `PascalCase`:
```cpp
class SensorDataProcessor { ... };
struct FrameMetadata { ... };
```

**Constants and macros** use `UPPER_SNAKE_CASE`:
```cpp
constexpr int kMaxRetryCount = 3;  // Google style for constexpr
#define MAX_BUFFER_SIZE 1024        // Macros
```

**Member variables** use `snake_case_` with trailing underscore (or `m_` prefix if team convention):
```cpp
class Pipeline {
    int retry_count_;
    std::string config_path_;
};
```

### 2. Memory Management

**Always use RAII**. Never use raw `new`/`delete` in application code:
```cpp
// Good
auto buffer = std::make_unique<float[]>(size);
auto processor = std::make_shared<SensorProcessor>(config);

// Bad
float* buffer = new float[size];
// ... forgot to delete[] buffer
```

**Use smart pointers** by default:
- `std::unique_ptr` for exclusive ownership
- `std::shared_ptr` for shared ownership (use sparingly)
- Never use `std::auto_ptr`

### 3. Error Handling

**Use exceptions** for exceptional cases, not for normal flow:
```cpp
// Good
if (!file.is_open()) {
    throw SimulationConfigError("Cannot open config: " + path);
}

// Bad - using error codes for everything
int result = open_file(path);
if (result != 0) {
    return result;  // Error code propagation is error-prone
}
```

**Use `noexcept`** for functions that should never throw (move constructors, destructors):
```cpp
class FrameBuffer {
public:
    FrameBuffer(FrameBuffer&& other) noexcept = default;
    ~FrameBuffer() noexcept = default;
};
```

### 4. Header Files

**Always use include guards**:
```cpp
#pragma once  // Preferred over #ifndef guard

#include <memory>
#include <string>
#include <vector>

namespace brt {
namespace sensor {

class DataProcessor { ... };

}  // namespace sensor
}  // namespace brt
```

**Forward declare** when possible to reduce compile times:
```cpp
// In header - forward declare
class Config;
class Logger;

class Pipeline {
    Config* config_;  // OK - pointer, no need for full definition
    std::unique_ptr<Logger> logger_;
};
```

### 5. Modern C++ Features

**Use auto** where it improves readability:
```cpp
// Good - type is obvious from context
auto result = std::make_unique<ProcessResult>();
for (const auto& frame : frames) { ... }

// Bad - type is not obvious
auto x = GetData();  // What does this return?
```

**Use range-based for loops**:
```cpp
// Good
for (const auto& sensor : sensors) {
    process(sensor);
}

// Bad
for (size_t i = 0; i < sensors.size(); ++i) {
    process(sensors[i]);
}
```

**Use structured bindings** (C++17):
```cpp
auto [success, result] = try_process(frame);
if (!success) {
    log_error(result.error_message);
}
```

### 6. Performance

**Pass large objects by const reference**:
```cpp
// Good
void process(const std::vector<SensorFrame>& frames);

// Bad - unnecessary copy
void process(std::vector<SensorFrame> frames);
```

**Reserve vector capacity** when size is known:
```cpp
std::vector<Result> results;
results.reserve(expected_count);
```

**Avoid unnecessary allocations** in hot paths:
```cpp
// Good - reuse buffer
class Processor {
    std::vector<float> work_buffer_;  // Reuse across calls
public:
    void process(const SensorFrame& frame) {
        work_buffer_.resize(frame.size());
        // ... use work_buffer_
    }
};
```

---

## BRT-Specific Standards

### 1. Sensor Data Handling

**Always validate sensor data** before processing:
```python
def process_lidar_frame(frame: LidarFrame) -> PointCloud:
    if frame.num_points == 0:
        logger.warning("Empty lidar frame", extra={"frame_id": frame.id})
        return PointCloud.empty()
    if not _validate_point_cloud(frame.points):
        raise SensorDataError(f"Invalid point cloud in frame {frame.id}")
    return _transform_to_point_cloud(frame)
```

**Timestamp validation** is mandatory:
```python
def validate_timestamp(timestamp_ns: int, reference_ns: int, max_drift_ms: float = 100.0) -> bool:
    """Validate that timestamp is within acceptable drift from reference."""
    drift_ms = abs(timestamp_ns - reference_ns) / 1e6
    if drift_ms > max_drift_ms:
        logger.warning(f"Timestamp drift {drift_ms:.1f}ms exceeds {max_drift_ms}ms")
        return False
    return True
```

### 2. Simulation Configuration

**Simulation configs must be version-controlled** and validated:
```python
class SimulationConfig:
    """Simulation configuration with validation."""

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of errors."""
        errors = []
        if self.scenario_duration_s <= 0:
            errors.append("scenario_duration_s must be positive")
        if self.sensor_frequency_hz > 100:
            errors.append("sensor_frequency_hz exceeds maximum (100 Hz)")
        if not self.map_path.exists():
            errors.append(f"map file not found: {self.map_path}")
        return errors
```

**Never hardcode paths** in simulation configs:
```python
# Good
map_path = Path(os.environ["BRT_MAP_DIR"]) / config.map_name

# Bad
map_path = Path("/data/maps/san_francisco.bin")
```

### 3. Safety-Critical Code

**Safety-critical functions** must have explicit error handling and logging:
```python
def compute_vehicle_trajectory(
    current_state: VehicleState,
    sensor_readings: list[SensorReading],
    safety_margin_m: float = 2.0,
) -> Trajectory:
    """Compute vehicle trajectory with safety margin.

    This function is safety-critical. Any failure must be logged
    and a safe fallback trajectory must be returned.
    """
    try:
        trajectory = _plan_trajectory(current_state, sensor_readings)
        trajectory = _apply_safety_margin(trajectory, safety_margin_m)
        return trajectory
    except Exception as e:
        logger.critical(
            "Trajectory computation failed, returning stop trajectory",
            extra={"error": str(e), "vehicle_state": current_state},
        )
        return Trajectory.stop(current_state)
```

**Use assertions for invariants** in development, but never rely on them in production:
```python
def process_critical_data(data: CriticalData) -> Result:
    assert data.is_valid(), "Data must be validated before processing"  # Dev check
    if not data.is_valid():  # Production check
        raise SafetyError("Invalid critical data")
    ...
```

### 4. Logging Standards

**Use structured logging** with consistent fields:
```python
logger.info(
    "Frame processed successfully",
    extra={
        "frame_id": frame.id,
        "sensor_type": frame.sensor_type,
        "processing_time_ms": duration_ms,
        "point_count": frame.num_points,
    },
)
```

**Log levels**:
- `DEBUG`: Detailed diagnostic info (disabled in production)
- `INFO`: Normal operations (frame processed, config loaded)
- `WARNING`: Unexpected but recoverable (timestamp drift, retry)
- `ERROR`: Operation failed (sensor read failed, parse error)
- `CRITICAL`: Safety-critical failure (trajectory computation failed)

---

## Code Review Severity Guide

When reviewing code, apply the following severity levels:

| Severity | Criteria | Examples |
|----------|----------|----------|
| CRITICAL | Security vulnerability, crash risk, data corruption, safety issue | Hardcoded credentials, null dereference, missing safety validation |
| MAJOR | Logic error, performance problem, anti-pattern | Wrong algorithm, memory leak, bare except, missing type hints |
| MINOR | Style violation, minor improvement | Wrong naming convention, missing docstring, unused import |
| INFO | Suggestion, best practice | Could use generator, consider caching, alternative approach |
