# frozen_string_literal: true

source "https://rubygems.org"

# GitHub Pages uses the github-pages gem which includes Jekyll and all supported themes
gem "github-pages", "~> 232", group: :jekyll_plugins
gem "html-proofer", "~> 5.0", group: :test

platforms :windows, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end

gem "wdm", "~> 0.2.0", platforms: [:windows]
