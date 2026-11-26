# usegalaxy.eu infrastructure playbook

Ansible playbooks for UseGalaxy.it infrastructure.   
<!-- For the playbook managing Galaxy itself, see https://github.com/galaxyproject/usegalaxy-playbook/ -->

## Provisioned infrastructure

At least 5 VMs are required:
| VM                       | Image      | Tested on                          |
| ------------------------ | ---------- | ---------------------------------- |
| Galaxy VM                | RockyLinux | RockyLinux 9.1                     |
| NFS server               | vggp       | vggp-v60-j225-1a1df01ec8f3-dev.raw |
| HTCondor Central Manager | vggp       | vggp-v60-j225-1a1df01ec8f3-dev.raw |
| Database                 | RockyLinux | RockyLinux 9.1                     |
| Rabbit-MQ server         | RockyLinux | RockyLinux 9.1                     |

Addtitional VMs for Database management:
| VM      | Image      | Tested on      |
| ------- | ---------- | -------------- |
| Replica | RockyLinux | RockyLinux 9.2 |
| Backup  | RockyLinux | RockyLinux 9.2 |

vggp images are located at https://usegalaxy.eu/static/vgcn/  
Recommended to use the latest main version.


## Requiremets

On the control VM you need to install:
1. Virtual environment

```
python3 -m venv master_env/
```
2. Ansible [core 2.11.3] in the venv

```
. master_env/bin/activate
pip install wheel ansible-core==2.11.3
```
3. Install the ansible roles that are not tracked in this repository

```
ansible-galaxy install -r requirements.yml
```

## Infrastructure-playbook

`hosts` inventory file contains each infrastructure element created using Terraform (IP adresses of machines and FQDNs)  
Make sure, there are FQDNs for Galaxy and RabbitMQ VMs.  

### Configuration playbooks in order of execution

1. `db_cluster.yml` creates PostgresQL cluster: `database`, `replica` and `backup` servers. Variables:  
   - `group_vars/database.yml` (backup and replication are enabled by default, may be changed in this var file)  
   - `secret_group_vars/db-main.yml` (sensitive data)  
2. `mount.yml` creates shared directories.
3. `central-manager.yml` creates and configures HTCondor Central Manager. Variabes:  
   - `group_vars/central-manager.yml`
   - `secret_group_vars/htcondor.yml` (sensitive data)
4. `sn06.yml` creates and configures Galaxy instance. Variables:
   - `group_vars/gxconfig.yml` (the base galaxy configuration)
   - `secret_group_vars/db-main.yml` (database secrets)
   - `secret_group_vars/htcondor.yml` (condor secrets)
   - `secret_group_vars/rabbitmq.yml` (rabbitmq and pulsar secrets)
   - `secret_group_vars/all.yml` (all of the other assorted secrets)
5. `rabbitmq.yml` configures RabbitMQ server. Variables:
   - `group_vars/rabbitmq.yml`
   - `secret_group_vars/rabbitmq.yml`

Executors for HTCondor are managed by Terrform+Jenkins (https://github.com/usegalaxy-it/vgcn-infrastructure)

### Jenkins (`build.yml`)

`build.yml` configures the Jenkins controller. Variables:
   - `group_vars/build.yml`
   - `secret_group_vars/jenkins.yml` (sensitive data)

The `geerlingguy.java` and `geerlingguy.jenkins` roles use conditionals that evaluate to strings, which
ansible-core 2.19+ rejects. Run the playbook with broken conditionals allowed:

```
ANSIBLE_ALLOW_BROKEN_CONDITIONALS=True ansible-playbook -i inventory build.yml
```

### Keycloak (`keycloak_prod.yml`)

`keycloak_prod.yml` deploys Keycloak on `auth.elixirservices.it` (inventory group `keycloak_prod`) as a docker compose
stack in `/data/keycloak`: `postgres_db`, `keycloak_app` and the `nginx_proxy` reverse proxy. Variables:
   - `group_vars/keycloak_prod.yml` (image versions, JVM options, custom theme switch)
   - `secret_group_vars/all.yml` (database and admin credentials, rendered into `/data/keycloak/.env`)
   - `secret_group_vars/os.yml` (service user password): **not tracked in this repository**, it exists only on the
     control VM and must be recreated there when the control VM is rebuilt

Templates: `templates/keycloak/compose.yml.j2`, `templates/keycloak/keycloak_prod.conf.j2`, `templates/keycloak/env.j2`
and `templates/nginx/keycloak-ssl.j2`. The login theme lives in `files/keycloak/themes/usegalaxy-it/` and is copied to
`/data/keycloak/themes/` (enabled by `keycloak_custom_themes_enabled`). A theme change restarts `keycloak_app` and clears
its theme cache. The certificate is managed by `usegalaxy-eu.certbot` and is only requested if it does not exist yet.

All images are pinned in `group_vars/keycloak_prod.yml` (`_keycloack_version`, `_kc_postgresql_version`,
`keycloak_nginx_image`). To upgrade a component, bump its version there. Changing an image recreates its container:
a PostgreSQL change restarts the database, so run it when a short login outage is acceptable.

Run a dry-run first, check the diff, then apply (the certbot role has string conditionals, see the Jenkins note above):

```
ANSIBLE_ALLOW_BROKEN_CONDITIONALS=True ansible-playbook -i inventory keycloak_prod.yml --check --diff
ANSIBLE_ALLOW_BROKEN_CONDITIONALS=True ansible-playbook -i inventory keycloak_prod.yml
```

The `--diff` output includes `/data/keycloak/.env` when it changes, i.e. the database and admin passwords: do not share
it unredacted. After the run, check the stack on the Keycloak VM:

```
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
curl -sI https://auth.elixirservices.it/ | head -1
```
