from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GITHUB_CI = ROOT / ".github" / "workflows" / "midas-ci.yml"
MIRROR = ROOT / ".github" / "workflows" / "midas-github-to-gitlab-mirror.yml"
GITLAB_CI = ROOT / ".gitlab-ci.yml"
CONTROLLER = ROOT / "scripts" / "midas-sync-controller.sh"
OPERATING_MODEL = ROOT / "docs" / "OPERATING_MODEL.md"
SYNC_RUNBOOK = ROOT / "docs" / "SYNC_RUNBOOK.md"
PROMOTION = ROOT / "docs" / "PROMOTION_WORKFLOW.md"
README = ROOT / "README.md"


ACTIVE_GITLAB_REPO = "midas-touch-group1/midas-touch2"
SYNC_GITLAB_REPO = "midas-touch-group1/midas-touch2-sync"
OBSOLETE_GITLAB_REPO = "midas-touch-group1/midas-touchsync"


def test_mirror_targets_only_the_sha1_sync_repository():
    text = MIRROR.read_text()
    assert f"gitlab.com/{SYNC_GITLAB_REPO}.git" in text
    assert f"gitlab.com/{ACTIVE_GITLAB_REPO}.git" not in text
    assert f"gitlab.com/{OBSOLETE_GITLAB_REPO}.git" not in text


def test_governance_documents_declare_active_and_sync_gitlab_repositories():
    operating = OPERATING_MODEL.read_text()
    runbook = SYNC_RUNBOOK.read_text()
    assert ACTIVE_GITLAB_REPO in operating
    assert SYNC_GITLAB_REPO in operating
    assert SYNC_GITLAB_REPO in runbook
    assert "kelsonkiiru15/midas-touch2" not in operating
    assert "kelsonkiiru15/midas-touch2" not in runbook
    assert f"gitlab.com/{OBSOLETE_GITLAB_REPO}.git" not in MIRROR.read_text()


def test_github_ci_is_pr_gated_to_main_not_broad_push_ci():
    text = GITHUB_CI.read_text()
    assert 'push:\n    branches:\n      - main' in text
    assert 'pull_request:\n    branches:\n      - main' in text
    assert '"hardening/**"' not in text
    assert '"feature/**"' not in text


def test_github_ci_contains_the_required_validation_layers():
    text = GITHUB_CI.read_text()
    for job in (
        "python-tests:",
        "research-tests:",
        "mql5-structure:",
        "handbook-tests:",
        "bridge-quality:",
        "repository-governance:",
    ):
        assert job in text


def test_gitlab_ci_is_explicitly_paused():
    text = GITLAB_CI.read_text()
    assert "workflow:" in text
    assert "rules:" in text
    assert "when: never" in text


def test_sync_controller_is_fail_closed_for_release_refs():
    text = CONTROLLER.read_text()
    assert 'PROTECTED_REFS=("main" "production")' in text
    assert "feature/*|fix/*|audit/*|chore/*|ops/*|integration/*|sync-test/*" in text
    assert "force-push" not in text.lower() or "never force-pushes" in text.lower()
    assert "GitHub and GitLab have diverged; resolve through a normal PR/MR" in text


def test_promotion_docs_do_not_claim_cross_provider_sha_identity():
    text = PROMOTION.read_text()
    assert "GitLab `production` does not exist." in text
    assert "GitHub `production` exists at `74cabb8d61564c1bebec2287df6ad44f82dea2aa`" in text
    assert "GitHub `main` == GitLab `main`" not in text
    assert "The release commit is the same SHA on both providers" not in text


def test_root_readme_distinguishes_reference_code_from_live_runtime():
    text = README.read_text()
    assert "Non-production handbook/reference implementation" in text
    assert "GitLab CI is currently paused" in text


def test_documented_scheduler_is_not_misrepresented_as_gitlab_ci():
    text = README.read_text()
    assert "Operational/admin trigger (scheduler is external to this repository)" in text
    assert "GitLab CI/CD (scheduled maintenance)" not in text
