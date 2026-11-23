# Reverse proxy, certificati e CA interna (dev)

Questo documento descrive come l'ambiente di sviluppo è esposto su internet con
un solo IP pubblico, come sono gestiti i certificati e come comunicano i servizi
interni.

## Architettura

Nella cloud CINECA c'è **un solo floating IP**, assegnato alla macchina di
controllo (`control-galaxy`). Su quella macchina gira un reverse proxy nginx che
inoltra il traffico alle VM interne.

```
internet → control-galaxy (131.175.80.230, nginx "stream", solo TCP)
             :80   → Galaxy:80     certbot + redirect https
             :443  → Galaxy:443    Galaxy
             (5671 e 9443 predisposte ma chiuse)

rete privata 192.168.0.0/24
  Galaxy   192.168.0.30  ──TLS 5671──▶  RabbitMQ 192.168.0.113
  Celery   192.168.0.126 ──TLS 5671──▶  RabbitMQ
  HTCondor CM 192.168.0.143, exec, NFS 192.168.0.219, database, ...
```

Il proxy lavora a livello **TCP** (modulo `stream` di nginx): non decifra il
traffico e non contiene certificati. Il TLS viene gestito dalle VM che servono
i servizi.

## Il proxy

File:

- `proxy.yml`: il playbook;
- `templates/proxy/nginx.conf.j2`: la configurazione completa di nginx;
- `inventories/dev/group_vars/proxy.yml`: le porte da inoltrare.

La macchina di controllo è nel gruppo `proxy` dell'inventory, con
`ansible_connection=local`.

Le porte si configurano solo con la lista `proxy_streams`:

```yaml
proxy_streams:
  - name: galaxy_http
    listen: 80
    backend_group: usegalaxy_it    # si usa il primo host del gruppo
    backend_port: 80
  - name: galaxy_https
    listen: 443
    backend_group: usegalaxy_it
    backend_port: 443
```

Per aggiungere un servizio basta un nuovo elemento della lista e rilanciare
`ansible-playbook proxy.yml`. Gli IP dei backend vengono dall'inventory.

Note:

- il playbook funziona sia su Ubuntu (macchina di controllo) sia su RHEL/Alma;
- il template sostituisce tutto `/etc/nginx/nginx.conf` e **non** contiene un
  blocco `http`: su quella macchina nginx fa solo da proxy TCP;
- `proxy_timeout 1h` evita che connessioni lunghe (websocket, AMQP) vengano chiuse;
- il log per connessione è in `/var/log/nginx/stream_access.log`
  (`200` = ok, `502` = backend irraggiungibile).

Security group: alla macchina di controllo è associato `public-web`
(80, 443, 8080). La 8080 non è usata.

## Certificati

| Dove | Certificato | Chi lo gestisce |
|---|---|---|
| Galaxy (443, pubblico) | Let's Encrypt | `usegalaxy-eu.certbot` sulla VM di Galaxy |
| RabbitMQ (5671 e pagina di gestione) | firmato dalla **CA interna** | ruolo `internal_tls` |

### Certificato pubblico di Galaxy

- Il nome pubblico è la variabile `galaxy_public_hostname`.
- Finché CINECA non assegna il nome definitivo si usa `131-175-80-230.sslip.io`,
  un nome DNS pubblico che risolve nell'IP indicato nel nome stesso.
- `certbot_domains` deve contenere **solo** il nome pubblico (Let's Encrypt
  rifiuta i nomi interni):
  ```yaml
  certbot_domains:
    - "{{ galaxy_public_hostname }}"
  ```
- nginx usa sempre `/etc/ssl/certs/fullchain.pem`; lo script post-renewal di
  certbot ci copia il certificato di `certbot_domains[0]`.

**Quando arriva il nome definitivo:**

1. creare il record DNS verso il floating IP e verificarlo con `dig +short <nome>`;
2. cambiare `galaxy_public_hostname`;
3. rilanciare il playbook di Galaxy;
4. aggiornare i redirect URI del client Galaxy in Keycloak;
5. cancellare il vecchio certificato: `certbot delete --cert-name 131-175-80-230.sslip.io`.

### CA interna

RabbitMQ non ha un nome pubblico, quindi Let's Encrypt non può rilasciargli un
certificato. Per il traffico interno si usa una piccola CA gestita con Ansible.

- La CA sta sulla macchina di controllo in `internal_ca_dir`
  (`/root/usegalaxy-internal-ca/dev/`): `ca.key` (segreta) e `ca.crt` (pubblica).
- **Fare il backup di `ca.key`.** Senza, per rinnovare va rigenerata la CA e
  ridistribuita a tutti i client.
- La CA vale 10 anni, i certificati dei server 2 anni: per rinnovarli basta
  rilanciare il playbook.

#### Ruolo `internal_tls`

