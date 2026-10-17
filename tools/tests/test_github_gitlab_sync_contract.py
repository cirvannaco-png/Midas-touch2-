from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "github-to-gitlab-sync.yml"


def test_excluded_github_workflows_are_removed_from_existing_mirror() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    remove_stale_tree = "rm -rf /tmp/midas-gitlab-tree/.github"
    rsync = "rsync -a --delete"

    assert remove_stale_tree in source
    assert rsync in source
    assert source.index(remove_stale_tree) < source.index(rsync)
    assert "--exclude '.github/'" in source


def test_sync_is_scoped_to_canonical_main_for_manual_dispatch() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.ref == 'refs/heads/main'" in source
    assert "github.event.workflow_run.head_branch == github.event.repository.default_branch" in source
