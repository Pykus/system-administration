# Grafana on Windows — local dashboard runbook

This runbook installs Grafana on Windows as a local observability UI and connects it to a Prometheus instance running on the same host.

The example uses localhost only and contains no production infrastructure data.

## Layout

~~~text
C:\Observability\
  grafana\
    bin\
    conf\
    data\
    logs\
    provisioning\
~~~

## Download and install

Use the current stable Windows build from the official Grafana download page:

~~~text
https://grafana.com/grafana/download
~~~

Grafana supports a Windows installer and a standalone ZIP. For a portable lab installation, the ZIP is convenient because the full deployment can live under `C:\Observability\grafana`.

When using the ZIP:

1. Extract it.
2. Copy `conf\sample.ini` to `conf\custom.ini`.
3. Change only `custom.ini`; do not edit `defaults.ini`.

## Local-only configuration

Example `conf\custom.ini`:

~~~ini
[server]
http_addr = 127.0.0.1
http_port = 3000
domain = localhost
root_url = http://127.0.0.1:3000/

[paths]
data = C:/Observability/grafana/data
logs = C:/Observability/grafana/logs
provisioning = C:/Observability/grafana/conf/provisioning

[analytics]
reporting_enabled = false
check_for_updates = true

[users]
allow_sign_up = false
~~~

Start manually:

~~~powershell
Set-Location C:\Observability\grafana
.\bin\grafana-server.exe --config .\conf\custom.ini --homepath .
~~~

Open locally: `http://127.0.0.1:3000/`

Change the default administrator password immediately after first login.

## Prometheus data source

Create a Prometheus data source pointing at `http://127.0.0.1:9090`.

Example provisioning file:

~~~yaml
apiVersion: 1

datasources:
  - name: Prometheus
    uid: prometheus-local
    type: prometheus
    access: proxy
    url: http://127.0.0.1:9090
    isDefault: true
    editable: true
~~~

Save under `conf\provisioning\datasources\prometheus.yml`, then restart Grafana.

## First operations dashboard

A useful first dashboard should answer whether the application is available, whether monitored systems and integrations are healthy, and whether automated actions succeed.

Suggested queries:

Request rate:
~~~promql
sum(rate(app_http_requests_total[5m]))
~~~

Error ratio:
~~~promql
sum(rate(app_http_errors_total[5m])) / sum(rate(app_http_requests_total[5m]))
~~~

95th percentile request latency:
~~~promql
histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[5m])))
~~~

Online/offline systems:
~~~promql
app_hosts_online
app_hosts_offline
~~~

Open incidents:
~~~promql
app_open_incidents
~~~

Integration health:
~~~promql
app_external_source_up
~~~

Automation failures:
~~~promql
sum by (action) (increase(app_action_failures_total[1h]))
~~~

## Windows startup

Grafana's Windows documentation supports the Windows installer or standalone server. For a ZIP deployment, a Scheduled Task is also suitable for a workstation/lab:

~~~powershell
$exe = 'C:\Observability\grafana\bin\grafana-server.exe'
$args = '--config C:\Observability\grafana\conf\custom.ini --homepath C:\Observability\grafana'
$action = New-ScheduledTaskAction -Execute $exe -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Register-ScheduledTask -TaskName 'Grafana' -Action $action -Trigger $trigger -Principal $principal -Settings $settings
~~~

## Security

- bind to `127.0.0.1` unless remote access is explicitly required;
- disable public sign-up;
- change the default administrator password;
- never export dashboard JSON containing secrets;
- keep private data-source credentials outside Git;
- prefer a reverse proxy with authentication if Grafana is later published remotely.

## Upgrade and rollback

Back up `conf\custom.ini`, `data\`, and provisioning before upgrades. Keep the previous binary directory until login, Prometheus data source, and key dashboard checks pass.