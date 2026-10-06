# 07 — Hyper-V Live Migration: Kerberos, delegation, networks and troubleshooting

Hyper-V Live Migration przenosi uruchomioną maszynę wirtualną z jednego hosta Hyper-V na drugi z minimalną przerwą widoczną dla systemu gościa. Funkcja przydaje się przy aktualizacjach hostów, wymianie sprzętu, równoważeniu obciążenia oraz planowanych pracach serwisowych.

Najczęściej nie psuje się samo polecenie Move-VM. Problemy zwykle wynikają z czterech obszarów:

1. uwierzytelnianie i delegowanie,
2. DNS, routing i łączność,
3. niezgodność hostów lub przełączników wirtualnych,
4. błędne założenia dotyczące magazynu i wydajności.

Ten materiał pokazuje nie tylko jak wykonać migrację, ale przede wszystkim jak rozumieć jej zależności i diagnozować awarie.

## 1. Kiedy Live Migration ma sens

Typowe zastosowania:

- restart lub aktualizacja hosta bez długiego wyłączenia maszyny wirtualnej,
- przeniesienie obciążenia ze starszego lub przeciążonego hosta,
- wymiana sprzętu,
- rozłożenie CPU i pamięci między hostami,
- planowane prace w klastrze,
- test procedur migracyjnych i utrzymaniowych.

Live Migration nie zastępuje:

- kopii zapasowej,
- replikacji do innej lokalizacji,
- klastra wysokiej dostępności,
- planu disaster recovery.

Jeżeli oba hosty korzystają z tego samego uszkodzonego storage albo tej samej awarii zasilania, możliwość migracji VM nie rozwiąże problemu.

## 2. Co faktycznie jest przenoszone

Maszyna wirtualna to nie tylko plik VHDX. Migracja musi skoordynować:

- konfigurację VM,
- stan procesora wirtualnego,
- strony pamięci RAM,
- urządzenia wirtualne,
- konfigurację sieciową,
- dyski, jeżeli migracja obejmuje również storage.

Uproszczony przebieg:

~~~text
source host
   |
   | kopiowanie pamięci
   v
destination host
   |
   | ponowne kopiowanie zmienionych stron
   v
krótka finalna synchronizacja
   |
   v
VM kontynuuje pracę na hoście docelowym
~~~

Im szybciej VM modyfikuje pamięć, tym trudniej zakończyć kopiowanie w kilku przebiegach.

## 3. Trzy pytania przed migracją

Zanim zmienisz konfigurację, rozdziel problem.

### Czy hosty się widzą?

Sprawdź:

- DNS,
- routing,
- zapory,
- WinRM tam, gdzie jest używany,
- nazwy hostów,
- sieć migracyjną.

### Czy host źródłowy może uwierzytelnić się do docelowego?

Tu pojawiają się:

- CredSSP,
- Kerberos,
- SPN,
- constrained delegation.

### Czy host docelowy może uruchomić tę VM?

Sprawdź:

- CPU,
- pamięć,
- przełączniki Hyper-V,
- storage,
- funkcje zabezpieczeń,
- urządzenia wymagane przez VM.

Doskonały Kerberos nie pomoże, jeśli host docelowy nie ma właściwego vSwitcha.

## 4. Włączenie i inspekcja Live Migration

Włączenie:

~~~powershell
Enable-VMMigration
~~~

Sprawdzenie konfiguracji:

~~~powershell
Get-VMHost | Select-Object VirtualMachineMigrationEnabled, VirtualMachineMigrationAuthenticationType, VirtualMachineMigrationPerformanceOption, MaximumVirtualMachineMigrations, UseAnyNetworkForMigration
~~~

Host zdalny:

~~~powershell
Get-VMHost -ComputerName HV02
~~~

Nie zakładaj, że oba hosty mają takie same ustawienia.

## 5. CredSSP a Kerberos

