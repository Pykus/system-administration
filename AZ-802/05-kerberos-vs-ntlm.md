# Kerberos vs NTLM — AZ-802 drill

## Core idea
In an Active Directory domain, Kerberos is the preferred authentication protocol for normal domain authentication. NTLM can still appear as a fallback or for scenarios where Kerberos cannot be used.

A useful troubleshooting question is therefore not only **“Did authentication succeed?”** but also **“Which protocol was actually used, and why?”**

## Scenario
A user can access a file server by IP address, but access by the server's DNS name behaves differently. You suspect the authentication method is changing.

Lab environment:

- domain: `contoso.local`
- client: `CLIENT01`
- file server: `FS01`
- domain controller: `DC01`

## Diagnosis

Start with the client and confirm basic domain/DNS health. Then inspect the Kerberos ticket cache.

```powershell
klist
nltest /dsgetdc:contoso.local
Resolve-DnsName FS01.contoso.local
```

After accessing the service by its normal DNS name, run `klist` again and look for a service ticket for the target service.

If Kerberos is expected but no suitable ticket appears, investigate name resolution, SPNs, time synchronization, domain connectivity, and the exact way the service is being addressed.

## Kerberos — remember

- ticket-based authentication;
- commonly used for domain authentication in Active Directory;
- depends on working DNS and access to a KDC/domain controller when tickets are obtained;
- service authentication relies on the correct Service Principal Name (SPN);
- supports mutual authentication.

## NTLM — remember

- challenge-response authentication;
- does not use Kerberos service tickets;
- can appear as a fallback when Kerberos cannot be negotiated;
- generally offers fewer modern security properties than Kerberos and should not be treated as the preferred AD authentication path.

## Useful commands

### Inspect Kerberos tickets

```powershell
klist
```

### Remove cached Kerberos tickets for a clean troubleshooting test

```powershell
klist purge
```

Use this only when you understand the impact on the current user session.

### Inspect SPNs for an account

```powershell
setspn -L CONTOSO\FS01$
```

### Search for a specific SPN

```powershell
setspn -Q cifs/FS01.contoso.local
```

## Interpretation
If access by the canonical DNS name produces the expected Kerberos service ticket but access by another name does not, investigate whether the alternate name has an appropriate SPN and whether clients resolve it correctly.

Do not “fix” the problem by forcing NTLM. Find the reason Kerberos cannot be negotiated.

## Repair / recommended action

1. Confirm DNS resolution.
2. Confirm client and server time are synchronized.
3. Confirm the client can locate a domain controller.
4. Check the relevant SPN.
5. Check for duplicate SPNs.
6. Retest and confirm the expected Kerberos ticket appears.

## Exam traps

**Trap 1:** “Authentication works, so Kerberos must be working.”

Wrong. Authentication may have succeeded using another protocol.

**Trap 2:** “An A record is enough for Kerberos.”

Not necessarily. DNS gets the client to the host, while the SPN identifies the service principal used by Kerberos.

**Trap 3:** “NTLM fallback means the incident is solved.”

No. A fallback can hide the actual Kerberos configuration problem.

## Quick exam drill

### 1. A domain user accesses a file server successfully, but `klist` shows no expected CIFS service ticket. What should you verify first?
**Answer:** Verify how the server was addressed, DNS resolution, domain connectivity, and the relevant CIFS SPN before assuming Kerberos was used.

### 2. What uniquely identifies a service instance to Kerberos in Active Directory?
**Answer:** A Service Principal Name (SPN).

### 3. Why can using an IP address instead of a service's normal DNS name complicate Kerberos authentication?
**Answer:** Kerberos service ticket requests normally rely on service names/SPNs, so addressing the service in a way that does not map to the expected SPN can prevent normal Kerberos negotiation.

### 4. Which command shows the current user's Kerberos ticket cache?
**Answer:** `klist`.

### 5. Should you enable or force NTLM as the first repair for a broken Kerberos path?
**Answer:** No. Diagnose and repair the Kerberos prerequisites and configuration.

## Interview question
**A user can reach a domain service, but you suspect NTLM fallback. How would you prove which authentication protocol is being used?**

A strong answer starts with the client-side Kerberos ticket cache, then correlates the result with the service name, DNS resolution, SPN registration, domain-controller reachability, and relevant authentication logs.

## Wyjaśnienie po polsku
Najważniejsza myśl egzaminacyjna: **samo działanie usługi nie dowodzi, że działa Kerberos**. W diagnostyce trzeba potwierdzić protokół. Jeżeli Kerberos nie działa, szukaj przyczyny w DNS, nazwie usługi/SPN, czasie i łączności z domeną zamiast uznawać fallback do NTLM za poprawne rozwiązanie.

## C1 / CAE phrase
**fall back on** — use something less preferred when the normal option is unavailable.

Example: *The client may fall back on another authentication mechanism when Kerberos cannot be negotiated.*
