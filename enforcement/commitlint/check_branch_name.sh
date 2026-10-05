#!/bin/sh
# Check one branch name.
# Usage: check_branch_name.sh [name]
# An empty name is not a pull request. That name passes.
# A dependabot/* name passes. Dependabot chooses that name.

set -eu

if [ "$#" -gt 0 ]; then
  name=$1
else
  name=${GITHUB_HEAD_REF:-}
fi

if [ -z "${name}" ]; then
  exit 0
fi

case ${name} in
  dependabot/*)
    exit 0
    ;;
esac

pattern='^(feat|fix|chore|docs|release|hotfix|ai|claude|codex|copilot|cursor|standards)/[a-z0-9]+([.-][a-z0-9]+)*$'

if printf '%s\n' "${name}" | grep -Eq -- "${pattern}"; then
  exit 0
fi

printf 'bad branch name: %s\n' "${name}" >&2
exit 1
