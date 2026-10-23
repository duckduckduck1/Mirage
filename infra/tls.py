#!/usr/bin/env python3
"""Publish a validated TLS pair, then force Caddy reload without restarting Xray."""

import argparse
import fcntl
import os
import shutil
import sys
import tempfile
from pathlib import Path

from host import (SafeError, compose, load_config, notify, private_dir,
                  read_env, run, sha256)


def validate_pair(certificate, key, hostname, ca_file=None):
    certificate, key = str(certificate), str(key)
    run(["openssl", "x509", "-in", certificate, "-noout", "-checkend", "604800"])
    run(["openssl", "x509", "-in", certificate, "-noout", "-checkhost", hostname])
    public_certificate = run(["openssl", "x509", "-in", certificate, "-pubkey", "-noout"])
    public_key = run(["openssl", "pkey", "-in", key, "-pubout"])
    if public_certificate != public_key:
        raise SafeError("The certificate and private key do not match.")
    command = ["openssl", "verify", "-purpose", "sslserver", "-verify_hostname", hostname]
    if ca_file:
        command.extend(["-CAfile", str(ca_file)])
    run([*command, "-untrusted", certificate, certificate])


def point_current(root, target):
    temporary = root / ".current.new"
    if temporary.is_symlink():
        temporary.unlink()
    elif temporary.exists():
        raise SafeError("An unexpected certificate staging path already exists.")
    temporary.symlink_to(target)
    os.replace(temporary, root / "current")


def publish(config, certificate, key, *, publish_only=False):
    read_env(config)
    root = private_dir(Path(config["state_dir"]) / "tls")
    releases = private_dir(root / "releases")
    with (root / "publish.lock").open("a") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = root / "current"
        if current.exists() and not current.is_symlink():
            raise SafeError("The current certificate path must be a managed symlink.")
        old = os.readlink(current) if current.is_symlink() else None
        if old and (not current.resolve().is_relative_to(releases.resolve()) or not current.exists()):
            raise SafeError("The current certificate link is invalid.")
        with tempfile.TemporaryDirectory(prefix=".pair-", dir=root) as temporary:
            stage = Path(temporary)
            for source, filename in ((certificate, "fullchain.pem"), (key, "key.pem")):
                target = stage / filename
                shutil.copyfile(source, target)
                target.chmod(0o600)
            validate_pair(stage / "fullchain.pem", stage / "key.pem", config["public_host"], config["ca_file"])
            # Include both hashes so reissuing/replacing a key cannot reuse an old pair.
            name = sha256(stage / "fullchain.pem")[:24] + "-" + sha256(stage / "key.pem")[:24]
            release = releases / name
            if release.exists():
                for filename in ("fullchain.pem", "key.pem"):
                    if sha256(release / filename) != sha256(stage / filename):
                        raise SafeError("A certificate release unexpectedly differs.")
            else:
                release.mkdir(mode=0o700)
                for filename in ("fullchain.pem", "key.pem"):
                    shutil.copyfile(stage / filename, release / filename)
                    (release / filename).chmod(0o600)
        point_current(root, "releases/" + name)
        if publish_only:
            return
        if old is None:
            current.unlink()
            raise SafeError("Bootstrap certificates with --publish-only before starting Compose.")
        try:
            compose(config, "exec", "-T", "caddy", "caddy", "validate", "--config", "/etc/caddy/Caddyfile")
            compose(config, "exec", "-T", "caddy", "caddy", "reload", "--force", "--config", "/etc/caddy/Caddyfile")
        except SafeError:
            point_current(root, old)
            try:
                compose(config, "exec", "-T", "caddy", "caddy", "reload", "--force", "--config", "/etc/caddy/Caddyfile")
            except SafeError:
                raise SafeError("Certificate reload and recovery reload failed; investigate both listeners.") from None
            raise SafeError("Certificate reload failed; the previous pair was restored.") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--publish-only", action="store_true", help="Bootstrap or test only; do not contact Docker")
    args = parser.parse_args()
    os.umask(0o077)
    config = None
    try:
        config = load_config(args.config)
        publish(config, args.certificate, args.key, publish_only=args.publish_only)
    except Exception:
        if config and not args.publish_only:
            try:
                notify(config, "Mirage TLS publication/reload failed. Check both TLS listeners; no VPN restart was requested.")
            except Exception:
                pass
        print("TLS publication failed; private values and command output were suppressed.", file=sys.stderr)
        return 1
    print("TLS pair published. Verify both served certificates and connection continuity separately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