Hyper-V obsługuje oba mechanizmy.

Kerberos:

~~~powershell
Set-VMHost -VirtualMachineMigrationAuthenticationType Kerberos
~~~

CredSSP:

~~~powershell
Set-VMHost -VirtualMachineMigrationAuthenticationType CredSSP
~~~

CredSSP jest prosty, gdy administrator pracuje bezpośrednio na hoście źródłowym.

Problem pojawia się przy scenariuszu:

~~~text
stacja administratora
       |
       v
      HV01
       |
       v
      HV02
~~~

Jeżeli migracja działa uruchomiona lokalnie na HV01, ale nie działa z komputera administratora, bardzo mocno wskazuje to na problem delegowania poświadczeń.

## 6. Kerberos dla zdalnego zarządzania

Dla hostów domenowych i zdalnego uruchamiania migracji Kerberos jest zwykle właściwszym rozwiązaniem.

Przykład:

~~~powershell
Set-VMHost -ComputerName HV01 -VirtualMachineMigrationAuthenticationType Kerberos
Set-VMHost -ComputerName HV02 -VirtualMachineMigrationAuthenticationType Kerberos
~~~

Samo ustawienie Kerberos nie wystarcza.

Konto komputera hosta źródłowego musi mieć prawo delegowania do odpowiednich usług hosta docelowego.

## 7. Constrained delegation

Najważniejsza usługa dla migracji VM:

~~~text
Microsoft Virtual System Migration Service
~~~

Dla migracji storage może być wymagane także:

~~~text
cifs
~~~

Typowa konfiguracja w Active Directory Users and Computers:

1. Otwórz konto komputera HV01.
2. Properties -> Delegation.
3. Wybierz delegowanie tylko do określonych usług.
4. Dodaj konto komputera HV02.
5. Dodaj Microsoft Virtual System Migration Service.
6. Dodaj cifs, jeśli potrzebna jest migracja storage.
7. Powtórz odwrotnie, jeśli migracja ma działać także HV02 -> HV01.

Delegowanie jest kierunkowe.

Przykład:

~~~text
HV01 może delegować do:
  Microsoft Virtual System Migration Service / HV02
  cifs / HV02

HV02 może delegować do:
  Microsoft Virtual System Migration Service / HV01
  cifs / HV01
~~~

Nie stosuj unconstrained delegation, jeśli wystarcza ograniczone delegowanie.

## 8. SPN i Kerberos

Lista SPN hosta:

~~~powershell
setspn -L HV01
setspn -L HV02
~~~

Sprawdzenie konkretnego SPN:

~~~powershell
setspn -Q "Microsoft Virtual System Migration Service/HV02.contoso.test"
~~~

Jeżeli diagnostyka potwierdza brak wpisu:

~~~powershell
setspn -S "Microsoft Virtual System Migration Service/HV02.contoso.test" HV02
~~~

Nie dodawaj SPN w ciemno.

Duplikat SPN może sam w sobie złamać Kerberos.

## 9. Stare bilety Kerberos

Po zmianie delegowania lub SPN stary ticket może nadal zachowywać poprzedni stan.

Dla bieżącej sesji:

~~~powershell
klist purge
~~~

Dla Local System Microsoft w diagnostyce Hyper-V wskazuje:

~~~powershell
klist purge -li 0x3e7
~~~

Czyszczenie ticketów to krok diagnostyczny, a nie trwałe rozwiązanie.

## 10. Windows Server 2025 i Credential Guard

W Windows Server 2025 trzeba brać pod uwagę Credential Guard.

Microsoft dokumentuje problemy z migracją Hyper-V opartą na CredSSP, gdy Credential Guard jest aktywny. To szczególnie istotne przy aktualizacji z Windows Server 2022 do 2025.

Sprawdź wersję systemu:

~~~powershell
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber
~~~

Sprawdź Device Guard:

~~~powershell
Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard
~~~

