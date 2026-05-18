# PLAN

## Planning assumptions
- At least two engineers will work in parallel.
- Work should be tracked as GitHub issues, with each task below suitable for one issue unless it is explicitly marked as an epic.
- The near-term product goal is a small, working Flutter chat path backed by the native stubbed OpenAI v1-style FFI ABI for GNUS-NEO-SWARM, the Expert Language Model and application code for the parent GeniusCognitiveSystem.
- Keep the native ABI stable while the implementation evolves from stubbed responses to real local ELM behavior.
- Do not expand scope into the full swarm runtime until the app, bridge, build, and test loops are reliable.

## Current repo state
- Root `CMakeLists.txt` builds `GNUS-NEO-SWARM` as a static library from `src/elm_base.cpp`.
- A shared FFI target, `GNUS-NEO-SWARM-FFI`, exists for the chat ABI.
- `src/genius_elm_chat_c.h` and `src/genius_elm_chat_c.cpp` expose a minimal OpenAI v1-style chat completion surface:
  - `GeniusElmChatHealth()`
  - `GeniusElmChatCompletionsCreate(const char * requestJson)`
  - `GeniusElmStringFree(char * value)`
- `flutter_app/` exists and includes `ffi` and `flutter_ai_toolkit`, but `lib/main.dart` is still the generated template app.
- `flutter_slm_bridge/` exists, but its generated Dart and native files still expose the template `sum` API instead of the `GeniusElm...` chat ABI.
- Native build verification is still pending until the required local build environment is working.
- The heavier `build/<Platform>/...` CMake path exists, but the current tree does not yet match the larger structure described in `README.md`.

## Team lanes

### Engineer A: Native and Build
- Owns the C/C++ ABI, CMake targets, platform build packaging, native tests, and build documentation.
- Keeps the FFI boundary small and stable.
- Coordinates ABI changes with Engineer B before merging.

### Engineer B: Flutter and Product Integration
- Owns the Flutter app, Flutter plugin bridge, Dart API shape, UI flow, and Flutter tests.
- Keeps the UI focused on proving the native chat path end-to-end.
- Coordinates bridge changes with Engineer A before merging.

### Shared
- Both engineers review API-boundary issues.
- Both engineers keep tasks small enough to merge independently.
- Each GitHub issue should include acceptance criteria and a verification note before closing.

## Sprint 0: Repo Stabilization and Issue Setup

Goal: Convert the checkpoint into a trackable backlog and confirm the repo can be worked on safely by two engineers.

### Task 0.1: Create GitHub issue labels and milestones
Owner: Project lead

Description:
Create GitHub labels for `native`, `flutter`, `ffi`, `build`, `test`, `docs`, `blocked`, and `good-first-pass`. Create milestones matching the sprint names in this plan.

Acceptance criteria:
- Labels exist in GitHub.
- Sprint milestones exist in GitHub.
- Each task from Sprint 1 is filed as an issue and assigned to a lane.

### Task 0.2: Confirm source-of-truth docs
Owner: Engineer A

Description:
Review `README.md`, `CLAUDE.md`, `AgentDocs/CHECKPOINT.md`, and this plan. Identify any contradictions that would block the first implementation sprint.

Acceptance criteria:
- Any contradictions are captured in GitHub issues.
- `AgentDocs/CHECKPOINT.md` remains a historical checkpoint.
- `AgentDocs/PLAN.md` remains the active execution plan.

### Task 0.3: Confirm local toolchain requirements
Owner: Engineer A

Description:
Document the exact local tools required for the native and Flutter loops, including CMake, Ninja, compiler, Flutter SDK, Dart SDK, CocoaPods if needed, and platform-specific requirements.

Acceptance criteria:
- Toolchain requirements are documented in the repo.
- Missing toolchain items are filed as blockers.
- The first native and Flutter validation commands are listed.

## Sprint 1: End-to-End Stub Chat

Goal: Make the smallest complete path from Flutter UI to Dart bridge to native stub and back.

### Task 1.1: Validate native CMake build
Owner: Engineer A

Description:
Run the README-prescribed native build flow, starting with the macOS path if working on macOS. Confirm that `GNUS-NEO-SWARM` and `GNUS-NEO-SWARM-FFI` configure and build.

Acceptance criteria:
- CMake configure succeeds.
- Native build succeeds.
- Any required local setup is documented.
- Any build failures are captured with exact commands and error output.

