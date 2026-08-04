# Plugin boundary

NexusOS plugins are optional, operator-approved extensions. Plugin code never runs inside the FastAPI process.

## Configuration

Set `PLUGINS_DIR` to an absolute directory mounted or created by the operator. Leave it empty to disable plugin discovery. `PLUGIN_INVOKE_TIMEOUT_SECONDS` bounds each invocation (1–120 seconds; default 20).

The directory should be owned by the NexusOS service account and should not be writable by untrusted users or by plugin processes. Do not mount the Docker socket, host root, secrets directories, or the live SQLite database into a plugin directory.

## Manifest

Each plugin must live in a directory whose name exactly matches `name` and contain `plugin.json`:

```json
{
  "name": "weather",
  "version": "1.0.0",
  "description": "Read-only local weather adapter",
  "entrypoint": "run.py",
  "capabilities": [
    {"method": "current", "description": "Read current conditions", "risk": "read"}
  ]
}
```

Names, entrypoints, methods, versions, and capabilities are bounded and validated. Entrypoints are confined beneath the plugin directory. Capability risks are `read`, `write`, or `dangerous`.

## Invocation contract

The broker sends one JSON line on stdin:

```json
{"method":"current","arguments":{"location":"home"}}
```

The plugin must write one final JSON object to stdout:

```json
{"result":{"temperature_c":21}}
```

or:

```json
{"error":"provider_unavailable"}
```

Stderr is discarded, output is capped, and malformed or oversized responses fail closed. Python entrypoints run with the server's Python interpreter; executable entrypoints are started directly without a shell.

## Confirmation and audit model

- Discovery and plugin lifecycle changes (`rescan`, enable, disable, uninstall) are confirmation-gated host actions.
- The direct API invocation route never executes code and returns `requires_assistant_confirmation`.
- Every capability, including one labeled `read`, is available only through the assistant's `plugins.invoke` tool, which is always confirmation-gated; manifest risk labels describe intent but are not treated as a sandbox.
- Every invocation records bounded status, duration, method, and error code in `plugin_runs` and writes an audit event. Arguments and plugin output are not stored in the audit log.
- Plugin failures never expose raw subprocess output to the client.

## Resource and platform boundaries

On Linux/Raspberry Pi 5, the child receives CPU, address-space, file-descriptor, and core-dump limits plus a wall-time timeout. The broker starts a new process session so timed-out child processes can be terminated as a group. Docker deployments should keep `PLUGINS_DIR` on a dedicated read-only or tightly controlled volume and use the existing non-root container user.

The boundary is not a complete sandbox. A plugin should be treated as trusted operator-installed code. For hostile or third-party code, use a separate VM or container runtime with a stronger policy boundary instead of installing it into `PLUGINS_DIR`.