Nie diagnozuj Windows Server 2025 dokładnie tak samo jak starszego hosta.

## 11. Sieć Live Migration

Migracja może zużyć znaczną część przepustowości.

Potencjalnie konkuruje z:

- ruchem VM,
- storage,
- backupem,
- zarządzaniem.

Przykładowe logiczne rozdzielenie:

~~~text
Management network     -> administracja
VM network             -> ruch systemów gości
Storage network        -> storage
Live Migration network -> transfer pamięci/stanu
~~~

W małym laboratorium jedna sieć może wystarczyć. W produkcji warto świadomie kontrolować ścieżkę migracji.

Adaptery:

~~~powershell
Get-NetAdapter | Sort-Object Name | Format-Table Name, Status, LinkSpeed, MacAddress
~~~

Routing:

~~~powershell
Get-NetRoute -AddressFamily IPv4 | Sort-Object RouteMetric
~~~

## 12. Czy używać dowolnej sieci

Sprawdź:

~~~powershell
Get-VMHost | Select-Object UseAnyNetworkForMigration
~~~

Przykład ustawienia:

~~~powershell
Set-VMHost -UseAnyNetworkForMigration $true
~~~

W produkcji wygodniejsze nie zawsze znaczy lepsze. Lepiej świadomie ustalić, którędy ma iść ruch migracyjny.

## 13. Tryby wydajności migracji

Hyper-V obsługuje między innymi:

- TCP/IP,
- Compression,
- SMB.

Przykład:

~~~powershell
Set-VMHost -VirtualMachineMigrationPerformanceOption Compression
~~~

Sprawdzenie:

~~~powershell
Get-VMHost | Select-Object VirtualMachineMigrationPerformanceOption
~~~

### Compression

Dobre, gdy:

- CPU ma zapas,
- sieć jest ograniczeniem.

Koszt: więcej pracy procesora.

### SMB

Może wykorzystać wysokowydajne mechanizmy SMB, w tym środowiska z SMB Multichannel lub RDMA.

Nie wybieraj SMB tylko dlatego, że nazwa brzmi szybciej. Infrastruktura musi być do tego przygotowana.

### TCP/IP

Najprostszy punkt wyjścia bez rozbudowanej infrastruktury SMB/RDMA.

## 14. Kompatybilność CPU

Migracja może się nie udać, jeżeli VM korzysta z funkcji CPU niedostępnych na hoście docelowym.

Sprawdzenie:

~~~powershell
Get-VMProcessor -VMName APP01 | Select-Object CompatibilityForMigrationEnabled
~~~

Włączenie trybu zgodności:

~~~powershell
Set-VMProcessor -VMName APP01 -CompatibilityForMigrationEnabled $true
~~~

Nie włączaj tego automatycznie dla wszystkich VM. Tryb zgodności może ukrywać nowsze funkcje procesora przed gościem.

## 15. Virtual switch

Bardzo częsty problem: inna nazwa przełącznika na hoście docelowym.

Porównanie:

~~~powershell
Get-VMSwitch -ComputerName HV01 | Select-Object Name, SwitchType
Get-VMSwitch -ComputerName HV02 | Select-Object Name, SwitchType
~~~

Sieć VM:

~~~powershell
Get-VMNetworkAdapter -VMName APP01 -ComputerName HV01 | Select-Object Name, SwitchName, MacAddress
~~~

Jeżeli VM używa Production, a drugi host ma Prod-Network, Hyper-V nie musi traktować ich jako odpowiedników.

## 16. Pamięć na hoście docelowym

VM:

~~~powershell
Get-VM -ComputerName HV01 -Name APP01 | Select-Object Name, State, MemoryAssigned
~~~

Dostępna pamięć:

~~~powershell
Get-Counter -ComputerName HV02 '\Memory\Available MBytes'
~~~

Inne VM:

