#!/usr/bin/env python3
"""Helper to generate an Ansible Vault-encrypted vars file for AWS credentials.

Usage:
    python scripts/encrypt_aws_credentials.py

The script prompts for the AWS access key ID and secret access key, then writes
an encrypted Ansible Vault file to ansible/group_vars/aws_credentials.yml.
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
import tempfile


def prompt_secret(label: str) -> str:
    """Prompt twice and return the confirmed secret."""
    while True:
        first = getpass.getpass(f"Enter {label}: ")
        second = getpass.getpass(f"Confirm {label}: ")
        if first == second:
            return first
        print("Secrets do not match. Try again.", file=sys.stderr)


def encrypt_with_vault(plain_vars: str, vault_password: str, output_path: str) -> None:
    """Encrypt plain YAML content with ansible-vault and write to output_path."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as pw_file:
        pw_file.write(vault_password)
        pw_path = pw_file.name

    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as plain_file:
        plain_file.write(plain_vars)
        plain_path = plain_file.name

    try:
        subprocess.run(
            [
                "ansible-vault",
                "encrypt",
                "--vault-password-file",
                pw_path,
                "--output",
                output_path,
                plain_path,
            ],
            check=True,
        )
    finally:
        os.unlink(pw_path)
        os.unlink(plain_path)


def main() -> int:
    access_key = prompt_secret("AWS Access Key ID")
    secret_key = prompt_secret("AWS Secret Access Key")
    vault_password = prompt_secret("Ansible Vault password")

    plain = (
        f"aws_access_key_id: {access_key}\n"
        f"aws_secret_access_key: {secret_key}\n"
    )

    output_path = os.path.join(
        os.path.dirname(__file__), "..", "ansible", "group_vars", "aws_credentials.yml"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    encrypt_with_vault(plain, vault_password, output_path)

    print(f"Encrypted credentials written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
