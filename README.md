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
