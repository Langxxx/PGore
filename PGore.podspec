Pod::Spec.new do |s|

  s.name         = "PGore"
  s.version      = "0.0.1"
  s.summary      = "PGore"

  s.homepage     = "https://github.com/langxxx/PGore"
  s.license      = { :type => 'MIT' }
  s.author       = { "langxxx" => "lang.w.xxx@gmail.com" }

  s.source       = { :http => "https://github.com/Langxxx/PGore/releases/download/untagged-30e326a42cbd8118cab2/PGore.zip" }

  s.requires_arc = true
  s.ios.deployment_target     = "9.0"
  s.preserve_path = ["bin/pgore", "tmpl/*"]
end