`roles/internal_tls/` genera la chiave **sulla VM** (non lascia mai la macchina),
la fa firmare dalla CA sulla macchina di controllo e installa i file **negli stessi
percorsi che usava certbot**:

| File | Uso |
|---|---|
| `/etc/ssl/certs/cert.pem` | certificato del server (RabbitMQ) |
| `/etc/ssl/certs/fullchain.pem` | certificato + CA (nginx, RabbitMQ `cacertfile`) |
| `/etc/ssl/certs/internal-ca.pem` | solo la CA |
| `/etc/ssl/user/privkey-<utente>.pem` | chiave, una copia per ogni utente |

Il ruolo **non** si chiama dal playbook: è agganciato al ruolo
`galaxyproject.nginx` al posto di certbot.

```yaml
# inventories/dev/group_vars/rabbitmq.yml
nginx_ssl_role: internal_tls
internal_tls_sans:
  - "DNS:{{ inventory_hostname }}"
  - "IP:{{ ansible_host }}"
internal_tls_key_users:
  - nginx
  - { name: rabbitmq, owner: "999" }   # UID di rabbitmq dentro il container
```

Perché `nginx_ssl_role`: quando ci sono server HTTPS (`nginx_ssl_servers`),
`galaxyproject.nginx` esegue il ruolo indicato in `nginx_ssl_role` per procurarsi
i certificati. Se la variabile non è definita prova invece a copiarli dal repo
(`files/ssl/`), e fallisce.

`owner: "999"`: RabbitMQ gira in un container il cui utente ha UID 999, diverso
dall'utente `rabbitmq` dell'host (UID 1999). La chiave deve appartenere all'UID
del container, altrimenti RabbitMQ non parte
(`ssl_options.keyfile invalid ... cannot be read`).

Le variabili `internal_ca_dir` e `internal_ca_cn` stanno in
`inventories/dev/group_vars/all/vars.yml`.

#### Client: fidarsi della CA

Chi si collega a RabbitMQ deve fidarsi della CA. `trust_internal_ca.yml` copia
`ca.crt` in `/etc/pki/ca-trust/source/anchors/` ed esegue `update-ca-trust`.

Va incluso nei **`pre_tasks`** (non nei `post_tasks`) dei playbook dei client:
Galaxy deve fidarsi della CA prima che i suoi servizi partano, altrimenti
l'handler `Restart Galaxy` resta bloccato in attesa di un gunicorn che non parte.

```yaml
  pre_tasks:
    - name: Trust internal CA
      ansible.builtin.include_tasks: trust_internal_ca.yml
```

Oggi è incluso in: `usegalaxy_it_dev.yml`, `celerycluster_dev.yml`,
`prepare_node.yml`.

## RabbitMQ

- Ascolta **solo** in TLS sulla 5671 (`listeners: tcp: none`).
- Galaxy, Celery e Flower si collegano con URL `...:5671/...?ssl=1`.
- La libreria usata da Galaxy (`py-amqp`) verifica che il certificato sia firmato
  da una CA fidata, ma **non** controlla il nome.
- `rabbitmq_dev.yml`: certbot rimosso, utenti `rabbitmq` (UID 1999) e `nginx`
  creati nei `pre_tasks` prima dei ruoli, `initscripts-service` installato
  (serve a `os_hardening` per riavviare auditd).
- Su rabbit, nginx serve la **pagina di gestione** di RabbitMQ (443 → 15672),
  non il traffico AMQP.

Il nome dell'host di rabbit nell'inventory è ancora quello del vecchio setup
(`rabbitmq-usegalaxy-it...`). `rabbitmq_url` deve corrispondere a uno dei SAN
del certificato (nome dell'inventory o IP).

## Galaxy: note legate al proxy

- **Hook di tusd.** tusd riceve gli upload e poi avvisa Galaxy tramite un hook
  HTTPS. L'URL usa il nome pubblico:
  ```yaml
  - "-hooks-http=https://{{ galaxy_public_hostname }}/api/upload/hooks"
  ```
- **`/etc/hosts` sulla VM di Galaxy.** Il nome pubblico viene risolto localmente,
  così le chiamate che Galaxy fa a se stessa (es. gli hook di tusd) non escono su
  internet per rientrare dal proxy, e il certificato resta valido:
  ```yaml
  - name: Resolve public hostname locally (tusd hooks)
    ansible.builtin.lineinfile:
      path: /etc/hosts
      line: "127.0.0.1 {{ galaxy_public_hostname }}"
  ```

## Lavori aperti

- Pagina di gestione di RabbitMQ su `https://<nome>:9443`, servita dall'nginx di
  Galaxy (che ha il certificato pubblico) e inoltrata a rabbit.
- Flower sotto `https://<nome>/flower` tramite l'nginx di Galaxy.
- Keycloak sotto `https://<nome>/auth`.
