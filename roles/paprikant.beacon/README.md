paprikant.beacon
================

![lint](https://github.com/paprikant/ansible-role-beacon/actions/workflows/lint.yml/badge.svg) ![test](https://github.com/paprikant/ansible-role-beacon/actions/workflows/test.yml/badge.svg)

An ansible role that sets up a running instance of [beacon-python](https://beacon-python.readthedocs.io/en/latest/), with an accompaning PostgreSQL database. Both services are exposed via network - refer to the _Role Variables_ section for default ports and credentials.

This role is using the official [postgres](https://hub.docker.com/_/postgres) and [beacon-python](https://hub.docker.com/r/cscfi/beacon-python/) docker images. Hence, docker is installed as a requirement to run beacon-python.  

Requirements
------------

The role uses the community.docker collection, which can be installed from ansible galaxy:

    ansible-galaxy collection install community.docker

Role Variables
--------------

Available variables are listed below, along with default values (see defaults/main.yml):

```yaml
shared_network_name: beacon-python
```

Name of a docker network that is shared between postgres and beacon-python containers. There is not much reason to change this.

```yaml
postgres_container_name: beacon-python-db
postgres_version: 13
```

PostgreSQL container name and version. The version may be any valid tag of the [official PostgreSQL image](https://hub.docker.com/_/postgres)

```yaml
postgres_external_binding: 5432
```
The port on which to expose the PostgreSQL database. You may also give an ip:port combination to expose the database on a specific network interface only.

```yaml
postgres_user: beacon
postgres_pass: change_me!
```
Credentials of the database user. The specified user is created on first start - for more information checḱ out the `POSTGRES_USER` and `POSTGRES_PASSWORD` environment variables in the docs of the PostgreSQL image. It is recommended to (at least) change the password.

> :warning: **Do not change these credentials after the first playbook execution**: Ansible will not drop the beacon database and as a result no other user will get access. (unless you manually create a new user using the old credentials first)

```yaml
postgres_database_name: beacon
```
Name of the database used by beacon-python. Will be created on initial playbook execution - for more information checḱ out the `POSTGRES_DATABASE` environment variables in the docs of the PostgreSQL image.

```yaml
postgres_data_dir: /var/lib/postgresql/data
```
Where to store PostgreSQL database files.

```yaml
postgres_init_dir: /var/lib/postgresql/init
```
Ansible will put a `.sql` file here that is used to create the tables of the beacon database.


```yaml
bp_container_name: beacon-python
bp_version: latest
```
Container name and version for beacon-python. Use any [tag of the beacon-python docker image](https://hub.docker.com/r/cscfi/beacon-python/tags) as bp_version.

```yaml
bp_external_binding: 5050
```
The port on which to expose the beacon API. You may also give an ip:port combination to expose the API on a specific network interface only. The protocol will be HTTP since beacon-python does not support HTTPS yet.

```yaml
# Name of the Beacon service
beacon_info_title: GA4GH Beacon at usegalaxy.eu

# Documentation url for GA4GH Discovery
beacon_info_docs_url: https://app.swaggerhub.com/apis/ELIXIR-Finland/ga-4_gh_beacon_api_specification/1.0.0-rc1

# Globally unique identifier for this Beacon instance
beacon_info_beaconId: galaxy.eu.beacon

# Description of this Beacon service
beacon_info_description: Beacon service hosting datastes from all over the usegalaxy.eu instance

# URL of Beacon service
beacon_info_url: https://usegalaxy.eu/beacon/

# Datetime when this Beacon was created
beacon_info_createtime: 2022-11-16T00:00:00Z

# GA4GH Discovery type `groupId` and `artifactId`, joined in /service-info with apiVersion
# See https://github.com/ga4gh-discovery/ga4gh-service-info for more information and possible values
beacon_info_service_group: galaxy-eu
beacon_info_service_artifact: beacon

# GA4GH Discovery server environment, possible values: prod, dev, tes
beacon_info_environment: prod

#Globally unique identifier for organisation that hosts this Beacon service
beacon_info_org_id: usegalaxy.eu

# Name of organisation that hosts this Beacon service
beacon_info_org_name: Galaxy Europe

# Description for organisation
beacon_info_org_description: European Galaxy community

# Visit address of organisation
beacon_info_org_address: Georges-Köhler-Allee 79, 79110 Freiburg im Breisgau

# Homepage of organisation
beacon_info_org_welcomeUrl: https://galaxyproject.org/eu/

# URL for contacting organisation
beacon_info_org_contact_url: https://usegalaxy-eu.github.io/freiburg/people.html

# URL for organisation logo
beacon_info_org_logo_url: https://galaxyproject.org/images/galaxy-logos/galaxy_project_logo_square.png

# Other organisational information
beacon_info_org_info: The European Galaxy server UseGalaxy.eu is maintained primarily by the Freiburg Galaxy Team in collaboration with other academic groups across Europe and with the US Galaxy team.

```
Above section contains metadata that is published by the `/` and `/service-info` endpoints for service discovery.


Dependencies
------------

* includes [geerlingguy.docker](https://galaxy.ansible.com/geerlingguy/docker) role

Example Playbook
----------------

Minimal plabook (since changing the database password is recommended in most use cases):

```yaml
- hosts: all
  tasks:
    - name: "Include paprikant.beacon"
      include_role:
        name: "paprikant.beacon"
      vars:
        postgres_pass: please_use_a_secure_password
```

License
-------

BSD