### Task 1.2: Add native ABI smoke test
Owner: Engineer A

Description:
Add a small native executable or test target that calls `GeniusElmChatHealth`, `GeniusElmChatCompletionsCreate`, and `GeniusElmStringFree`.

Acceptance criteria:
- Test proves the health function returns a usable status.
- Test proves chat completion returns valid JSON.
- Test frees returned strings through `GeniusElmStringFree`.
- Test is runnable from the documented native build flow.

### Task 1.3: Replace generated bridge API with chat API
Owner: Engineer B

Description:
Update `flutter_slm_bridge/` so its public Dart API wraps the native chat ABI instead of the generated `sum` example.

Acceptance criteria:
- Public Dart API exposes a simple chat completion method that accepts request JSON or a typed request object.
- Bridge loads the expected native library on the initial supported desktop platform.
- Generated or manual bindings include `GeniusElmChatHealth`, `GeniusElmChatCompletionsCreate`, and `GeniusElmStringFree`.
- Template `sum` API is removed or isolated from the public API.

### Task 1.4: Wire Flutter app to bridge
Owner: Engineer B

Description:
Replace the generated Flutter counter app with a minimal chat screen that sends a user message through `flutter_slm_bridge` and renders the stubbed response.

Acceptance criteria:
- App has a message input, send action, and visible response area.
- Sending a message calls the native stub path through the bridge.
- Errors from the bridge are shown in a minimal user-visible state.
- No real networking is added.

### Task 1.5: Add Flutter smoke test
Owner: Engineer B

Description:
Add focused Flutter tests for the chat screen and bridge-facing app logic. Mock the bridge where needed so tests do not depend on native dynamic library loading.

Acceptance criteria:
- Test covers entering a prompt and rendering a response.
- Test covers bridge error display.
- `flutter test` passes for the app package.

## Sprint 2: API Contract and Packaging

Goal: Make the FFI contract explicit and make native artifacts predictable for Flutter development.

### Task 2.1: Define chat request and response contract
Owner: Engineer A

Description:
Document the supported subset of the OpenAI v1 chat completions request and response JSON. Include required fields, ignored fields, error response shape, and versioning expectations.

Acceptance criteria:
- Contract is documented in `AgentDocs/` or the bridge package README.
- Stub response matches the documented contract.
- Unsupported input behavior is explicit.

### Task 2.2: Harden native JSON handling
Owner: Engineer A

Description:
Validate null, empty, malformed, and oversized request inputs at the native boundary. Return structured JSON errors instead of crashing or returning ambiguous data.

Acceptance criteria:
- Native function handles null input.
- Native function handles malformed JSON.
- Native function returns valid JSON for error cases.
- Smoke tests cover success and error paths.

### Task 2.3: Standardize dynamic library loading
Owner: Engineer B

Description:
Make `flutter_slm_bridge` load the correct native library consistently for the first supported platform, with a clear extension path for macOS, Linux, Windows, iOS, and Android.

Acceptance criteria:
- Library name and lookup behavior are documented.
- Development build instructions explain where the dynamic library must be placed.
- Bridge errors clearly identify missing library failures.

### Task 2.4: Package bridge for local app consumption
Owner: Engineer B

Description:
Connect `flutter_app` to `flutter_slm_bridge` as a local dependency and remove unused generated template code from both packages where it conflicts with the chat path.

Acceptance criteria:
- `flutter_app` depends on the local bridge package.
- App compiles against the bridge public API.
- Unused generated example API is removed from the main product path.

## Sprint 3: Product MVP Chat Experience

Goal: Turn the technical stub path into a usable MVP shell that can survive real model integration later.

### Task 3.1: Build typed Dart chat models
Owner: Engineer B

Description:
Add typed Dart request and response models for the supported chat contract. Keep raw JSON escape hatches for debugging.

Acceptance criteria:
- Dart models serialize to the native request contract.
- Dart models parse native success responses.
- Dart models parse native error responses.
- Unit tests cover serialization and parsing.

### Task 3.2: Improve chat UI states
Owner: Engineer B

Description:
Add basic conversation state handling: pending send, empty state, success response, error response, and retry for the last message.

Acceptance criteria:
- Send action cannot dispatch duplicate pending requests.
- Errors do not erase the user's prompt.
- Retry reuses the last failed prompt.
- UI remains simple and focused on the chat workflow.

