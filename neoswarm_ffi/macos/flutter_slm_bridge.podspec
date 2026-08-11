#
# To learn more about a Podspec see http://guides.cocoapods.org/syntax/podspec.html.
# Run `pod lib lint flutter_slm_bridge.podspec` to validate before publishing.
#
Pod::Spec.new do |s|
  s.name             = 'flutter_slm_bridge'
  s.version          = '0.0.1'
  s.summary          = 'Genius SLM FFI bridge for GNUS NEO SWARM.'
  s.description      = 'Flutter FFI plugin that wraps the Genius-MOS-SLM-FFI native library.'
  s.homepage         = 'http://example.com'
  s.license          = { :file => '../LICENSE' }
  s.author           = { 'GNUS AI' => 'ssivakumar@gnus.ai' }

  s.source           = { :path => '.' }
  s.source_files     = 'Classes/**/*'

  # Embed the pre-built dylib so it is copied into the app bundle Frameworks folder.
  # Path is relative to this podspec file (flutter_slm_bridge/macos/).
  s.vendored_libraries = '../../../build/OSX/Release/libGenius-MOS-SLM-FFI.dylib'

  s.dependency 'FlutterMacOS'

  s.platform = :osx, '10.15'
  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
    'EXCLUDED_ARCHS[sdk=iphonesimulator*]' => 'i386',
  }
  s.swift_version = '5.0'
end
