# Prometheus on Windows — local monitoring runbook

This runbook installs Prometheus on a Windows host in a self-contained directory, binds it to localhost, and configures it to scrape a local application that exposes a Prometheus-compatible `/metrics` endpoint.

The example intentionally uses only neutral hostnames and localhost addresses. Do not publish production hostnames, internal addresses, credentials, tokens, or inventory.

## Layout

```text
C:\Observability\
  prometheus\
    prometheus.exe
    promtool.exe
    prometheus.yml
    data\
    logs\
```

## Download

Download the current Windows amd64 ZIP from the official Prometheus download page:

```text
https://prometheus.io/download/
```

Verify the SHA256 checksum published on the download page before extraction.

Example PowerShell verification:

```powershell
Get-FileHash .\prometheus-<version>.windows-amd64.zip -Algorithm SHA256
```

## Minimal configuration

Save as `C:\Observability\prometheus\prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets:
          - 127.0.0.1:9090

  - job_name: app
    metrics_path: /metrics
    static_configs:
      - targets:
          - 127.0.0.1:8080
```

Validate before starting:

```powershell
C:\Observability\prometheus\promtool.exe check config C:\Observability\prometheus\prometheus.yml
```

## Start manually

```powershell
C:\Observability\prometheus\prometheus.exe `
  --config.file=C:\Observability\prometheus\prometheus.yml `
  --storage.tsdb.path=C:\Observability\prometheus\data `
  --web.listen-address=127.0.0.1:9090
```

Open locally:

```text
http://127.0.0.1:9090/
```

Useful checks:

```powershell
Invoke-RestMethod http://127.0.0.1:9090/-/healthy
Invoke-RestMethod http://127.0.0.1:9090/api/v1/targets
```

## Windows startup

For a lab or workstation, a Scheduled Task is sufficient and avoids adding another service wrapper.

Example action:

```powershell
$exe = 'C:\Observability\prometheus\prometheus.exe'
$args = '--config.file=C:\Observability\prometheus\prometheus.yml --storage.tsdb.path=C:\Observability\prometheus\data --web.listen-address=127.0.0.1:9090'

$action = New-ScheduledTaskAction -Execute $exe -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable

Register-ScheduledTask -TaskName 'Prometheus' -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

## Application metrics

A useful first set for a small operations application:

```text
app_http_requests_total
app_http_request_duration_seconds
app_http_errors_total
app_hosts_total
app_hosts_online
app_hosts_offline
app_open_incidents
app_external_source_up{source="..."}
app_action_requests_total{action="..."}
app_action_failures_total{action="..."}
```

Avoid high-cardinality labels such as usernames, ticket IDs, request IDs, host serial numbers, or arbitrary URLs.

Good labels are small bounded sets:

```text
source
action
status
method
endpoint
severity
```

## Example PromQL

Requests per second:

```promql
sum(rate(app_http_requests_total[5m]))
```

HTTP error ratio:

```promql
sum(rate(app_http_errors_total[5m]))
/
sum(rate(app_http_requests_total[5m]))
```

Offline systems:

```promql
app_hosts_offline
```

External integration health:

```promql
app_external_source_up
```

## Upgrade

1. Stop the Scheduled Task.
2. Back up `prometheus.yml`.
3. Replace the binaries with a verified release.
4. Run `promtool check config`.
5. Start the task.
6. Verify `/-/healthy`, `/api/v1/targets`, and a sample query.

Do not delete the TSDB directory during a normal upgrade.

## Rollback

Keep the previous Prometheus directory or binaries until the new version has passed health and scrape-target checks. Roll back by restoring the old binaries and restarting the Scheduled Task.