### Task 3.3: Add native response metadata
Owner: Engineer A

Description:
Extend the stubbed native response with stable metadata that future model routing can populate, such as model id, created timestamp, finish reason, and token usage placeholders.

Acceptance criteria:
- Metadata follows the documented response contract.
- Existing bridge parsing still works.
- Native tests assert metadata fields exist.

### Task 3.4: Document development runbook
Owner: Shared

Description:
Create a concise runbook for building native code, placing or linking the dynamic library, running the Flutter app, and running tests.

Acceptance criteria:
- New engineer can follow the runbook from a clean checkout.
- Runbook includes troubleshooting for missing native library and missing toolchain.
- Runbook lists known unsupported platforms.

## Sprint 4: Real ELM Integration Preparation

Goal: Prepare the stubbed path for a real local ELM backend without disrupting the Flutter app.

### Task 4.1: Define backend interface behind the C ABI
Owner: Engineer A

Description:
Introduce an internal C++ interface behind `GeniusElmChatCompletionsCreate` so the ABI remains stable while the backend changes from stubbed response to real model execution.

Acceptance criteria:
- Public C ABI does not change.
- Stub backend implements the internal interface.
- Native tests still pass.
- Interface has clear ownership for request, response, and error strings.

### Task 4.2: Identify first local model backend
Owner: Engineer A

Description:
Evaluate the repo docs and existing code to choose the first local model backend path. Capture required dependencies, model asset expectations, and platform constraints.

Acceptance criteria:
- Recommendation is documented.
- Dependency and asset requirements are listed.
- Follow-up implementation issues are created.

### Task 4.3: Add capability reporting
Owner: Engineer A

Description:
Extend the native health or metadata API to report available backend capabilities without requiring the Flutter app to guess.

Acceptance criteria:
- Capability response is valid JSON.
- Flutter bridge can call the capability path.
- App can display or log capability data for debugging.

### Task 4.4: Add integration-test strategy
Owner: Shared

Description:
Define which tests remain mocked, which tests require the native library, and which tests require model assets once real ELM execution begins.

Acceptance criteria:
- Test tiers are documented.
- CI expectations are described.
- Large model assets are not required for normal unit tests.

## Sprint 5: Swarm Runtime Discovery

Goal: Scope the first real swarm-oriented work after the single-agent chat path is stable.

### Task 5.1: Inventory swarm-related docs and code
Owner: Engineer A

Description:
Review `docs/`, `gnus-poc/`, and any existing swarm protocol documentation. Identify what can be reused and what is only exploratory.

Acceptance criteria:
- Inventory document lists relevant docs and code paths.
- Reusable pieces are separated from research notes.
- Unknowns are captured as GitHub issues.

### Task 5.2: Define MVP swarm behavior
Owner: Shared

Description:
Define the smallest swarm behavior that should appear after single-agent local chat works. Keep this concrete enough to implement and test.

Acceptance criteria:
- MVP behavior has a clear user-visible outcome.
- Required native/backend changes are listed.
- Required Flutter UI changes are listed.
- Non-goals are explicit.

### Task 5.3: Create swarm implementation backlog
Owner: Project lead

Description:
Convert the MVP swarm behavior into GitHub issues, grouped by native runtime, bridge contract, Flutter UI, testing, and documentation.

Acceptance criteria:
- Backlog is split into independently reviewable issues.
- Dependencies between issues are marked.
- First implementation sprint after MVP chat is ready.

## GitHub issue template

Use this shape when pushing tasks to GitHub issues:

```markdown
## Description
What needs to change and why.

## Owner lane
Native and Build / Flutter and Product Integration / Shared

## Dependencies
List prerequisite issues or "None".

## Acceptance criteria
- Concrete, testable result
- Concrete, testable result
- Concrete, testable result

## Verification
Commands to run or manual checks to perform.

## Notes
Constraints, risks, or implementation hints.
```

## Cross-sprint guardrails
- Keep the public C ABI small and stable.
- Prefer additive internal changes over breaking Flutter-facing contracts.
- Keep stub behavior deterministic until real model execution is intentionally introduced.
- Do not add networking to the stub chat path.
- Do not require large model assets for normal unit tests.
- Document exact commands when a task changes the build or test loop.
- File blockers explicitly instead of hiding them in broad implementation issues.
