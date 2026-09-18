#!/usr/bin/env bash
set -euo pipefail

# Midas Touch cross-provider synchronizer.
# Fail-closed transport controller.
#
# Default behavior is VERIFY ONLY.
# Set ALLOW_FAST_FORWARD_PUSH=1 only when an explicit caller has approved
# a one-way GitHub -> GitLab update for an unprotected development ref.
#
# Never force-pushes, auto-merges, or resolves divergence.

GITHUB_REMOTE="${GITHUB_REMOTE:-origin}"
GITLAB_REMOTE="${GITLAB_REMOTE:-gitlab}"
REF="${1:-${GITHUB_REF_NAME:-}}"
ALLOW_FAST_FORWARD_PUSH="${ALLOW_FAST_FORWARD_PUSH:-0}"

PROTECTED_REFS=("main" "production")

is_protected() {
  local ref="$1"
  for p in "${PROTECTED_REFS[@]}"; do
    [[ "$ref" == "$p" ]] && return 0
  done
  return 1
}

is_allowed_development_ref() {
  case "$1" in
    feature/*|fix/*|audit/*|chore/*|ops/*|integration/*|sync-test/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

stop() {
  echo "STOP: $*" >&2
  exit 2
}

push_mirror() {
  # Plain git push is intentionally used. Git rejects non-fast-forward updates
  # by default, so a remote race cannot silently rewrite history.
  git push "$GITLAB_REMOTE" "$GITHUB_REMOTE/$REF:refs/heads/$REF" ||     stop "GitLab push was rejected; provider state changed or is protected"
}

echo "Midas Touch sync controller"
echo "GitHub remote: $GITHUB_REMOTE"
echo "GitLab remote:  $GITLAB_REMOTE"
echo "Ref:            ${REF:-<missing>}"
echo "Policy:         equal=no-op; GitHub-ahead=fast-forward only; GitLab-ahead/divergence=STOP"
echo

[[ -n "$REF" ]] || stop "branch/ref name is required"

if is_protected "$REF"; then
  stop "protected ref '$REF' is never mutated by this controller"
fi

is_allowed_development_ref "$REF" || stop "ref '$REF' is outside the approved mirror namespaces"

git rev-parse --git-dir >/dev/null 2>&1 || stop "not running inside a Git repository"

git fetch --prune "$GITHUB_REMOTE" "$REF" || stop "failed to fetch GitHub ref '$REF'"
# Fetch all GitLab refs so a legitimately missing target branch can be detected
# without confusing "branch absent" with "remote unavailable".
git fetch --prune "$GITLAB_REMOTE" || stop "failed to fetch GitLab refs"

GH_REF="refs/remotes/$GITHUB_REMOTE/$REF"
GL_REF="refs/remotes/$GITLAB_REMOTE/$REF"

git rev-parse --verify "$GH_REF" >/dev/null 2>&1 || stop "GitHub ref '$REF' is unavailable after fetch"

GH_SHA="$(git rev-parse "$GH_REF")"

if ! git rev-parse --verify "$GL_REF" >/dev/null 2>&1; then
  echo "GitLab ref '$REF' does not exist."
  echo "GitHub source: $GH_SHA"
  if [[ "$ALLOW_FAST_FORWARD_PUSH" == "1" ]]; then
    push_mirror
    echo "CREATED: GitLab '$REF' at $GH_SHA"
    exit 0
  fi
  echo "VERIFY ONLY: creation would mirror GitHub without rewriting history."
  exit 0
fi

GL_SHA="$(git rev-parse "$GL_REF")"
echo "GitHub: $GH_SHA"
echo "GitLab:  $GL_SHA"

if [[ "$GH_SHA" == "$GL_SHA" ]]; then
  echo "OK: refs are identical."
  exit 0
fi

if git merge-base --is-ancestor "$GL_SHA" "$GH_SHA"; then
  echo "GitLab is strictly behind GitHub."
  if [[ "$ALLOW_FAST_FORWARD_PUSH" == "1" ]]; then
    push_mirror
    echo "FAST-FORWARDED: GitLab '$REF' -> $GH_SHA"
  else
    echo "VERIFY ONLY: fast-forward push would update GitLab to $GH_SHA"
  fi
  exit 0
fi

if git merge-base --is-ancestor "$GH_SHA" "$GL_SHA"; then
  stop "GitLab is ahead of GitHub; reverse sync is not automatic"
fi

stop "GitHub and GitLab have diverged; resolve through a normal PR/MR"
