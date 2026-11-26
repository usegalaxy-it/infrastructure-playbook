#!/usr/bin/env python3
"""Align installed Jenkins plugins with the running core.

Reads the update center for the installed core version, then:
  * plugins whose installed release requires a newer core are replaced with the
    newest release compatible with this core;
  * required (non-optional) dependencies that are missing are installed.

Dry run by default; pass --apply to download. Run as root on the controller,
then restart Jenkins. Managed by Ansible (build.yml), which runs it with --apply.
"""
import json
import os
import pwd
import re
import shutil
import sys
import urllib.request

JENKINS_HOME = os.environ.get("JENKINS_HOME", "/var/lib/jenkins")
PLUGINS = os.path.join(JENKINS_HOME, "plugins")
WAR = "/usr/share/java/jenkins.war"


def vkey(v):
    return [int(x) for x in re.findall(r"\d+", v)]


def core_version():
    import zipfile
    with zipfile.ZipFile(WAR) as z:
        for line in z.read("META-INF/MANIFEST.MF").decode().splitlines():
            if line.startswith("Jenkins-Version:"):
                return line.split(":", 1)[1].strip()
    sys.exit("cannot read core version from " + WAR)


def installed():
    out = {}
    for name in os.listdir(PLUGINS):
        mf = os.path.join(PLUGINS, name, "META-INF", "MANIFEST.MF")
        if not os.path.isfile(mf):
            continue
        meta = {}
        for line in open(mf, encoding="utf-8", errors="replace"):
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        out[name] = {"version": meta.get("Plugin-Version", "?"),
                     "core": meta.get("Jenkins-Version", "0")}
    return out


def main():
    apply = "--apply" in sys.argv
    core = core_version()
    print(f"core: {core}")
    url = f"https://updates.jenkins.io/update-center.actual.json?version={core}"
    uc = json.load(urllib.request.urlopen(url))["plugins"]
    have = installed()

    todo = {}
    for name, info in have.items():
        if vkey(info["core"]) > vkey(core):
            if name in uc:
                todo[name] = f"installed {info['version']} needs core {info['core']}"
            else:
                print(f"!! {name}: needs core {info['core']}, not in update center for {core}")

    # missing required dependencies, resolved transitively
    queue = list(have) + list(todo)
    seen = set()
    while queue:
        name = queue.pop()
        if name in seen or name not in uc:
            continue
        seen.add(name)
        for dep in uc[name].get("dependencies", []):
            if dep.get("optional"):
                continue
            d = dep["name"]
            if d not in have and d not in todo and d in uc:
                todo[d] = f"missing dependency of {name}"
                queue.append(d)

    if not todo:
        print("nothing to do")
        return
    for name, why in sorted(todo.items()):
        p = uc[name]
        print(f"{name}: -> {p['version']} (core {p['requiredCore']}) [{why}]")

    if not apply:
        print("\ndry run: re-run with --apply to download")
        return

    jenkins = pwd.getpwnam("jenkins")
    for name in sorted(todo):
        dest = os.path.join(PLUGINS, name + ".jpi")
        tmp = dest + ".download"
        with urllib.request.urlopen(uc[name]["url"]) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        if os.path.exists(dest):
            shutil.copy2(dest, dest + ".bak")
        os.replace(tmp, dest)
        os.chown(dest, jenkins.pw_uid, jenkins.pw_gid)
        # an exploded directory from the newer release would win over the new .jpi
        exploded = os.path.join(PLUGINS, name)
        if os.path.isdir(exploded):
            shutil.rmtree(exploded)
        print(f"installed {name} {uc[name]['version']}")
    print("\ndone: restart Jenkins (systemctl restart jenkins)")


if __name__ == "__main__":
    main()
