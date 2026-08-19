from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/install_github_ci_bwrap_prerequisite.sh"
WORKFLOW = ROOT / ".github/workflows/governed-ci.yml"


def test_bwrap_bootstrap_helper_has_bounded_resilient_contract() -> None:
    helper = HELPER.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert workflow.count("bash scripts/install_github_ci_bwrap_prerequisite.sh") == 2
    assert "MIRROR_ATTEMPTS=3" in helper
    assert "MIRROR_TIMEOUT_SECONDS=60" in helper
    assert "MIRROR_BACKOFF_SECONDS=(2 5)" in helper
    assert "timeout --signal=TERM --kill-after=" in helper
    assert "Acquire::http::Timeout=20" in helper
    assert "Acquire::https::Timeout=20" in helper
    assert "Dpkg::Lock::Timeout=20" in helper
    assert "INFRASTRUCTURE_FAILURE" in helper
    assert "exit 75" in helper

    # The fallback may use only package-manager-provenanced Ubuntu runner assets.
    assert "packages_are_installed" in helper
    assert "dpkg-query -S" in helper
    assert "/var/cache/apt/archives" in helper
    assert '!= "apparmor-profiles"' in helper

    # Mandatory package, profile, AppArmor, sysctl, and isolation probes remain.
    for contract in (
        "install -y --no-install-recommends apparmor bubblewrap",
        "download apparmor-profiles",
        "usr/share/apparmor/extra-profiles/bwrap-userns-restrict",
        "apparmor_parser -r /etc/apparmor.d/bwrap-userns-restrict",
        "/proc/sys/kernel/apparmor_restrict_unprivileged_userns",
        "bwrap --die-with-parent --new-session --unshare-all --share-net",
    ):
        assert contract in helper


def test_exhausted_dependency_install_is_classified_as_infrastructure_failure(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    attempts = tmp_path / "apt-attempts.log"

    (fake_bin / "sudo").write_text(
        "#!/usr/bin/env bash\n"
        "if [[ ${1:-} == -n ]]; then shift; fi\n"
        'exec "$@"\n',
        encoding="utf-8",
    )
    (fake_bin / "apt-get").write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >>"$APT_ATTEMPT_LOG"\n'
        "exit 42\n",
        encoding="utf-8",
    )
    (fake_bin / "dpkg-query").write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    (fake_bin / "sleep").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    for command in ("sudo", "apt-get", "dpkg-query", "sleep"):
        (fake_bin / command).chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "APT_ATTEMPT_LOG": str(attempts),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "RUNNER_TEMP": str(tmp_path),
        }
    )
    completed = subprocess.run(
        ["bash", str(HELPER)],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 75, completed.stdout
    assert "INFRASTRUCTURE_FAILURE" in completed.stdout
    assert "required packages are not preinstalled" in completed.stdout
    assert len(attempts.read_text(encoding="utf-8").splitlines()) == 6
