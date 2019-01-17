Pod::Spec.new do |s|

  s.name         = "PGore"
  s.version      = "0.3.0"
  s.summary      = "PGore"

  s.homepage     = "https://github.com/langxxx/PGore"
  s.license      = { :type => 'MIT' }
  s.author       = { "langxxx" => "lang.w.xxx@gmail.com" }

  s.source       = { :http => "https://github.com/Langxxx/PGore/releases/download/#{s.version}/PGore.zip" }

  s.requires_arc = true
  s.ios.deployment_target     = "9.0"
  s.preserve_paths = "pgore", "tmpl/*"
end