# Monitoring: Telegraf, InfluxDB, Grafana

Questo documento descrive lo stack di monitoring di usegalaxy.it, come è
organizzato nel repo e cosa serve per portarlo dal dev (CINECA, OpenStack)
alla prod (CNR, Proxmox).

## Architettura

```
 VM monitorate                 InfluxDB                     Grafana
 (Galaxy, DB, HTCondor, ...)   (dev: privato, prod: VPN)    (pubblico)

 Telegraf ── HTTPS :8086 ───▶  influxdb:1.8 (Docker)  ◀── HTTPS :8086 ──  Grafana
   metriche di sistema         database "galaxy", ...                    + PostgreSQL locale
   statsd di Galaxy                                                       + nginx (443)
```

- **Telegraf** gira su ogni VM monitorata e scrive ogni 10 s nel database
  `galaxy` di InfluxDB. Ogni punto ha il tag `host` con il nome dell'host
  nell'inventory: è così che in Grafana si distinguono le macchine.
- **InfluxDB 1.8** gira in un container Docker, con i dati su un disco dedicato
  montato su `/data`. È raggiungibile solo dalla rete interna (dev) o dalla VPN
  (prod, come RabbitMQ): il suo certificato TLS è firmato dalla **CA interna**.
- **Grafana** gira come pacchetto di sistema (servizio `grafana-server`), ascolta
  solo su `127.0.0.1:3000` e sta dietro nginx. Il suo database (utenti,
  dashboard, alert) è un PostgreSQL locale sulla stessa VM.

## Playbook e file

| File | Cosa fa |
|---|---|
| `trust_ca.yml` | Crea la CA interna sulla macchina che lancia Ansible (se manca) e la installa nel trust store di tutti gli host. Su host con Telegraf già attivo lo riavvia. |
| `trust_internal_ca.yml` | Task incluso dagli altri playbook: stessa cosa su un singolo host. Funziona su RHEL e su Debian/Ubuntu. |
| `roles-local/internal_tls/` | Ruolo che firma con la CA interna il certificato di un servizio. `tasks/ca.yml` contiene solo la creazione della CA. |
| `influxdb.yml` | VM InfluxDB: disco dati, Docker, nginx, container InfluxDB, Telegraf, hardening. |
| `telegraf.yml` | Telegraf sulle VM monitorate. La riga `hosts` decide quali. |
| `grafana.yml` | VM Grafana: PostgreSQL, nginx, Grafana, hardening. |

I playbook sono **uguali per dev e prod**. Tutto quello che cambia sta
nell'inventory (`inventories/<env>/`) e nei segreti.

## Dove stanno le variabili

| Cosa | File |
|---|---|
| Percorso della CA interna e file dei segreti | `inventories/<env>/group_vars/all/vars.yml` (`internal_ca_dir`, `internal_ca_cn`, `monitoring_secrets_file`) |
| Segreti del monitoring | `secret_group_vars/monitoring-<env>.yml` (vault) |
| InfluxDB | `inventories/<env>/group_vars/influxdb.yml` |
| Grafana | `inventories/<env>/group_vars/grafana.yml` |
| Configurazione comune di Telegraf (output, plugin di sistema) | `group_vars/all/all.yml` |
| Plugin Telegraf in più per un gruppo | `telegraf_plugins_extra` nei `group_vars` di quel gruppo (es. statsd in `usegalaxy_it.yml`) |

Struttura del file dei segreti:

```yaml
influxdb:
  url: <IP o nome di InfluxDB, senza porta>
  admin:   { username: admin,    password: ... }
  grafana: { username: grafana,  password: ... }
  node:    { username: telegraf, password: ... }

grafana_secrets:
  admin_user: admin
  admin_password: ...
  secret_key: ...        # openssl rand -hex 32
  db_password: ...
  # solo se si usa il login GitHub:
  # github_client_id: ...
  # github_client_secret: ...
```

`influxdb.url` va scritto **senza porta**: il ruolo di InfluxDB lo usa anche come
`-host` del client `influx`. La porta `:8086` viene aggiunta nella configurazione
di Telegraf e delle datasource di Grafana.

### Differenze tra dev e prod

| | dev | prod |
|---|---|---|
| Rete di InfluxDB | rete privata | IP pubblico, accessibile solo via VPN (come RabbitMQ) |
| Certificato InfluxDB | `internal_tls` | `internal_tls` |
| Certificato Grafana | `internal_tls` | `usegalaxy-eu.certbot` |
| Accesso a Grafana | proxy della control, porta 3443 | IP e nome pubblici |
| Accesso anonimo (sola lettura) | spento | acceso |
| Disco dati InfluxDB (`influxdb_data_device`) | `/dev/vdb` | da verificare con `lsblk` (su Proxmox con VirtIO SCSI è `/dev/sdb`) |

## CA interna

La CA serve per i servizi che **non sono raggiungibili da internet** (rete
privata o solo VPN), e quindi non possono ottenere un certificato Let's Encrypt
con la validazione HTTP: oggi InfluxDB, e in dev anche RabbitMQ e Grafana.

- I file `ca.key` e `ca.crt` stanno in `internal_ca_dir`, sulla macchina che
  lancia Ansible (in dev la control, in prod il nodo Jenkins di prod).
- Viene creata **da sola** la prima volta che gira `trust_ca.yml`,
  `prepare_node.yml` o un playbook che usa `internal_tls`.
- **Una CA per ambiente**: quella di dev non va usata in prod.
- `ca.key` è un segreto: va tenuto fuori dal repo, con permessi `0600`, e ne va
  fatto un backup.
