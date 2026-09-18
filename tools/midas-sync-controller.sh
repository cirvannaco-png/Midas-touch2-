#!/usr/bin/env bash
set -euo pipefail

GITHUB_REMOTE="${GITHUB_REMOTE:-github}"
GITLAB_REMOTE="${GITLAB_REMOTE:-gitlab-sync}"
PROTECTED_REGEX='^(main|production)$'

git rev-parse --git-dir >/dev/null 2>&1 || {
  echo "Not a Git repository."
  exit 1
}

git fetch "$GITHUB_REMOTE" '+refs/heads/*:refs/remotes/github/*' --prune
git fetch "$GITLAB_REMOTE" '+refs/heads/*:refs/remotes/gitlab-sync/*' --prune

git show-ref --head >/dev/null

mapfile -t BRANCHES < <(
  {
    git for-each-ref --format='%(refname)' refs/remotes/github/ | sed 's#^refs/remotes/github/##'
    git for-each-ref --format='%(refname)' refs/remotes/gitlab-sync/ | sed 's#^refs/remotes/gitlab-sync/##'
  } | sort -u
)

result=0

for branch in "${BRANCHES[@]}"; do
  gh="refs/remotes/github/$branch"
  gl="refs/remotes/gitlab-sync/$branch"
  gh_exists=$(git show-ref --verify --quiet "$gh"; echo $?)
  gl_exists=$(git show-ref --verify --quiet "$gl"; echo $?)

  if [ "$gh_exists" -ne 0 ] && [ "$gl_exists" -ne 0 ]; then
    continue
  fi

  if [ "$gh_exists" -ne 0 ]; then
    if [[ "$branch" =~ $PROTECTED_REGEX ]]; then
      echo "ALERT: protected branch exists only on GitLab: $branch"
      result=2
    else
      echo "SYNC GitLab -> GitHub (create): $branch"
      git push "$GITHUB_REMOTE" "$gl:refs/heads/$branch"
    fi
    continue
  fi

  if [ "$gl_exists" -ne 0 ]; then
    if [[ "$branch" =~ $PROTECTED_REGEX ]]; then
      echo "ALERT: protected branch exists only on GitHub: $branch"
      result=2
    else
      echo "SYNC GitHub -> GitLab (create): $branch"
      git push "$GITLAB_REMOTE" "$gh:refs/heads/$branch"
    fi
    continue
  fi

  gh_sha=$(git rev-parse "$gh")
  gl_sha=$(git rev-parse "$gl")

  if [ "$gh_sha" = "$gl_sha" ]; then
    echo "OK $branch $gh_sha"
    continue
  fi

  if git merge-base --is-ancestor "$gl" "$gh"; then
    if [[ "$branch" =~ $PROTECTED_REGEX ]]; then
      echo "ALERT: protected branch GitHub ahead of GitLab: $branch"
      result=2
    else
      echo "SYNC GitHub -> GitLab: $branch $gl_sha -> $gh_sha"
      git push "$GITLAB_REMOTE" "$gh:refs/heads/$branch"
    fi
    continue
  fi

  if git merge-base --is-ancestor "$gh" "$gl"; then
    if [[ "$branch" =~ $PROTECTED_REGEX ]]; then
      echo "ALERT: protected branch GitLab ahead of GitHub: $branch"
      result=2
    else
      echo "SYNC GitLab -> GitHub: $branch $gh_sha -> $gl_sha"
      git push "$GITHUB_REMOTE" "$gl:refs/heads/$branch"
    fi
    continue
  fi

  echo "CONFLICT: $branch"
  echo "  GitHub: $gh_sha"
  echo "  GitLab: $gl_sha"
  echo "  Automatic merge/force-push: BLOCKED"
  result=2
done

exit "$result"