~~~powershell
Get-VM -ComputerName HV02 | Select-Object Name, State, MemoryAssigned, MemoryDemand
~~~

Nie patrz tylko na fizycznie zainstalowany RAM.

## 17. Podstawowa migracja

~~~powershell
Move-VM -Name APP01 -DestinationHost HV02
~~~

Z komputera administracyjnego:

~~~powershell
Move-VM -ComputerName HV01 -Name APP01 -DestinationHost HV02
~~~

Różnica między powodzeniem lokalnym i błędem zdalnym jest bardzo cenną wskazówką diagnostyczną.

## 18. Migracja razem ze storage

~~~powershell
Move-VM -Name APP01 -DestinationHost HV02 -IncludeStorage -DestinationStoragePath "D:\VMs\APP01"
~~~

Sprawdzenie przestrzeni:

~~~powershell
Get-Volume -CimSession HV02 | Select-Object DriveLetter, FileSystemLabel, SizeRemaining, Size
~~~

Dochodzi wtedy więcej zależności:

- CIFS,
- delegowanie,
- prawa,
- miejsce na dysku,
- przepustowość,
- ścieżki.

## 19. Preflight przed migracją

Przykładowy read-only check:

~~~powershell
param(
    [Parameter(Mandatory)]
    [string]$SourceHost,

    [Parameter(Mandatory)]
    [string]$DestinationHost,

    [Parameter(Mandatory)]
    [string]$VMName
)

Resolve-DnsName $SourceHost -ErrorAction Stop
Resolve-DnsName $DestinationHost -ErrorAction Stop

$source = Get-VMHost -ComputerName $SourceHost
$destination = Get-VMHost -ComputerName $DestinationHost

$source | Select-Object ComputerName, VirtualMachineMigrationEnabled, VirtualMachineMigrationAuthenticationType, VirtualMachineMigrationPerformanceOption
$destination | Select-Object ComputerName, VirtualMachineMigrationEnabled, VirtualMachineMigrationAuthenticationType, VirtualMachineMigrationPerformanceOption

$vm = Get-VM -ComputerName $SourceHost -Name $VMName -ErrorAction Stop
$vm | Select-Object Name, State, MemoryAssigned, ProcessorCount

$vmNics = Get-VMNetworkAdapter -ComputerName $SourceHost -VMName $VMName
$destinationSwitches = Get-VMSwitch -ComputerName $DestinationHost

$missingSwitches = foreach ($nic in $vmNics) {
    if ($nic.SwitchName -and $nic.SwitchName -notin $destinationSwitches.Name) {
        $nic.SwitchName
    }
}

if ($missingSwitches) {
    Write-Warning ("Missing destination switches: " + ($missingSwitches -join ", "))
}

Get-VMProcessor -ComputerName $SourceHost -VMName $VMName |
    Select-Object CompatibilityForMigrationEnabled
~~~

Taki skrypt nie gwarantuje sukcesu, ale szybko wyłapuje kilka najczęstszych niespójności.

## 20. Diagnostyka według klasy błędu

### Access denied / Kerberos

Objawy:

- 0x80070005,
- błędy Kerberos,
- działa lokalnie, nie działa zdalnie.

Sprawdź:

~~~powershell
Get-VMHost -ComputerName HV01 | Select-Object VirtualMachineMigrationAuthenticationType
~~~

Następnie:

- delegation,
- SPN,
- tickets,
- DNS.

### Brak połączenia z hostem

~~~powershell
Resolve-DnsName HV02
Test-NetConnection HV02
Test-WSMan HV02
~~~

Nie poprawiaj Kerberos, jeśli DNS nie działa.

### Błąd sieci VM

~~~powershell
Get-VMNetworkAdapter -ComputerName HV01 -VMName APP01
Get-VMSwitch -ComputerName HV02
~~~

### Błąd CPU

~~~powershell
Get-VMProcessor -ComputerName HV01 -VMName APP01
~~~

