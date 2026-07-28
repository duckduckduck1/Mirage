#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SKIP_DOCKER=false

usage() {
  cat <<'EOF'
Usage: ops/release/check-local.sh [--skip-docker]

Runs the Mirage v2 release gate.

Options:
  --skip-docker  Skip the optional build of the temporary Marzban A-13 image.
EOF
}

log() {
  printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-docker)
      SKIP_DOCKER=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 was not found"
}

check_no_secrets() {
  python3 - <<'PY'
import re
import subprocess
import sys
from pathlib import Path

tracked = subprocess.check_output(["git", "ls-files", "-z"])
paths = [Path(item.decode("utf-8")) for item in tracked.split(b"\0") if item]
findings: list[str] = []

for path in paths:
    normalized = path.as_posix()
    name = path.name

    if name.startswith(".env") and not name.endswith(".example"):
        findings.append(f"{normalized}: tracked env file")
    if any(part in {"backups", "exports", "secrets"} for part in path.parts):
        findings.append(f"{normalized}: tracked sensitive directory")
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".dump", ".backup", ".key", ".pem", ".p12"}:
        findings.append(f"{normalized}: tracked sensitive file extension")

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        findings.append(f"{normalized}: cannot read file: {exc}")
        continue

    if re.search(r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----", text):
        findings.append(f"{normalized}: private key marker")

    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        proxy_url = re.search(r"\b(?:vless|trojan|ss)://\S+@\S+", stripped)
        if proxy_url:
            lowered = stripped.lower()
            placeholder = any(
                token in lowered
                for token in [
                    "...",
                    "example.",
                    "example/",
                    "server_ip",
                    "server_host",
                    "domain",
                    "домен",
                    "uuid",
                    "panel.local",
                    "vpn.example",
                ]
            )
            real_ip_url = re.search(r"\b(?:vless|trojan|ss)://\S+@\d{1,3}(?:\.\d{1,3}){3}\b", stripped)
            if real_ip_url or not placeholder:
                findings.append(f"{normalized}:{line_no}: proxy link")

        assignment = re.match(r"^([A-Z0-9_]*(?:TOKEN|PASSWORD|PRIVATE_KEY|SECRET)[A-Z0-9_]*)=(.+)$", stripped)
        if assignment:
            value = assignment.group(2).strip().strip("\"'")
            safe_value = (
                not value
                or value == "..."
                or value.startswith("${")
                or value.startswith("$")
                or value.startswith("CHANGE_")
                or value.startswith("PASTE_")
                or value.startswith("SERVER_")
                or "example" in value.lower()
            )
            if not safe_value:
                findings.append(f"{normalized}:{line_no}: secret-like assignment")

if findings:
    print("Potential secrets in tracked files:", file=sys.stderr)
    for item in findings:
        print(f"  - {item}", file=sys.stderr)
    sys.exit(1)
PY
}

check_no_legacy() {
  python3 - <<'PY'
import subprocess
import sys
from pathlib import Path

legacy_paths = ("ops/admin/", "ops/xui/", "ops/vpn/", "ops/up.sh")
legacy_terms = ("3x-ui", "x-ui", "xui-ops")
historical_paths = {"CHANGELOG.md", "ops/release/check-local.sh"}
tracked = [Path(item) for item in subprocess.check_output(["git", "ls-files"]).decode().splitlines()]
findings: list[str] = []

for path in tracked:
    normalized = path.as_posix()
    if normalized.startswith(legacy_paths):
        findings.append(f"{normalized}: legacy path")
        continue
    if normalized in historical_paths:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for term in legacy_terms:
        if term in text.lower():
            findings.append(f"{normalized}: legacy term {term}")
            break

if findings:
    print("Legacy Mirage v0.1 material is still tracked:", file=sys.stderr)
    for item in findings:
        print(f"  - {item}", file=sys.stderr)
    sys.exit(1)
PY
}

