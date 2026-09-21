#
# To learn more about a Podspec see http://guides.cocoapods.org/syntax/podspec.html.
# Run `pod lib lint neoswarm_ffi.podspec` to validate before publishing.
#
Pod::Spec.new do |s|
  s.name             = 'neoswarm_ffi'
  s.version          = '0.0.1'
  s.summary          = 'NEO-SWARM FFI bridge for GNUS NEO SWARM.'
  s.description      = 'Flutter FFI plugin that wraps the Genius-MOS-ELM-FFI native library.'
  s.homepage         = 'http://example.com'
  s.license          = { :file => '../LICENSE' }
  s.author           = { 'GNUS AI' => 'ssivakumar@gnus.ai' }

  s.source           = { :path => '.' }
  s.source_files     = 'Classes/**/*'

  # Embed the pre-built dylib so it is copied into the app bundle Frameworks folder.
  # The dylib is staged into macos/lib/ by the consumer's CMake build (post-build
  # copy from the Genius-MOS-ELM-FFI target), so this stays a stable relative
  # path regardless of build config or build directory layout.
  s.vendored_libraries = 'lib/libGenius-MOS-ELM-FFI.dylib'

  s.dependency 'FlutterMacOS'

  s.platform = :osx, '10.15'
  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
    'EXCLUDED_ARCHS[sdk=iphonesimulator*]' => 'i386',
  }
  s.swift_version = '5.0'
end
