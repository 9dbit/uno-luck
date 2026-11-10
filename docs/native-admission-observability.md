# Native admission observability

UNO retains the existing default **40-token** AnyIO worker limiter while the
native dispatch delay is investigated. This change does not alter startup
configuration or the separate callback pool. Read the serving loop's actual
`anyio_thread_limiter.total_tokens` in `/health` when collecting an interval;
an environment string alone is not an observation of the running limiter.

## Boundaries and compatibility

The existing `dispatch_to_worker` phase remains unchanged. Three optional fixed
phase labels are added to `native_phases.operations.<operation>.phases`, with
the same schema 1, microsecond units, cumulative aggregate fields and fixed
per-operation phase-sum histogram as existing phases:

| Phase | Start | End | Interpretation |
|---|---|---|---|
| `dispatch_to_admission` | Existing dispatch timestamp | Immediately before delegating the default limiter acquisition | Wrapper setup and the backend's pre-acquisition checkpoint/dispatch overhead. |
| `admission_wait` | Immediately before delegated acquisition | Successful acquisition return | Observed acquire wall time, including the limiter's own checkpoint, time awaiting capacity and event-loop wake-up. It does not isolate pure queue time. |
| `admission_to_worker` | Successful acquisition return | Existing `_run_worker` entry timestamp | Work between admission and observed worker entry: telemetry recording, backend dispatch, worker creation or reuse and thread scheduling. It does not isolate the OS scheduler. |

Each phase exports `operations`, `invocations`, `total_us`,
`max_operation_us`, `max_invocation_us`, and `buckets`. Successful, fully
observed offloads have one invocation in each new phase. Their durations
partition `dispatch_to_worker`: because each span independently floors
nanoseconds to microseconds, the full duration minus the sum of the three is
between zero and two microseconds per offload. No request samples, borrower
identities, task names or new variable labels are retained. Storage is fixed:
the existing bounded registry gains three phase cells per operation and one
admission timestamp per capture.

The admission phases describe successful acquisition. A request cancelled or
failed before acquiring has no successful admission samples. A worker-start
failure after acquisition can have `dispatch_to_admission` and
`admission_wait`, without `admission_to_worker` or `dispatch_to_worker`.
Background recovery does not use the request offload and has no admission
phases. Aborted/error counts and the phase invocation counts must be considered
when comparing intervals; absent phases must not be presented as measured zero.

## Execution and failure behavior

The wrapper resolves the serving loop's existing
`anyio.to_thread.current_default_thread_limiter()` and passes a per-call
observing delegate to `anyio.to_thread.run_sync`. The delegate forwards the
backend's acquisition and release to that **same limiter**, exactly once. It
does not acquire an outer token and then call a second offload, create another
pool, set `total_tokens`, or replace global limiter/backend methods.

The asyncio backend uses the delegate's async context manager. The on-behalf
acquire/release interface is forwarded for AnyIO's alternative backend
protocol. Instrumentation adds no asynchronous cancellation checkpoint after
successful acquisition. AnyIO keeps responsibility for its default
`abandon_on_cancel=False` behavior, worker lifecycle and token cleanup. Work
waiting for capacity remains cancellable; cancellation through an AnyIO cancel
scope after admission waits for the worker according to the existing backend
behavior. The callable and its positional/keyword arguments are bound using
`functools.partial`, as in the pinned Starlette implementation. Business
arguments named `limiter`, `cancellable` or `abandon_on_cancel` still reach the
original callable; they are not interpreted as offload options. AnyIO still
copies the caller's context into the worker.

Telemetry runs through the existing fail-open helpers. Failure to construct
the delegate or resolve its observational limiter reference falls back to the
original Starlette offload before any worker execution and sets
`telemetry_error`. Failures while recording an admission cannot escape with a
borrowed token. The underlying limiter and worker exceptions still propagate;
no failed offload or business callback is retried by instrumentation. Existing
capture-generation checks and cleanup protect reused slots after cancellation.

## Reading a diagnostic interval

Use closed before/after snapshots with stable source, boot, registry and reset
identities, zero active captures at boundaries, expected operation counts and
no telemetry error, dropped captures or saturation. Subtract cumulative phase
counts, totals and histogram buckets for each operation. Check coverage before
comparing means. A large `admission_wait` establishes time spent inside the
observed acquisition boundary; a large `admission_to_worker` locates delay after
admission. Neither result alone identifies CPU starvation, a resource upgrade,
or a particular event-loop or OS scheduling mechanism.

Do not sum phase percentiles, subtract lifetime maxima, or infer peak occupancy
from the existing `borrowed_tokens`/`tasks_waiting` health snapshots. Those
snapshots observe their sampling instants only. This instrumentation creates
no continuous occupancy sampler and changes no qualification gates.

## Verification and runtime references

`tests/test_native_phase_observability.py` exercises both asyncio and uvloop
when uvloop is installed, including:

- Forty ordinary default-limiter workers, five observed requests queued behind
  them, context isolation, admission delay and the full-span partition.
- A controlled delay after admission which appears in
  `admission_to_worker`.
- Cancellation while queued, after admission before observed worker entry, and
  while the worker runs, including token/capture release.
- Thirty-nine ordinary workers plus the observed call sharing the last default
  token, for both original return and exception paths, keyword argument binding
  and context propagation without worker-to-caller leakage.
- Setup, limiter lookup, recording and clock faults without business retries,
  altered results or token leaks; actual backend worker-start failure before
  the business function can run.

`tests/test_native_observability.py` also exercises the complete public `/health`
response through the actual ASGI serializer. The fixture fills every fixed
phase/counter/histogram cell to the 53-bit ceiling, includes all callback and
runtime counters, finite floating-point exponent notation, 128-character
deployment identities, a 64-character filesystem type, and the public SHA/UUID
fields. The full wire body is 221,437 bytes; conservative re-encoding with
default JSON spacing is 234,612 bytes, leaving 27,532 bytes below the existing
262,144-byte consumer limit. Credential fixture values are absent. This is
synthetic maximum-width data within the public numeric/identity format, not a
workload result. The test remains in the existing native provider workflow,
whose push filter also includes `feat/native-admission-observability-20261110`;
all source-lock, mount, image and regression gates remain enabled.

The local validation environment uses Python 3.12.14, pinned Starlette 1.3.1,
AnyIO 4.16.0 and uvloop 0.23.0. Trio is not a declared project dependency and was
not installed in that environment, so runtime validation covers asyncio and
uvloop. The source-level on-behalf delegation does not claim a Trio deployment
test. AnyIO is transitive; record the resolved dependency/image versions during
deployment rather than assuming a future rebuild has identical dependencies.

The implementation was checked against the installed Starlette
`run_in_threadpool`, AnyIO `to_thread.run_sync` and asyncio backend source. The
public contracts are documented in [AnyIO's thread documentation](https://anyio.readthedocs.io/en/stable/threads.html)
and [AnyIO's API reference](https://anyio.readthedocs.io/en/stable/api.html#anyio.to_thread.run_sync).