### Błąd storage

~~~powershell
Get-VMHardDiskDrive -ComputerName HV01 -VMName APP01
~~~

Potem sprawdź miejsce, ścieżki, uprawnienia i CIFS.

## 21. Logi Hyper-V

Lista logów:

~~~powershell
Get-WinEvent -ListLog "*Hyper-V*" | Select-Object LogName, RecordCount
~~~

Ostatnie zdarzenia VMMS:

~~~powershell
Get-WinEvent -LogName "Microsoft-Windows-Hyper-V-VMMS-Admin" -MaxEvents 50 |
    Select-Object TimeCreated, Id, LevelDisplayName, Message
~~~

Tylko ostatnie 15 minut:

~~~powershell
$since = (Get-Date).AddMinutes(-15)

Get-WinEvent -FilterHashtable @{
    LogName = "Microsoft-Windows-Hyper-V-VMMS-Admin"
    StartTime = $since
} | Select-Object TimeCreated, Id, Message
~~~

Ograniczenie czasu jest ważne, bo log może zawierać tysiące starych zdarzeń.

## 22. Kolejność diagnostyki

Dobra procedura:

1. sprawdź stan VM,
2. sprawdź DNS obu hostów,
3. porównaj ustawienia migracji,
4. ustal, czy migracja jest lokalna czy zdalna,
5. sprawdź Kerberos/delegation/SPN,
6. porównaj vSwitch,
7. sprawdź CPU,
8. sprawdź pamięć,
9. sprawdź storage,
10. sprawdź VMMS logs,
11. zmieniaj jedną rzecz naraz.

Nie zmieniaj jednocześnie firewalla, Kerberosa, switcha i CPU compatibility. Możesz wtedy uzyskać sukces, ale nie dowiesz się, co było przyczyną.

## 23. Scenariusz: lokalnie działa, zdalnie nie

~~~text
ADM01 -> HV01 -> HV02
~~~

Move-VM uruchomione na HV01 działa.

To samo uruchomione na ADM01 kończy się access denied.

Najbardziej prawdopodobna grupa problemów:

~~~text
Kerberos
delegation
SPN
~~~

To znacznie lepszy punkt startu niż otwieranie przypadkowych portów.

## 24. Scenariusz: host docelowy osiągalny, ale VM nie startuje po przygotowaniu

Najpierw porównaj sieci:

~~~powershell
Get-VMNetworkAdapter -ComputerName HV01 -VMName APP01 | Select-Object SwitchName
Get-VMSwitch -ComputerName HV02 | Select-Object Name
~~~

Brak zgodnego switcha to częsty, prosty błąd.

## 25. Scenariusz: migracja trwa bardzo długo

Sprawdź:

~~~powershell
Get-VMHost | Select-Object VirtualMachineMigrationPerformanceOption
~~~

Następnie:

- prędkość NIC,
- obciążenie sieci backupem,
- CPU przy Compression,
- SMB/RDMA przy SMB,
- intensywność zmian pamięci VM.

Duża VM nie zawsze migruje wolniej niż mniejsza. VM intensywnie zapisująca RAM może być trudniejsza do przeniesienia.

## 26. Błędy bezpieczeństwa

Nie rób:

- unconstrained delegation bez potrzeby,
- ręcznego dodawania SPN bez wyszukania duplikatów,
- wyłączania nowoczesnych zabezpieczeń bez analizy,
- Live Migration przez niezaufaną sieć,
- publikowania realnych hostów i topologii w publicznym repo.

## 27. Jak rozumować na AZ-802

Model:

~~~text
Czy hosty się komunikują?
        |
        v
Czy uwierzytelnienie i delegacja działają?
        |
        v
Czy host docelowy jest zgodny z VM?
        |
        v
Czy storage i sieć są dostępne?
        |
        v
Czy transport migracji jest właściwy?
~~~

Typowe podpowiedzi w zadaniach:

