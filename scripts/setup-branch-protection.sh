#!/usr/bin/env bash
set -euo pipefail

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
BRANCH="main"

echo "Configuring branch protection for ${REPO}:${BRANCH}..."

gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" \
  --input - << 'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "lint-and-test (3.9)",
      "lint-and-test (3.11)",
      "type-check",
      "yaml-lint",
      "codespell"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
EOF

echo "Done. Branch protection configured for ${BRANCH}."
