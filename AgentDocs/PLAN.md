# PLAN

## Files examined
- `CLAUDE.md`
- `README.md`
- `CMakeLists.txt`
- `src/slm_base.h`
- `src/slm_base.cpp`
- `build/README.md`
- `build/OSX/CMakeLists.txt`
- `build/Linux/CMakeLists.txt`
- `build/Windows/CMakeLists.txt`
- `build/Android/CMakeLists.txt`
- `build/iOS/CMakeLists.txt`
- `build/CommonBuildParameters.cmake`
- `build/CommonCompilerOptions.cmake`
- `build/cmake/functions.cmake`
- `cmake/CommonBuildParameters.cmake`
- `cmake/CompilationFlags.cmake`
- `build/CompilationFlags.cmake`
- `src/genius_slm_chat_c.h`
- `src/genius_slm_chat_c.cpp`
- `flutter_app/pubspec.yaml`
- `flutter_app/lib/main.dart`
- `flutter_slm_bridge/pubspec.yaml`
- `flutter_slm_bridge/lib/flutter_slm_bridge.dart`
- `flutter_slm_bridge/src/CMakeLists.txt`

## Current repo state
- Root `CMakeLists.txt` builds `Genius-MOS-SLM` as a static library from `src/slm_base.cpp` and `Genius-MOS-SLM-FFI` as a shared target.
- There is now a minimal OpenAI v1-style chat FFI surface in this repo.
- `flutter_app/` now exists in-repo and includes `ffi` and `flutter_ai_toolkit`, but `lib/main.dart` is still the generated template app.
- `flutter_slm_bridge/` now exists in-repo, but its generated Dart and native files still expose the template `sum` API instead of the `GeniusSlm...` chat ABI.
- The heavier `build/<Platform>/...` CMake path exists, but the current checked-in tree does not yet match the larger structure described in `README.md`.

## User-approved direction
- Work incrementally.
- Stub FFI only for now.
- Shape the stub around an OpenAI v1 chat call system.
- Keep changes small so the work can be checked in soon and continued tomorrow.

## Minimal phased plan

### Step 1
Create tracking docs under `AgentDocs/` and stage them in git.

### Step 2
Add a tiny native FFI surface for a stubbed OpenAI v1 chat completion call.
Possible minimal API:
- `GeniusSlmChatHealth()`
- `GeniusSlmChatCompletionsCreate(const char * requestJson)`
- `GeniusSlmStringFree(char * value)`

Notes:
- Return fixed JSON for now.
- Keep implementation local to this repo.
- No GeniusSDK dependency yet.
- No real networking yet.

Status:
- Completed with `src/genius_slm_chat_c.h`
- Completed with `src/genius_slm_chat_c.cpp`
- Completed with shared target `Genius-MOS-SLM-FFI` in `CMakeLists.txt`

### Step 3
Add a minimal Flutter app scaffold in-repo that:
- depends on `ffi`
- depends on `flutter_ai_toolkit`
- calls the native stub through a very small Dart bridge
- provides a basic chat UI backed by the stub provider

Status:
- Scaffolded and staged in `flutter_app/`
- Dependencies added in `flutter_app/pubspec.yaml`
- Still not wired to the native chat stub

### Step 4
Once the required build environment is working, validate the native project build using the README-prescribed `build/OSX/Debug` flow.

### Step 5
Make the smallest possible Flutter-side wiring change so `flutter_slm_bridge/` calls `GeniusSlmChatCompletionsCreate` / `GeniusSlmStringFree`, and `flutter_app/` invokes that bridge instead of the generated template behavior.

## Guardrails
- Minimal changes only.
- No refactor of the existing build architecture unless explicitly approved.
- No attempt to finish the whole system in one step.
- Real chat behavior can be implemented later behind the same stubbed ABI.

## Proposed next step after this checkpoint
After the user gets the build environment working, first validate the native build with the README-prescribed `build/OSX/Debug` flow, then do the smallest possible wiring from `flutter_slm_bridge/` and `flutter_app/` to the existing native chat stub.
