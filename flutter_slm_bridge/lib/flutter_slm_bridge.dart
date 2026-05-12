import 'dart:async';
import 'dart:ffi';
import 'dart:io';
import 'dart:isolate';

import 'package:ffi/ffi.dart';

import 'genius_slm_bindings_generated.dart';

const String _libName = 'Genius-MOS-SLM-FFI';

/// The dynamic library containing the GeniusSlm symbols.
final DynamicLibrary _dylib = () {
  if (Platform.isMacOS) {
    // Use absolute path to the pre-built dylib during development.
    // In a production app bundle this would be embedded via the podspec.
    const dylib =
        '/Volumes/Work/Gnus_ai/genius-llm-v1/GNUS-NEO-SWARM/build/OSX/Release/lib$_libName.dylib';
    return DynamicLibrary.open(dylib);
  }
  if (Platform.isIOS) {
    return DynamicLibrary.open('$_libName.framework/$_libName');
  }
  if (Platform.isAndroid || Platform.isLinux) {
    return DynamicLibrary.open('lib$_libName.so');
  }
  if (Platform.isWindows) {
    return DynamicLibrary.open('$_libName.dll');
  }
  throw UnsupportedError('Unsupported platform: ${Platform.operatingSystem}');
}();

/// The generated FFI bindings.
final GeniusSlmBindings _bindings = GeniusSlmBindings(_dylib);

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Initialises the Genius SLM engine.
///
/// Call this once at app startup before sending any chat messages.
/// Pass [modelPath] to use a real MNN model, or leave null for stub mode
/// (useful for UI development without a model file).
///
/// Returns 0 on success, -1 on failure.
int geniusSlmInit({String? modelPath, String? knowledgePath}) {
  final modelPtr = modelPath != null
      ? modelPath.toNativeUtf8().cast<Char>()
      : nullptr.cast<Char>();
  final knowledgePtr = knowledgePath != null
      ? knowledgePath.toNativeUtf8().cast<Char>()
      : nullptr.cast<Char>();

  final result = _bindings.GeniusSlmInit(modelPtr, knowledgePtr);

  if (modelPath != null) malloc.free(modelPtr);
  if (knowledgePath != null) malloc.free(knowledgePtr);

  return result;
}

/// Sends a chat message and returns the assistant's reply.
///
/// [requestJson] must be an OpenAI v1 chat/completions request JSON string:
/// ```json
/// {"messages": [{"role": "user", "content": "What is 2+2?"}]}
/// ```
///
/// Returns the full OpenAI v1 response JSON string.
/// Runs on the calling isolate — use [chatCompletionsCreateAsync] for
/// long-running inference to avoid blocking the UI thread.
String chatCompletionsCreate(String requestJson) {
  final ptr = requestJson.toNativeUtf8().cast<Char>();
  final result = _bindings.GeniusSlmChatCompletionsCreate(ptr);
  malloc.free(ptr);

  if (result == nullptr) {
    return '{"error":{"message":"null response from native","type":"ffi_error"}}';
  }

  final response = result.cast<Utf8>().toDartString();
  _bindings.GeniusSlmStringFree(result);
  return response;
}

/// Sends a chat message on a helper isolate and returns the assistant's reply.
///
/// Use this for real model inference to avoid dropping frames in Flutter.
/// The stub mode response is fast enough for the main isolate, but once a
/// real model is loaded this should be the default call path.
Future<String> chatCompletionsCreateAsync(String requestJson) async {
  return await Isolate.run(() => chatCompletionsCreate(requestJson));
}

/// Convenience helper: extracts the assistant's text content from a
/// raw OpenAI v1 response JSON string returned by [chatCompletionsCreate].
///
/// Returns the content string, or an error message if parsing fails.
String extractContent(String responseJson) {
  try {
    // Simple extraction without importing dart:convert at this layer.
    // Looks for "content":"..." in the choices array.
    const contentKey = '"content":"';
    final idx = responseJson.indexOf(contentKey);
    if (idx == -1) {
      // Check for error response
      const errorKey = '"message":"';
      final errIdx = responseJson.indexOf(errorKey);
      if (errIdx != -1) {
        final start = errIdx + errorKey.length;
        final end = responseJson.indexOf('"', start);
        if (end != -1) return '[Error] ${responseJson.substring(start, end)}';
      }
      return responseJson;
    }
    final start = idx + contentKey.length;
    // Find closing quote, skipping escaped quotes
    var end = start;
    while (end < responseJson.length) {
      if (responseJson[end] == '"' &&
          (end == 0 || responseJson[end - 1] != '\\')) {
        break;
      }
      end++;
    }
    return responseJson
        .substring(start, end)
        .replaceAll(r'\"', '"')
        .replaceAll(r'\n', '\n')
        .replaceAll(r'\t', '\t')
        .replaceAll(r'\\', '\\');
  } catch (_) {
    return responseJson;
  }
}
