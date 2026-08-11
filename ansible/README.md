# Ansible host provisioning

On the supported Debian-family host:

```sh
cd ansible
sudo ansible-playbook playbooks/site.yml
```

The idempotent role installs Debian's `simh`, Python 3 and PyYAML packages,
creates the non-login `unix-time-machine` account/group and protected canonical
directories, and fails with a diagnostic if `pdp11` is not on PATH. It installs
no historical media. Debian is the M1 qualification base; Ubuntu is accepted as
Debian-family only where its repositories provide the same package/executable,
and the post-install assertion prevents silent guessing.
