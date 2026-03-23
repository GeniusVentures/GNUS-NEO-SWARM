# CHECKPOINT

## Date
2026-03-22

## What was decided
- Do this work step-by-step.
- Do not one-shot the full Flutter + FFI + chat stack.
- Stub the FFI into an OpenAI v1 chat call system for now.
- Keep the changes small enough to check in soon.

## What is true right now
- Native repo exposes the original tiny static C++ library plus a new shared FFI target.
- A minimal OpenAI v1-style chat ABI now exists here for stubbed chat completion responses.
- `flutter_app/` and `flutter_slm_bridge/` now exist in this repo as staged scaffolds.
- `flutter_app/lib/main.dart` is still the generated template app, and `flutter_slm_bridge/` still exposes the generated `sum` FFI surface.

## Completed in this checkpoint
- Created `AgentDocs/PLAN.md`
- Created `AgentDocs/CHECKPOINT.md`
- Added `src/genius_slm_chat_c.h`
- Added `src/genius_slm_chat_c.cpp`
- Updated `CMakeLists.txt` to build `Genius-MOS-SLM-FFI`
- Staged `flutter_app/` scaffold with `ffi` and `flutter_ai_toolkit` dependencies
- Staged `flutter_slm_bridge/` FFI plugin scaffold, including its generated example app

## Not done yet
- Native build verification is still pending until the required build environment is working.
- `flutter_slm_bridge/` is not yet wired to `GeniusSlmChatCompletionsCreate` / `GeniusSlmStringFree`.
- `flutter_app/` is not yet calling the native chat stub or showing a chat UI.

## Next proposed single step
After the build environment is working, validate the native project build using the README-prescribed flow, then make the smallest possible Flutter/plugin wiring change to call the existing native chat stub.

## Suggested minimal acceptance for next step
- The required build dependencies are available
- `build/OSX/Debug` configures successfully with the README flow
- `ninja` builds the native targets successfully
- `flutter_slm_bridge/` exposes a minimal Dart wrapper for the existing native chat stub
- `flutter_app/` can invoke the stubbed chat path end-to-end with no additional scope added

