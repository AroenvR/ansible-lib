# frozen_string_literal: true

# aslib.infra (role gitlab): applies the application settings, those GitLab keeps
# in its database rather than in gitlab.rb. Reads them as JSON from
# ASLIB_GITLAB_SETTINGS, changes only those that differ, and prints one JSON line:
# the names of the settings it changed, and whether root has a password. The
# deploy runs it in the container:
#   gitlab-rails runner /etc/gitlab-aslib/application_settings.rb
# An unknown setting name stops it with an error, changing nothing.
require 'json'

wanted = JSON.parse(ENV.fetch('ASLIB_GITLAB_SETTINGS'))
setting = ApplicationSetting.current_without_cache || ApplicationSetting.create_from_defaults
setting.assign_attributes(wanted)
changed = setting.changed
setting.save! if setting.changed?

root = User.find_by(username: 'root')
puts JSON.generate('changed' => changed, 'root_password' => root.present? && root.encrypted_password.present?)
