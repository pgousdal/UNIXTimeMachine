# Ansible host provisioning

From the repository root on the supported Debian 13 (Trixie) host:

```sh
sudo apt-get install ansible
make provision
```

This target supplies the repository's absolute Ansible configuration, inventory,
role path, and playbook; global Ansible configuration is not part of the contract.
The equivalent direct invocation is:

```sh
ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg" ansible-playbook \
  -i "$PWD/ansible/inventory/localhost.yml" \
  "$PWD/ansible/playbooks/site.yml" --ask-become-pass
```

The idempotent role installs explicit build dependencies, downloads the pinned
Open SIMH source archive with SHA-256 verification, builds only `pdp11` with
host networking disabled, installs it at the project-selected absolute path,
records provenance, removes the build tree, and creates the service account and
protected directories. The verified source archive remains in the controlled
system cache for auditing/reprovisioning. It installs no historical media.

No other Debian release, Ubuntu release, or other distribution is currently
claimed as qualified. Do not add Bookworm, testing, unstable, or third-party
binary repositories to provision this baseline.