- działa lokalnie, nie działa zdalnie -> delegation/Kerberos,
- brak sieci po migracji -> vSwitch,
- różne generacje CPU -> processor compatibility,
- przenoszony też storage -> CIFS/storage path,
- bardzo wolna migracja -> transport i bandwidth.

## 28. Weryfikacja po migracji

Stan VM:

~~~powershell
Get-VM -ComputerName HV02 -Name APP01 | Select-Object Name, State, Status
~~~

Sieć:

~~~powershell
Get-VMNetworkAdapter -ComputerName HV02 -VMName APP01 |
    Select-Object SwitchName, MacAddress, Status
~~~

Dyski:

~~~powershell
Get-VMHardDiskDrive -ComputerName HV02 -VMName APP01 | Select-Object Path
~~~

Test aplikacji:

~~~powershell
Test-NetConnection app01.contoso.test -Port 443
~~~

Sukces migracji infrastruktury nie jest równoznaczny ze zdrowiem aplikacji.

## 29. Rollback

Przed migracją zapisz:

~~~text
source host
destination host
VM name
storage paths
switch names
authentication mode
CPU compatibility state
application health check
rollback host
~~~

To szczególnie ważne, gdy razem z VM przenosisz storage albo zmieniasz konfigurację.

## 30. Laboratorium

Hosty:

~~~text
HV01.contoso.test
HV02.contoso.test
LAB-VM01
~~~

Zadanie:

1. włącz Live Migration,
2. porównaj tryby uwierzytelniania,
3. ustaw Kerberos,
4. skonfiguruj constrained delegation w obie strony,
5. sprawdź SPN,
6. porównaj vSwitch,
7. uruchom preflight,
8. przenieś LAB-VM01 na HV02,
9. sprawdź sieć VM,
10. przenieś VM z powrotem,
11. celowo zepsuj bezpieczny element labu, np. nazwę testowego switcha,
12. przeanalizuj błąd,
13. napraw,
14. ponownie potwierdź migrację.

Kontrolowane zepsucie środowiska uczy więcej niż jednorazowy sukces.

## 31. Final checklist

Przed:

- [ ] DNS działa,
- [ ] hosty są osiągalne,
- [ ] Live Migration jest włączone,
- [ ] tryb uwierzytelniania jest świadomie wybrany,
- [ ] delegation jest poprawne,
- [ ] SPN są poprawne,
- [ ] sieć migracyjna jest właściwa,
- [ ] vSwitch pasują,
- [ ] pamięć jest dostępna,
- [ ] CPU compatibility jest rozważone,
- [ ] storage jest dostępny.

Po:

- [ ] VM działa na hoście docelowym,
- [ ] sieć VM działa,
- [ ] dyski są we właściwej lokalizacji,
- [ ] aplikacja odpowiada,
- [ ] logi nie pokazują nierozwiązanych błędów.

## 32. Dokumentacja Microsoft

Hyper-V Live Migration troubleshooting:

https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/hyper-v-virtual-machine-live-migration

Constrained delegation and Live Migration troubleshooting:

https://learn.microsoft.com/en-us/troubleshoot/windows-server/virtualization/troubleshoot-live-migration-issues

Set-VMHost:

https://learn.microsoft.com/powershell/module/hyper-v/set-vmhost

Credential Guard considerations:

https://learn.microsoft.com/windows/security/identity-protection/credential-guard/considerations-known-issues

## Podsumowanie

Live Migration to nie jeden przełącznik. To współdziałanie:

~~~text
Hyper-V
+ DNS
+ Kerberos
+ delegation
+ SPN
+ sieć
+ vSwitch
+ CPU
+ pamięć
+ storage
+ weryfikacja
~~~

Najbardziej wartościowa umiejętność administracyjna to diagnozowanie tych warstw osobno zamiast traktowania każdej awarii jako ogólnego błędu Hyper-V.
