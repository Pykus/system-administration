# Diagnostyka Harmonogramu zadań Windows i weryfikacja wykonania

## Cel

Harmonogram zadań Windows uruchamia skrypty, raporty i procesy administracyjne w określonych terminach. Jego status „Gotowe” nie oznacza, że ostatnie uruchomienie się powiodło. Nawet kod zakończenia 0 nie potwierdza, że program zapisał prawidłowy wynik. Skuteczna diagnostyka rozdziela trzy zdarzenia: zadanie zostało zaplanowane, proces został uruchomiony, oczekiwany rezultat powstał i został zweryfikowany.

Poniższe techniki dotyczą Windows Server i Windows 10/11 z Windows PowerShell 5.1 oraz modułem ScheduledTasks. Przykłady są odczytowe względem konfiguracji zadań. Przydają się do nocnych raportów, synchronizacji plików, uruchamiania workerów, kontroli kopii zapasowych i okresowych skryptów administracyjnych.

## Kiedy stosować, a kiedy wybrać inne narzędzie

Używaj Harmonogramu dla przewidywalnych lokalnych uruchomień o znanej częstotliwości. Sprawdzaj go, kiedy zadanie działa ręcznie, ale nie działa automatycznie, zwraca kod błędu, uruchamia się z opóźnieniem albo tworzy nieaktualne wyniki.

Nie traktuj go jako transakcyjnej kolejki: sam nie zapewnia niezawodnej deduplikacji, rozproszonej blokady, gwarantowanego dostarczenia ani potwierdzenia przetworzenia każdej wiadomości. Dla krytycznych integracji użyj trwałych checkpointów, idempotencji i monitoringu zewnętrznego. Nie naprawiaj problemów przez automatyczne podnoszenie uprawnień lub umieszczanie haseł w plikach skryptów.

## Odczyt definicji zadania

Najpierw poznaj pełną ścieżkę zadania i jego nazwę. Ścieżka folderu Harmonogramu to nie ścieżka na dysku.

    $name = 'DailyReport'
    $path = '\Operations\'
    $task = Get-ScheduledTask -TaskName $name -TaskPath $path -ErrorAction Stop
    $info = $task | Get-ScheduledTaskInfo

    [pscustomobject]@{
        Name           = $task.TaskName
        Path           = $task.TaskPath
        State          = $task.State
        UserId         = $task.Principal.UserId
        LogonType      = $task.Principal.LogonType
        RunLevel       = $task.Principal.RunLevel
        LastRunTime    = $info.LastRunTime
        NextRunTime    = $info.NextRunTime
        LastTaskResult = $info.LastTaskResult
        MissedRuns     = $info.NumberOfMissedRuns
    } | Format-List

    $task.Actions  | Format-List Execute,Arguments,WorkingDirectory
    $task.Triggers | Format-List *
    $task.Settings | Format-List *

Wyzwalacz określa planowany czas, akcja wskazuje program i argumenty, a Principal określa konto i kontekst bezpieczeństwa. Poprawny wyzwalacz nie gwarantuje, że konto widzi udział sieciowy albo że ścieżka do skryptu jest prawidłowa.

LastTaskResult równy 0 zwykle oznacza sukces procesu, lecz nie jest dowodem powstania raportu. Wartość 0x41301 oznacza stan wykonywania, nie ukończony sukces. Kod 0x1 często pochodzi z aplikacji i wymaga analizy jej logów. Nie interpretuj wszystkich kodów jako uniwersalnych komunikatów systemowych. LastRunTime z odległej przeszłości lub wartością domyślną wymaga kontroli historii.

## Pełny skrypt audytu wielu zadań

Zapisz poniższy kod jako Get-TaskExecutionAudit.ps1. Skrypt pomija zadania systemowe, zapisuje raport CSV i wyświetla liczbę przypadków wymagających uwagi. Nie zmienia konfiguracji Harmonogramu. Tworzy jedynie lokalny plik wynikowy.

    [CmdletBinding()]
    param(
        [string]$OutputCsv = (Join-Path $PWD 'task-audit.csv'),
        [int]$MaxAgeHours = 26
    )

    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
    $now = Get-Date

    $rows = foreach ($task in Get-ScheduledTask) {
        if ($task.TaskPath -like '\Microsoft\*') { continue }

        try {
            $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -TaskPath $task.TaskPath
            $last = $info.LastRunTime
            $never = ($last.Year -le 2000)
            $stale = (-not $never) -and (($now - $last).TotalHours -gt $MaxAgeHours)

            $status = if ($never) {
                'NEVER_OR_UNKNOWN'
            } elseif ($info.LastTaskResult -ne 0) {
                'NONZERO_RESULT'
            } elseif ($stale) {
                'STALE'
            } else {
                'CHECK_ARTIFACT'
            }

            [pscustomobject]@{
                TaskPath       = $task.TaskPath
                TaskName       = $task.TaskName
                State          = [string]$task.State
                LastRunTime    = $last
                NextRunTime    = $info.NextRunTime
                LastTaskResult = $info.LastTaskResult
                MissedRuns     = $info.NumberOfMissedRuns
                Assessment     = $status
                Error          = ''
            }
        }
        catch {
            [pscustomobject]@{
                TaskPath       = $task.TaskPath
                TaskName       = $task.TaskName
                State          = [string]$task.State
                LastRunTime    = $null
                NextRunTime    = $null
                LastTaskResult = $null
                MissedRuns     = $null
                Assessment     = 'READ_ERROR'
                Error          = $_.Exception.Message
            }
        }
    }

    $rows = @($rows)
    $rows | Sort-Object Assessment,TaskPath,TaskName |
        Export-Csv -Path $OutputCsv -NoTypeInformation -Encoding UTF8
    $rows | Group-Object Assessment | Sort-Object Name |
        Select-Object Name,Count | Format-Table -AutoSize

    Write-Host "Raport: $OutputCsv; liczba zadan: $($rows.Count)"