check_documentation_locales() {
  python3 - <<'PY'
import sys
from pathlib import Path

root = Path("docs")
english = root / "en"
source = [path for path in root.rglob("*.md") if ".vitepress" not in path.parts and "en" not in path.parts]
findings: list[str] = []

for russian in source:
    relative = russian.relative_to(root)
    translated = english / relative
    if not translated.is_file():
        findings.append(f"missing English translation: {translated}")

for translated in english.rglob("*.md"):
    relative = translated.relative_to(english)
    russian = root / relative
    if not russian.is_file():
        findings.append(f"orphan English translation: {translated}")

if findings:
    print("Documentation locale parity failed:", file=sys.stderr)
    for item in findings:
        print(f"  - {item}", file=sys.stderr)
    sys.exit(1)
PY
}

check_a13_patch() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' RETURN

  python3 - "$temp_dir" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1]) / "share.py"
target.write_text(
    """\
                if sids := inbound.get("sids"):
                    inbound["sid"] = random.choice(sids)
""",
    encoding="utf-8",
)
PY
  python3 infra/ansible/roles/marzban/files/apply-a13.py "$temp_dir/share.py"
  python3 - "$temp_dir/share.py" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding="utf-8")
assert 'host_inbound["sid"] = random.choice(sids)' in source
assert '\n                    inbound["sid"] = random.choice(sids)' not in source
PY

  if [ "$SKIP_DOCKER" = true ]; then
    log "Docker A-13 image build skipped"
    return
  fi

  require_command docker
  python3 - "$temp_dir" <<'PY'
import re
import sys
from pathlib import Path

root = Path(".")
defaults = (root / "infra/ansible/roles/marzban/defaults/main.yml").read_text(encoding="utf-8")
template = (root / "infra/ansible/roles/marzban/templates/Dockerfile.a13.j2").read_text(encoding="utf-8")
digest = re.search(r"sha256:[a-f0-9]{64}", defaults)
revision = re.search(r'^marzban_a13_patch_revision: (.+)$', defaults, re.M)
if not digest or not revision:
    raise SystemExit("could not read pinned A-13 image metadata")

rendered = template
rendered = rendered.replace("{{ marzban_a13_base_image }}", f"gozargah/marzban@{digest.group(0)}")
rendered = rendered.replace("{{ marzban_a13_base_digest }}", digest.group(0))
rendered = rendered.replace("{{ marzban_a13_patch_revision }}", revision.group(1).strip())
destination = Path(sys.argv[1])
(destination / "Dockerfile").write_text(rendered, encoding="utf-8")
(destination / "apply-a13.py").write_bytes((root / "infra/ansible/roles/marzban/files/apply-a13.py").read_bytes())
PY
  docker build --pull --tag mirage-a13-release-gate "$temp_dir"
}

cd "$REPO_ROOT"

export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-/tmp/mirage-ansible-local}"
mkdir -p "$ANSIBLE_LOCAL_TEMP"

log "Tool versions"
require_command python3
require_command ansible-playbook
require_command yamllint
require_command node
require_command npm
python3 --version
ansible-playbook --version | head -n 1
yamllint --version
node --version
npm --version

log "Secret guard"
check_no_secrets

log "Legacy removal guard"
check_no_legacy

log "Ansible syntax and style"
yamllint infra/ansible .github/workflows
ansible-playbook --syntax-check -i infra/ansible/inventory/localhost.yml infra/ansible/site.yml
ansible-playbook --syntax-check -i infra/ansible/inventory/localhost.yml infra/ansible/playbooks/deploy-clean.yml
ansible-playbook --syntax-check -i infra/ansible/inventory/localhost.yml infra/ansible/playbooks/deploy-prepared.yml
ansible-playbook --syntax-check -i infra/ansible/inventory/localhost.yml infra/ansible/playbooks/restore.yml
python3 -m py_compile infra/ansible/roles/marzban/files/apply-a13.py
check_a13_patch

log "Documentation"
check_documentation_locales
npm ci
npm run docs:build

log "Release gate passed"
