// AUTO-GENERATED FILE — regenerate with:
//   dart run ffigen --config ffigen.yaml
//
// ignore_for_file: always_specify_types
// ignore_for_file: camel_case_types
// ignore_for_file: non_constant_identifier_names

import 'dart:ffi' as ffi;

/// Bindings for `src/genius_slm_chat_c.h`.
class GeniusSlmBindings {
  /// Holds the symbol lookup mechanism.
  final ffi.DynamicLibrary _dylib;

  /// The symbols are looked up in [dynamicLibrary].
  GeniusSlmBindings(ffi.DynamicLibrary dynamicLibrary)
      : _dylib = dynamicLibrary;

  late final _GeniusSlmInitPtr = _dylib.lookupFunction<
      ffi.Int32 Function(ffi.Pointer<ffi.Char>, ffi.Pointer<ffi.Char>),
      int Function(
          ffi.Pointer<ffi.Char>, ffi.Pointer<ffi.Char>)>('GeniusSlmInit');

  /// Initialises the Genius SLM engine.
  ///
  /// Returns 0 on success, -1 on failure.
  int GeniusSlmInit(
    ffi.Pointer<ffi.Char> modelPath,
    ffi.Pointer<ffi.Char> knowledgePath,
  ) {
    return _GeniusSlmInitPtr(modelPath, knowledgePath);
  }

  late final _GeniusSlmChatCompletionsCreatePtr = _dylib.lookupFunction<
      ffi.Pointer<ffi.Char> Function(ffi.Pointer<ffi.Char>),
      ffi.Pointer<ffi.Char> Function(
          ffi.Pointer<ffi.Char>)>('GeniusSlmChatCompletionsCreate');

  /// Creates an OpenAI v1-style chat completion response.
  ///
  /// Returns a heap-allocated UTF-8 JSON string. The caller must release it
  /// with [GeniusSlmStringFree].
  ffi.Pointer<ffi.Char> GeniusSlmChatCompletionsCreate(
    ffi.Pointer<ffi.Char> requestJson,
  ) {
    return _GeniusSlmChatCompletionsCreatePtr(requestJson);
  }

  late final _GeniusSlmStringFreePtr = _dylib.lookupFunction<
      ffi.Void Function(ffi.Pointer<ffi.Char>),
      void Function(ffi.Pointer<ffi.Char>)>('GeniusSlmStringFree');

  /// Releases a string buffer returned by [GeniusSlmChatCompletionsCreate].
  void GeniusSlmStringFree(
    ffi.Pointer<ffi.Char> value,
  ) {
    return _GeniusSlmStringFreePtr(value);
  }
}