Uruchom w PowerShell:

    .\Get-TaskExecutionAudit.ps1 -OutputCsv .\task-audit.csv -MaxAgeHours 26

Próg 26 godzin pasuje do zadań dziennych, ale jest błędny dla zadań tygodniowych. Dobieraj próg do SLA konkretnego procesu. Ocena STALE jest sygnałem do kontroli, a nie ostatecznym dowodem awarii. Stan CHECK_ARTIFACT oznacza, że trzeba sprawdzić faktyczny wynik działania.

## Historia zdarzeń

Dziennik Microsoft-Windows-TaskScheduler/Operational zawiera informacje o rozpoczęciu i zakończeniu zadań oraz akcji. Zdarzenia 100 i 102 często dotyczą zadania, a 200 i 201 akcji. Zależnie od wersji systemu i rodzaju awarii pojawiają się także inne identyfikatory; analizuj treść komunikatu.

    $logName = 'Microsoft-Windows-TaskScheduler/Operational'
    $start = (Get-Date).AddHours(-24)

    try {
        Get-WinEvent -FilterHashtable @{
            LogName   = $logName
            StartTime = $start
        } -ErrorAction Stop |
            Where-Object { $_.Message -like '*\Operations\DailyReport*' } |
            Select-Object TimeCreated,Id,LevelDisplayName,Message |
            Format-List
    }
    catch {
        Write-Warning "Brak dostepu do historii: $($_.Exception.Message)"
    }

Dziennik może być wyłączony, zrotowany lub niedostępny z powodu uprawnień. Brak wpisów nie dowodzi braku uruchomienia. Włączenie dziennika jest zmianą konfiguracji i powinno być osobną, kontrolowaną czynnością. Nie publikuj surowych logów bez usunięcia danych osobowych i ścieżek wewnętrznych.

## Trzy rzeczywiste scenariusze

### Zadanie działa ręcznie, lecz nie z Harmonogramu

Porównaj UserId, LogonType, RunLevel, WorkingDirectory, Execute i Arguments. Konto usługi nie musi widzieć dysków mapowanych w sesji użytkownika. Zamiast mapowanego dysku stosuj ścieżkę UNC oraz sprawdź prawa udziału i NTFS. Program powinien używać bezwzględnych ścieżek do plików wejściowych, wyjściowych i logów. Ustal, czy zadanie uruchamia właściwą wersję interpretera i czy argumenty są poprawnie cytowane.

### Zadanie zgłasza kod 0, ale raport jest nieaktualny

Sprawdź czas modyfikacji, rozmiar, strukturę i liczbę rekordów pliku wynikowego. Zapisuj wynik najpierw do pliku tymczasowego, weryfikuj go, a następnie podmieniaj docelowy plik. Po sukcesie twórz checkpoint zawierający czas, status, liczbę rekordów i identyfikator uruchomienia. Monitoring zewnętrzny powinien porównać checkpoint z wymaganym oknem czasowym. Sam kod 0 nie wystarcza.

### Kolejne uruchomienie nakłada się na poprzednie

Sprawdź MultipleInstances, ExecutionTimeLimit, ustawienia ponawiania oraz NumberOfMissedRuns. Dwie instancje mogą nadpisać ten sam plik albo przetworzyć te same rekordy. Stosuj idempotentne operacje, trwały rejestr przetworzonych identyfikatorów i blokadę z czasem wygaśnięcia. Ustawienie „Nie uruchamiaj nowej instancji” pomaga, ale nie zastępuje niezawodnej kolejki.

## Testowanie i kryteria odbioru

1. Uruchom audyt na koncie o standardowych uprawnieniach; zanotuj zadania niewidoczne lub zgłaszające READ_ERROR.
2. Porównaj trzy przykładowe zadania z graficznym Harmonogramem: LastRunTime, NextRunTime i LastTaskResult.
3. Dla wybranego zadania porównaj historię Operational z logiem aplikacji.
4. Zweryfikuj artefakt: świeżość, niepustą zawartość, oczekiwany format i liczbę rekordów.
5. W środowisku testowym zasymuluj brak pliku wejściowego. Proces powinien zakończyć się niezerowym kodem, a checkpoint nie może deklarować sukcesu.
6. Ponów test na tych samych danych: wynik musi być deterministyczny i wolny od podwójnego przetwarzania.

Kryterium sukcesu stanowi zgodność planu, faktycznego uruchomienia, kodu zakończenia i niezależnego dowodu rezultatu. Brak któregoś z elementów oznacz jako niezweryfikowany, nie jako sukces.

## Wnioski praktyczne

Zadanie może być zaplanowane, uruchomione i nadal nieskuteczne. Dlatego monitoring powinien obserwować nie tylko status Harmonogramu, ale też aktualność oraz poprawność plików wynikowych i checkpointów. Diagnostykę zaczynaj od odczytu definicji, zdarzeń i logów. Zmiany konta, uprawnień, triggerów lub retry wdrażaj dopiero po ustaleniu przyczyny i przygotowaniu rollbacku.