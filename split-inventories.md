# Inventory separati per dev e prod

Questo documento descrive come è organizzato il repository dopo il refactoring
che ha separato gli ambienti **dev** e **prod** in due inventory distinti.

## In breve

- Ogni ambiente ha la sua cartella in `inventories/`, con il proprio file
  `inventory` e i propri `group_vars/`.
- I playbook sono **uguali per tutti gli ambienti**: le differenze stanno solo
  nelle variabili dell'inventory.
- L'ambiente si sceglie con `-i`. Senza `-i` si usa **dev** (impostato in
  `ansible.cfg`), così un lancio dimenticato non tocca mai la produzione.

```bash
ansible-playbook usegalaxy_it_dev.yml                       # dev (default)
ansible-playbook -i inventories/prod usegalaxy_it.yml       # prod
```

## Struttura

```
ansible.cfg                       # inventory = inventories/dev
group_vars/                       # accanto ai playbook: comune a TUTTI gli ambienti
  all/...
  mountpoints.yml                 # cvmfs + autofs legacy
inventories/
  dev/
    inventory
    group_vars/
      all/                        # variabili di tutto l'ambiente dev
        vars.yml                  # env, galaxy_public_hostname, internal_ca_*, ...
        gxconfig.yml              # configurazione di Galaxy
        mountpoints.yml           # mountpoint di cineca + galaxy_data_path
        database.yml
      usegalaxy_it.yml            # variabili del gruppo usegalaxy_it
      rabbitmq.yml
      htcondor_cm.yml
      ...
  prod/
    (stessa struttura, valori di prod)
secret_group_vars/                # file cifrati con ansible-vault
```

## Dove mettere una variabile

| La variabile è...                                  | Dove va                                         |
|----------------------------------------------------|-------------------------------------------------|
| uguale in tutti gli ambienti e mai sovrascritta    | `group_vars/` accanto ai playbook               |
| diversa tra dev e prod, valida per tutte le VM     | `inventories/<env>/group_vars/all/`             |
| diversa tra dev e prod, valida per un solo gruppo  | `inventories/<env>/group_vars/<gruppo>.yml`     |
| un default che un ambiente può sovrascrivere       | `roles/<ruolo>/defaults/main.yml`               |

### Attenzione alla precedenza

Ansible carica **sia** i `group_vars/` accanto al playbook **sia** quelli
dell'inventory. Se la stessa variabile è definita in entrambi, l'ordine è
(dal più debole al più forte):

1. `inventories/<env>/group_vars/all`
2. `group_vars/all` accanto al playbook
3. `inventories/<env>/group_vars/<gruppo>`
4. `group_vars/<gruppo>` accanto al playbook

Quindi, a parità di livello, **vince il file accanto al playbook**.
Regola pratica: nei `group_vars/` accanto ai playbook metti solo variabili che
**non** esistono negli inventory.

`group_vars/` accanto al playbook viene letto solo se il playbook sta nella
root del repository. I comandi ad-hoc (`ansible`, `ansible-inventory`) lo leggono
solo se lanciati dalla root del repository.

## Variabili "neutre"

Per non avere due playbook quasi uguali, le differenze tra ambienti sono
espresse con variabili che hanno **lo stesso nome** in dev e in prod:

| Variabile                | A cosa serve                                                        |
|--------------------------|---------------------------------------------------------------------|
| `env`                    | `dev` o `prod`, per le poche condizioni davvero legate all'ambiente |
| `galaxy_public_hostname` | nome pubblico con cui si raggiunge Galaxy                           |
| `galaxy_data_path`       | path della share dati (es. `cineca.cineca01.path` in dev)           |
| `galaxy_share_path`      | cartella che contiene i dataset, `tus`, ecc.: `/data/share` in tutti e due gli ambienti |
| `galaxy_server_path`     | path di `/opt/galaxy` (codice e venv di Galaxy)                     |
| `db_secrets_file`        | file vault con i segreti del database                               |
| `rabbit_secrets_file`    | file vault con i segreti di RabbitMQ                                |
| `os_env_umask`           | umask usata da `os_hardening` (vedi sotto)                          |

Esempio: `miniconda.yml` usa solo `galaxy_data_path`, e ogni inventory decide a
cosa punta:

```yaml
# inventories/dev/group_vars/all/mountpoints.yml
galaxy_data_path: "{{ cineca.cineca01.path }}"

# inventories/prod/group_vars/all/mountpoints.yml
galaxy_data_path: "{{ cnr.cnr01.path }}"
```

### `galaxy_data_path` e `galaxy_share_path`

I mountpoint dei due ambienti non sono allo stesso livello:

| | `galaxy_data_path` | dove stanno i dataset |
|---|---|---|
| prod | `/data` (`cnr.cnr01.path`) | `/data/share/...` |
| dev | `/data/share` (`cineca.cineca01.path`) | `/data/share/...` |

