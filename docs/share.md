# Sharing the family

`./al share` keeps one standing copy of alfred and the engines it drives on
one host, for maintainers on that machine, on its network and elsewhere. It
is reached only from devices invited onto the share's own private network,
signed in with alfred's own accounts. It serves the commits its manifest
names, and keeps a database and a media library of its own, snapshotted by
name. qm's record [A family's dev state is shared by one standing host, to
invited devices only](https://github.com/quaternionmedia/qm/blob/main/records/DRAFT-a-familys-dev-state-is-shared-to-invited-devices.md)
is the rule it keeps; this page is how alfred keeps it.

## What it runs

| Member | How | Port | Reached from |
|---|---|---|---|
| alfred | containers built from its commit: the api, a render worker, MongoDB, and the site, built once | 17320 | loopback, and the host's address on the share's network |
| joe | a process, from its commit's own environment | 10594 | loopback only, through alfred |
| looksatwords | a process, from its commit's own environment | 14142 | loopback only, through alfred |

Each port is its constant's first five digits, where the dev stack's are the
first four, so a share and a developer's own servers run side by side
without moving either. joe and looksatwords ask no login, so nothing but
alfred reaches them.

alfred runs with `ALFRED_PRODUCTION` set: registration is closed, the login
bypass makes it refuse to start, and the projects seeded into its empty
database are a superuser's to see. Nothing in a share watches files or
reloads; saving a file in a checkout changes nothing it serves.

Everything is kept in `ALFRED_SHARE_STATE`, `~/.alfred/share` unless set:

| Path | What |
|---|---|
| `manifest.json` | what each member serves, where alfred is published, the network |
| `src/<member>/` | the share's own clone of each member, at its commit |
| `db/`, `videos/` | the database's files and the media library |
| `secret_key` | the signing key, made once and read by the share alone |
| `snapshots/<name>/` | each snapshot |
| `logs/`, `run/` | joe's and looksatwords' output, and their pids |
| `compose.json` | the compose file `./al share up` writes and runs |

The manifest says what one machine serves, so it is never committed.

## What it needs

Docker with Compose, git, a Python 3.8 or newer for `./al`, and uv for joe
and looksatwords, as for [the family](family.md). The share's network is a
ZeroTier network whose controller is the host's own ZeroTier One, so the
host runs ZeroTier One, and so does every invited device. joe needs an
ffmpeg, named by `JOE_FFMPEG` when it is not on `PATH`.

## Make the network, once

From a shell started as administrator, in this checkout:

```sh
python scripts/share.py network create
```

It makes a private network on the host's own controller, authorizes the host
on it at `10.173.20.1`, joins it, and publishes alfred there. It prints the
network's id, which is what an invited person joins. Only an administrator
can read the token ZeroTier One's local API asks for, which is why this and
`network authorize` run elevated; nothing prints the token.

On Windows the new adapter is a network of its own. If an invited device
reaches the network but not alfred, Windows' firewall is refusing port 17320
on that adapter: allow it inbound there.

## Choose what it serves

```sh
./al share move alfred=feat/who-spoke joe=main
./al share env joe JOE_FFMPEG=/path/to/ffmpeg
```

A ref is a branch of the member's origin, or a commit a branch of it holds;
a commit no branch of origin holds is refused, because nobody else could
fetch what a finding against it names. `move` clones the member into the
share on first use, borrowing the objects of the checkout this machine
works on, then checks the commit out, rebuilds what changed and starts it.
`./al share env` keeps a setting a member is started with; the login bypass
and the signing key are the share's own and are refused.

## Bring it up, and see what it serves

```sh
./al share up
./al share
```

`./al share` says, for each member and each address, the ref and commit the
manifest names and whether the member serves it:

| It says | It means |
|---|---|
| `serving` | the commit running is the manifest's, and the server answers as that member |
| `moved, not restarted` | the manifest moved and the member has not: `./al share up` |
| `not running` | nothing of the share's runs for it |
| `not answering as itself` | its port answers as something else |
| `unknown` | its port answers and does not say what it is |

It exits non-zero unless every member is `serving`, and ends with the space
the database, the media and the snapshots take.

## Let someone in

1. They install ZeroTier One and join the network's id. Their device shows
   its node id, ten hex digits.
2. From a shell started as administrator:
   `python scripts/share.py network authorize NODE --name "who they are"`.
3. `./al share account their@address --name First` makes their account; the
   password is asked for twice and given to them by a channel of your own.
   `--superuser` sees every project, the seeded ones included.
4. They open <http://10.173.20.1:17320>.

`python scripts/share.py network` lists every device and whether it is let
in, and `network revoke NODE` shuts one out.

## Snapshots

```sh
./al share snapshot before-the-demo
./al share snapshots
./al share restore before-the-demo --yes
```

A snapshot holds the database's files, the media library and the manifest it
was taken under; the cache of fetched remote media is left out, and fetched
again. Taking one and restoring one stop alfred's containers while the files
are copied. A restore replaces the database and the media whole, and asks
for `--yes`, because what is there is gone unless a snapshot holds it. A
snapshot is trusted once it has been restored.

## Coming back with the host

alfred's containers restart with Docker, so the share is back once Docker
is, when Docker Desktop is set to start at sign-in. joe and looksatwords are
processes, and `./al share up` brings back whatever is not serving. A task that runs it at sign-in brings the whole share
back; on Windows, from PowerShell, with the path to this checkout:

```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Program Files\Git\bin\bash.exe' -Argument '-lc "cd /c/path/to/alfred && ./al share up"'
Register-ScheduledTask -TaskName 'alfred share' -Trigger (New-ScheduledTaskTrigger -AtLogOn) -Action $action
```

## A member joins

A member alfred drives joins as a row in `MEMBERS`, in `scripts/share.py`:
the command that serves it on a host and port it is given, the setting that
tells alfred where it is, and the title its OpenAPI document gives, which is
how `./al share` knows it answers as itself. looksatwords joins that way:

```sh
./al share move looksatwords=main
```

and alfred is given `ALFRED_LANGUAGE_ENGINE_URL` at its next start. qmcp
drives alfred rather than being driven, so it is not served by the share: a
qmcp anywhere on the network points `QMCP_ALFRED_URL` at the share, with an
account of its own.

## What it does not do

- It has no public address. A device off the share's network reaches
  nothing.
- It sends no mail, so a forgotten password is set again by a superuser,
  with `PATCH /users/{id}`.
- A member's own files outside the share's directory are not in a snapshot:
  looksatwords keeps its `data.json` in its clone.
- It is down while its host sleeps.
- It asserts nothing about what it serves. A finding names the commit
  `./al share` reports, and the version tag stays the gate for a release.