- Chi deve fidarsi della CA: tutte le VM con Telegraf e la VM di Grafana. Il
  trust store di sistema si somma alle CA pubbliche, quindi gli stessi client
  continuano ad accettare i certificati Let's Encrypt.
- I client che girano dentro un container non vedono il trust store dell'host:
  se devono parlare con un servizio interno, la CA va montata nel container.

## Ordine di deploy

### dev

1. `prepare_node.yml --limit <nuove VM>` (installa anche la CA)
2. `influxdb.yml`
3. `telegraf.yml`
4. `grafana.yml`
5. `proxy.yml`, per esporre Grafana sulla 3443 della control

### prod

> **In prod non si lancia `prepare_node.yml`.** È pensato per le VM cloud del
> dev (remap dell'utente `galaxy`, autofs): su CNR farebbe danni.

1. `trust_ca.yml -i inventories/prod`
2. `influxdb.yml -i inventories/prod`
3. `telegraf.yml -i inventories/prod`
4. `grafana.yml -i inventories/prod`

`influxdb.yml` e `grafana.yml` installano da soli le dipendenze che servono,
e `telegraf.yml` installa la CA nei suoi pre_tasks.

## Accesso a Grafana in dev

La VM di Grafana non ha un IP pubblico. Il proxy stream della control inoltra la
porta 3443 alla 443 della VM (`inventories/dev/group_vars/proxy.yml`):

```yaml
  - name: grafana
    listen: 3443
    backend_group: grafana
    backend_port: 443
```

La porta è aperta dal security group `grafana-dev`, attaccato alla control.
Per chiuderla basta staccare il gruppo:

```bash
openstack server remove security group galaxy_gaia.control grafana-dev
```

Il certificato è firmato dalla CA interna: il browser lo segnala finché non si
importa `ca.crt` tra le autorità fidate.

## Verifiche

Telegraf sulle VM:

```bash
ansible <gruppi> -b -m shell -a "systemctl is-active telegraf"
ansible <gruppi> -b -m shell -a "journalctl -u telegraf --since '5 min ago' --no-pager | grep ' E! ' || echo OK"
```

Dati in InfluxDB (dal client nel container):

```
USE galaxy
SHOW TAG VALUES FROM cpu WITH KEY = "host"
SELECT last(usage_idle) FROM cpu WHERE time > now() - 2m GROUP BY host
```

Grafana:

```bash
ansible grafana -b -m shell -a "systemctl is-active grafana-server nginx postgresql-18"
ansible grafana -b -m shell -a "curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/login"
```

In Grafana: *Connections → Data sources → Galaxy → Save & test*.

## Datasource di Grafana

Sono definite in `grafana_datasources` e scritte dal ruolo in un file di
provisioning: non si modificano dall'interfaccia. Ognuna punta a un database di
InfluxDB:

| Datasource | Database | Contenuto |
|---|---|---|
| Galaxy | `galaxy` | metriche di sistema delle VM e statsd di Galaxy |
| InfluxDB - internal | `_internal` | statistiche di InfluxDB stesso |
| Galaxy Historical | `galaxy_stats` | statistiche di Galaxy (da attivare) |
| GRT Tool Usage | `grt` | uso dei tool (da attivare) |
| Notifications | `notifications` | notifiche (da attivare) |

Gli `uid` sono fissi: le dashboard esportate in JSON li usano per trovare la
datasource, e devono restare uguali tra dev e prod.

## Metriche di Galaxy

- **Tempi delle pagine (statsd)**: attivo. Galaxy manda i tempi a
  `127.0.0.1:8125` (`statsd_*` in `gxconfig.yml`), Telegraf li riceve con il
  plugin `statsd` definito in `inventories/<env>/group_vars/usegalaxy_it.yml`.
  La misura in InfluxDB si chiama `galaxy_page_timings.`, con il punto finale:
  con `statsd_influxdb: true` il percorso della pagina va in un tag e il nome
  resta solo prefisso + separatore. Nelle query va scritto tra virgolette
  doppie (`FROM "galaxy_page_timings."`). I campi utili sono `mean`,
  `90_percentile` e `count`.
- **Job, code, utenti (`galaxy_stats`)**, **uso dei tool (`grt`)**,
  **notifiche (`notifications`)**: da decidere quali attivare. Nel playbook di
  Galaxy c'è commentato `usegalaxy-eu.galaxy-slurp`, con le variabili già
  impostate.

## Checklist prima di prod

- [ ] VM InfluxDB con IP pubblico raggiungibile solo via VPN, con disco dati da 100 GB
- [ ] VM Grafana con IP pubblico, record DNS, porte 80 e 443 aperte
- [ ] Gruppi `[influxdb]` e `[grafana]` in `inventories/prod/inventory`
- [ ] `internal_ca_dir`, `internal_ca_cn`, `monitoring_secrets_file` in `inventories/prod/group_vars/all/vars.yml`
- [ ] `secret_group_vars/monitoring-prod.yml` (vault), con `influxdb.url` = indirizzo con cui le VM raggiungono InfluxDB attraverso la VPN
- [ ] `influxdb_data_device` di prod verificato con `lsblk`
- [ ] Se `influxdb.url` è un nome, aggiungerlo a `internal_tls_sans` di InfluxDB
- [ ] Nome pubblico di Grafana in `inventories/prod/group_vars/grafana.yml`
- [ ] Metodo di login di Grafana deciso (Keycloak, GitHub o utenti locali)
- [ ] Gruppi da monitorare nella riga `hosts` di `telegraf.yml`
- [ ] Backup di `ca.key` di prod e del PostgreSQL di Grafana
- [ ] Dashboard salvate come JSON nel repo (`files/grafana/dashboards/`)
