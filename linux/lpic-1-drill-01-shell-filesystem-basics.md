# LPIC-1 Drill 01 — Shell and Filesystem Basics

A short hands-on drill for the first Linux/LPIC-1 topics. The goal is not to memorize commands in isolation, but to build a repeatable troubleshooting workflow.

## Scenario

You are logged in to a Linux server and need to:

1. identify where you are,
2. inspect files safely,
3. find a configuration file,
4. check permissions,
5. make a copy,
6. verify a running process.

Use a lab VM or disposable test system.

## 1. Where am I?

```bash
pwd
whoami
hostname
```

Remember:

- `pwd` — current working directory,
- `whoami` — current user,
- `hostname` — host name.

### Quick check

What is the difference between:

```text
/etc/ssh
etc/ssh
```

The first path is **absolute**. The second is **relative** to the current directory.

## 2. Inspect a directory

```bash
ls
ls -l
ls -la
```

Useful fields in `ls -l`:

```text
-rw-r----- 1 root adm 2451 Sep 25 12:30 example.log
```

Read it as:

- `-` — regular file,
- `rw-` — owner permissions,
- `r--` — group permissions,
- `---` — permissions for others,
- `root` — owner,
- `adm` — group.

## 3. Move around without getting lost

```bash
cd /etc
pwd

cd ..
pwd

cd ~
pwd

cd -
```

Useful shortcuts:

- `..` — parent directory,
- `.` — current directory,
- `~` — current user's home directory,
- `cd -` — previous directory.

## 4. Identify a file before opening it

```bash
file /etc/passwd
file /bin/ls
```

Do not assume that a filename extension tells you what a file really is.

## 5. Search for files

Find a file by name:

```bash
find /etc -name "sshd_config" 2>/dev/null
```

Case-insensitive search:

```bash
find /etc -iname "*ssh*" 2>/dev/null
```

LPIC-1 distinction:

- `find` searches the filesystem directly,
- `which` searches for an executable in `PATH`,
- `whereis` searches common binary/source/manual locations.

Try:

```bash
which bash
whereis bash
```

## 6. Read text safely

```bash
cat /etc/os-release
less /etc/services
head -n 10 /etc/services
tail -n 10 /etc/services
```

For long files, prefer `less` over `cat`.

Useful `less` keys:

- `/` — search,
- `n` — next match,
- `q` — quit.

## 7. Copy before changing

Create a small lab directory:

```bash
mkdir -p ~/lpic-lab
cd ~/lpic-lab
```

Create and copy a file:

```bash
printf "server=demo\n" > app.conf
cp app.conf app.conf.bak
ls -l
```

Verify the files:

```bash
cat app.conf
cat app.conf.bak
```

## 8. Understand permissions

Check permissions:

```bash
ls -l app.conf
```

Set:

- owner: read + write,
- group: read,
- others: no access.

Symbolic form:

```bash
chmod u=rw,g=r,o= app.conf
```

Numeric form:

```bash
chmod 640 app.conf
```

Why `640`?

| Value | Permission |
|---:|---|
| 4 | read |
| 2 | write |
| 1 | execute |

So:

- owner: `4 + 2 = 6` → `rw-`,
- group: `4` → `r--`,
- others: `0` → `---`.

## 9. Pipes and redirection

Write output to a file:

```bash
printf "alpha\nbeta\ngamma\n" > names.txt
```

Append instead of replacing:

```bash
printf "delta\n" >> names.txt
```

Filter output:

```bash
cat names.txt | grep "a"
```

A cleaner version:

```bash
grep "a" names.txt
```

Count matching lines:

```bash
grep "a" names.txt | wc -l
```

Remember:

- `>` — overwrite,
- `>>` — append,
- `|` — send stdout of one command to stdin of another.

## 10. Check processes

Show processes:

```bash
ps
ps aux
```

Find a process by name:

```bash
pgrep -a ssh
```

or:

```bash
ps aux | grep ssh
```

For an interactive view:

```bash
top
```

Do not use `kill -9` as the first troubleshooting step. A normal termination signal is preferable when possible.

## 11. Mini LPIC-1 quiz

1. Which command prints the current directory?
2. What is the difference between an absolute and relative path?
3. Which `ls` option shows hidden files?
4. Which command searches the filesystem directly?
5. What does `chmod 640 file` mean?
6. What is the difference between `>` and `>>`?
7. What does the pipe operator `|` do?
8. Which command is better for interactively reading a long text file: `cat` or `less`?
9. Which command can show the path of an executable found through `PATH`?
10. Why should `kill -9` usually not be the first signal used?

## Answer key

1. `pwd`.
2. An absolute path starts from the filesystem root; a relative path starts from the current directory.
3. `-a`.
4. `find`.
5. Owner `rw-`, group `r--`, others `---`.
6. `>` replaces the target; `>>` appends.
7. It connects stdout of the left command to stdin of the right command.
8. `less`.
9. `which`.
10. SIGKILL does not give the process a chance to shut down cleanly.

## One-minute recap

If you remember only this sequence, it is already useful:

```bash
pwd
ls -la
cd /some/path
file somefile
find /etc -name "something"
less somefile
cp somefile somefile.bak
chmod 640 somefile
ps aux
pgrep -a process_name
```

That is enough for a solid first shell/filesystem drill and a good base for the next LPIC-1 topics: users/groups, package management, processes, services and storage.
