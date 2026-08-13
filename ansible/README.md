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
canonical directories. Implemented systems receive protected, setgid
`root:unix-time-machine` mode 2750 media directories. The shared staging root is
`unix-time-machine:unix-time-machine` mode 2770, so an enrolled operator can run
`install prepare` without sudo and new staging directories inherit the service
group. Media files remain protected publication objects (normally mode 0440);
provisioning creates no historical media and does not weaken existing content.
The verified source archive remains in the controlled system cache for
auditing/reprovisioning.

Provisioning does not select human operators. Enroll one existing local account
explicitly and idempotently from the repository root:

```sh
make operator-add USER="$USER"
```

Log out completely and log in again (or start an equivalent new login session)
before running operator commands; existing processes retain their old group set.
The target validates that the account exists and never grants arbitrary users or
broadens world permissions.

No other Debian release, Ubuntu release, or other distribution is currently
claimed as qualified. Do not add Bookworm, testing, unstable, or third-party
binary repositories to provision this baseline.
