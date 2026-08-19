#!/usr/bin/env bash
set -euo pipefail

# Keep mirror failures well inside the job budget so pytest still has a chance to run.
readonly MIRROR_ATTEMPTS=3
readonly MIRROR_TIMEOUT_SECONDS=60
readonly MIRROR_KILL_AFTER_SECONDS=5
readonly -a MIRROR_BACKOFF_SECONDS=(2 5)
readonly -a APT_BOUNDED_OPTIONS=(
  -o Acquire::Retries=0
  -o Acquire::http::Timeout=20
  -o Acquire::https::Timeout=20
  -o Acquire::ftp::Timeout=20
  -o Dpkg::Lock::Timeout=20
)

infrastructure_failure() {
  local message="$1"
  printf '::error title=INFRASTRUCTURE_FAILURE::%s\n' "$message" >&2
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf 'failure_class=INFRASTRUCTURE_FAILURE\n' >>"$GITHUB_OUTPUT" || true
  fi
  exit 75
}

security_prerequisite_failure() {
  local exit_code="$1"
  trap - ERR
  printf '%s\n' \
    '::error title=SECURITY_PREREQUISITE_FAILURE::Bubblewrap/AppArmor verification failed' \
    >&2
  exit "$exit_code"
}

retry_mirror_command() {
  local label="$1"
  shift
  local attempt exit_code=1

  for ((attempt = 1; attempt <= MIRROR_ATTEMPTS; attempt++)); do
    printf 'bootstrap_command=%s attempt=%d/%d timeout_seconds=%d\n' \
      "$label" "$attempt" "$MIRROR_ATTEMPTS" "$MIRROR_TIMEOUT_SECONDS"
    if "$@"; then
      return 0
    else
      exit_code=$?
    fi
    if ((attempt < MIRROR_ATTEMPTS)); then
      sleep "${MIRROR_BACKOFF_SECONDS[attempt - 1]}"
    fi
  done

  printf 'bootstrap_command=%s exhausted_attempts=%d last_exit=%d\n' \
    "$label" "$MIRROR_ATTEMPTS" "$exit_code" >&2
  return "$exit_code"
}

timed_sudo_apt_get() {
  sudo -n timeout --signal=TERM --kill-after="${MIRROR_KILL_AFTER_SECONDS}s" \
    "${MIRROR_TIMEOUT_SECONDS}s" apt-get "${APT_BOUNDED_OPTIONS[@]}" "$@"
}

timed_apt_get() {
  timeout --signal=TERM --kill-after="${MIRROR_KILL_AFTER_SECONDS}s" \
    "${MIRROR_TIMEOUT_SECONDS}s" apt-get "${APT_BOUNDED_OPTIONS[@]}" "$@"
}

packages_are_installed() {
  local package status
  for package in apparmor bubblewrap; do
    status="$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null)" || return 1
    [[ "$status" == "installed" ]] || return 1
  done
}

if ! retry_mirror_command apt-update timed_sudo_apt_get update; then
  printf '%s\n' \
    'apt update unavailable; falling back to the GitHub runner pre-provisioned package indexes' \
    >&2
fi

if ! retry_mirror_command \
  apt-install timed_sudo_apt_get install -y --no-install-recommends apparmor bubblewrap
then
  if packages_are_installed; then
    printf '%s\n' \
      'apt install unavailable; using provenance-checked packages preinstalled on the GitHub runner' \
      >&2
  else
    infrastructure_failure \
      'bounded apt installation exhausted and required packages are not preinstalled'
  fi
fi

runner_temp="${RUNNER_TEMP:?RUNNER_TEMP must be set by the GitHub runner}"
profile_download_root="$(mktemp -d "$runner_temp/upi-app-factory-apparmor-download.XXXXXX")"
profile_extract_root="$(mktemp -d "$runner_temp/upi-app-factory-apparmor-profile.XXXXXX")"
downloaded_profile_deb=""

download_profile_package() {
  local attempt_root
  attempt_root="$(mktemp -d "$profile_download_root/attempt.XXXXXX")"
  if (cd "$attempt_root" && timed_apt_get download apparmor-profiles); then
    downloaded_profile_deb="$(
      find "$attempt_root" -maxdepth 1 -type f -name 'apparmor-profiles_*.deb' -print \
        | LC_ALL=C sort | sed -n '1p'
    )"
    [[ -n "$downloaded_profile_deb" ]]
  else
    return $?
  fi
}

profile=""
if retry_mirror_command apt-download-apparmor-profiles download_profile_package; then
  if [[ "$(dpkg-deb -f "$downloaded_profile_deb" Package)" != "apparmor-profiles" ]]; then
    infrastructure_failure 'downloaded AppArmor profile package has unexpected provenance'
  fi
  dpkg-deb -x "$downloaded_profile_deb" "$profile_extract_root" || \
    infrastructure_failure 'downloaded AppArmor profile package could not be extracted'
  profile="$profile_extract_root/usr/share/apparmor/extra-profiles/bwrap-userns-restrict"
else
  installed_profile="/usr/share/apparmor/extra-profiles/bwrap-userns-restrict"
  if [[ -r "$installed_profile" ]] \
    && dpkg-query -S "$installed_profile" 2>/dev/null | grep -q '^apparmor-profiles:'
  then
    profile="$installed_profile"
    printf '%s\n' \
      'profile download unavailable; using the apparmor-profiles package-owned runner copy' \
      >&2
  else
    cached_profile_deb="$(
      find /var/cache/apt/archives -maxdepth 1 -type f -name 'apparmor-profiles_*.deb' \
        -print 2>/dev/null | LC_ALL=C sort | sed -n '1p'
    )"
    if [[ -z "$cached_profile_deb" ]] \
      || [[ "$(dpkg-deb -f "$cached_profile_deb" Package 2>/dev/null)" != "apparmor-profiles" ]]
    then
      infrastructure_failure \
        'bounded profile download exhausted and no provenance-checked runner fallback exists'
    fi
    dpkg-deb -x "$cached_profile_deb" "$profile_extract_root" || \
      infrastructure_failure 'cached AppArmor profile package could not be extracted'
    profile="$profile_extract_root/usr/share/apparmor/extra-profiles/bwrap-userns-restrict"
    printf '%s\n' \
      'profile download unavailable; using the provenance-checked apt package cache' \
      >&2
  fi
fi

trap 'security_prerequisite_failure $?' ERR

command -v apparmor_parser
test -r "$profile"
sha256sum "$profile"
sudo -n install -m 0644 "$profile" /etc/apparmor.d/bwrap-userns-restrict
sudo -n timeout --signal=TERM --kill-after="${MIRROR_KILL_AFTER_SECONDS}s" \
  "${MIRROR_TIMEOUT_SECONDS}s" apparmor_parser -r /etc/apparmor.d/bwrap-userns-restrict
if [[ -r /proc/sys/kernel/apparmor_restrict_unprivileged_userns ]]; then
  test "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns)" = "1"
fi
dpkg-query -W -f='${Package}=${Version}\n' apparmor bubblewrap
apt-cache policy apparmor-profiles | sed -n '1,8p'
command -v bwrap
bwrap --version
timeout --signal=TERM --kill-after="${MIRROR_KILL_AFTER_SECONDS}s" \
  "${MIRROR_TIMEOUT_SECONDS}s" \
  bwrap --die-with-parent --new-session --unshare-all --share-net \
  --ro-bind / / --proc /proc --dev /dev /bin/true

trap - ERR
printf '%s\n' 'Bubblewrap/AppArmor prerequisite installation and verification passed'