Per questo i template che costruiscono percorsi sotto `share/` (object store,
upload di tus) usano `galaxy_share_path`, che punta in entrambi gli ambienti
alla stessa cartella:

```yaml
# inventories/prod/group_vars/all/mountpoints.yml
galaxy_share_path: "{{ cnr.cnr01.path }}/share"

# inventories/dev/group_vars/all/mountpoints.yml
galaxy_share_path: "{{ cineca.cineca01.path }}"
```

Usare `galaxy_data_path` più `/share` in un template condiviso produce in dev
`/data/share/share/...`.

`templates/galaxy/config/object_store_conf.yml.j2` è condiviso tra gli ambienti:
ogni variabile che usa deve esistere in **tutti** gli inventory.

### `inventory_hostname` e `galaxy_public_hostname`

Nel vecchio setup ogni VM aveva un IP pubblico e un nome DNS, e il nome
dell'host nell'inventory coincideva con il nome pubblico. Molte configurazioni
usavano `inventory_hostname` come URL. Ora le VM hanno nomi interni e il nome
pubblico è uno solo, quindi le due cose vanno tenute separate:

| | `inventory_hostname` | `galaxy_public_hostname` |
|---|---|---|
| definita da | Ansible (nome nel file `inventory`) | noi, in `group_vars/all/vars.yml` |
| esempio dev | `usegalaxy-galaxy` | `131-175-80-230.sslip.io` |
| risolve nel DNS | no | sì |
| certificato pubblico | no | sì |

Regola:
- serve **identificare una VM** → `inventory_hostname`;
- serve **un indirizzo raggiungibile o un certificato pubblico** (URL, certbot,
  callback, hook) → `galaxy_public_hostname`.

Per trovare gli URL costruiti ancora con il nome interno:

```bash
rg -n "https?://\{\{ *(inventory_hostname|hostname)" . --glob '!roles/**'
```

## Condizioni legate all'ambiente

Quando un task deve girare solo in un ambiente, usare `env`:

```yaml
when: env == 'dev'
```

Le vecchie condizioni sul suffisso dei gruppi
(`"'_dev' in group_names | join(',')"`) non funzionano più, perché i gruppi
hanno lo stesso nome in tutti gli inventory.

Quando la condizione riguarda una funzione e non l'ambiente, meglio una
variabile dedicata (es. `when: manage_firewalld | default(false)`).

## Trappole incontrate

- **File mancanti in `vars_files` vengono saltati senza errore.** Un nome sbagliato
  si manifesta più avanti come variabile `undefined`.
- **`vars_files` con variabili** (es. `"{{ db_secrets_file }}"`) stampa un warning
  `skipping vars_files item due to an undefined variable`: è normale, viene dal
  primo passaggio di Ansible prima di conoscere gli host.
- **Un file in `group_vars/` viene caricato solo se esiste un gruppo con lo stesso
  nome.** `group_vars/secrets.yml` non viene mai letto se non esiste il gruppo
  `secrets`. Per più file dello stesso gruppo usare una cartella
  (`group_vars/<gruppo>/vars.yml`, `group_vars/<gruppo>/vault.yml`).
- **`mode` va sempre tra virgolette con lo zero iniziale.** `mode: 755` viene letto
  come numero decimale e produce permessi `1363`. Scrivere `mode: "0755"`.
- **Liste e stringhe.** Se un ruolo si aspetta una lista (es. `certbot_domains`),
  `certbot_domains: "nome"` è sbagliato. Serve:
  ```yaml
  certbot_domains:
    - "{{ galaxy_public_hostname }}"
  ```
- **Condizioni `when` come dizionario.** `when: ansible_os_family: RedHat` era
  tollerato dalle vecchie versioni di Ansible ma da ansible-core 2.19 dà errore.
  Forma corretta: `when: ansible_facts.os_family == 'RedHat'`.
- **Template con nomi di ambiente scritti a mano.** Un template condiviso non deve
  contenere riferimenti diretti a un ambiente (es. `cnr.cnr01.path`): in dev quella
  variabile non esiste. Usare una variabile neutra definita in ogni inventory.
- **umask di `os_hardening`.** L'hardening rende restrittiva la umask, e i pacchetti
  installati da root nel venv di Galaxy diventavano illeggibili per l'utente
  `galaxy` (`PermissionError` all'avvio di gunicorn). In dev è impostato
  `os_env_umask: "022"`. La umask agisce solo sui file creati dopo: per i file
  già esistenti serve una volta `chmod -R a+rX /opt/galaxy/venv`.

## Verifiche utili

```bash
# struttura e variabili di un ambiente
ansible-inventory -i inventories/dev --graph --vars

# valore di una variabile su un gruppo
ansible -i inventories/dev usegalaxy_it -m debug -a "var=galaxy_data_path"

# confronto delle variabili risolte prima/dopo una modifica
ansible-inventory -i inventories/dev --list > /tmp/dev.json
```
