# Reusable Agent Control Plane

A customer-neutral prototype for inspecting, governing, and controlling AI agents across a standardized hosting environment. The included inventory and adapter implementations use synthetic data only.

## Run locally

Requires Node.js 20 or later; there are no external dependencies.

```sh
npm start
```

Open <http://127.0.0.1:4173>. Set `PORT` to use a different port.

Run the core behavior tests with:

```sh
npm test
```

Lifecycle changes are held in memory by the synthetic runtime adapter and reset when the server or page is restarted. This prototype is not an authentication or production deployment system.

## Operator experience

The dashboard shows a synthetic agent inventory with runtime health, enabled/disabled state, hosting environment, and policy metadata. Operators can enable or disable agents. Enabling an agent is rejected when its policy requires approval and that approval has not been granted; the sample includes one such agent to demonstrate the governance guard.

## Architecture

```text
Browser dashboard
  └── AgentControlPlane
       ├── RuntimeAdapter     health, enabled state, lifecycle operations
       └── HostingAdapter     environment metadata
```

The browser UI depends on the `AgentControlPlane` interface in `src/control-plane.js`, not on a specific runtime or hosting vendor. The synthetic implementations in `src/demo-adapters.js` provide the runnable example.

### Extension interfaces

Implement a runtime adapter with:

- `getStatus(agentId)` → `{ enabled, health, lastSeen }`
- `setEnabled(agentId, enabled)` → updated status, or throw if the runtime cannot perform the operation

Implement a hosting adapter with:

- `getEnvironment(agentId)` → `{ name, type, region }`

Both methods are synchronous in this prototype; a production integration can expose asynchronous operations by making the control-plane methods asynchronous and updating the UI accordingly. The agent catalog uses the shape in `src/sample-data.js`; policy metadata is evaluated by the control plane before enabling. A production system should additionally authenticate operators, authorize changes, persist audit records, and validate adapter data at its trust boundary.

## Project structure

- `server.mjs` — dependency-free local static server
- `public/` — dashboard markup, styles, and browser entry point
- `src/control-plane.js` — reusable lifecycle and policy logic
- `src/demo-adapters.js` — synthetic runtime and hosting adapters
- `src/sample-data.js` — sanitized, synthetic agent catalog
- `test/` — core behavior tests using Node's built-in test runner
