"""Run veraPDF (https://verapdf.org, free, GPLv3/MPLv2, needs Java) with its PDF/UA-1 profile on one file.

Either its launcher (`verapdf` / `verapdf.bat` from the veraPDF installer) or its install folder plus a java program.
Returns {"compliant": bool, "failed": [{"rule", "checks", "message"}], "version": str}; raises VeraUnavailable when
veraPDF cannot be run.
"""
import json
import os
import subprocess
from pathlib import Path


class VeraUnavailable(RuntimeError):
    pass


def _command(launcher=None, home=None, java=None):
    if launcher:
        return [str(launcher)]
    if home and java:
        home = Path(home)
        cp = os.pathsep.join([str(home / "etc"), str(home / "bin" / "*")])
        return [str(java), "-classpath", cp, "-Dfile.encoding=UTF8", f"-Dapp.home={home}", f"-Dbasedir={home}",
                "org.verapdf.apps.GreenfieldCliWrapper"]
    raise VeraUnavailable("give --verapdf <launcher>, or --verapdf-home <folder> with --java <java program>")


def check(pdf, launcher=None, home=None, java=None, timeout=900):
    cmd = _command(launcher, home, java) + ["--flavour", "ua1", "--format", "json", str(pdf)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VeraUnavailable(f"veraPDF did not run: {e}") from None
    out = r.stdout.decode("utf-8", "replace")
    if "{" not in out:
        raise VeraUnavailable("veraPDF gave no report: " + (r.stderr.decode("utf-8", "replace").strip()[-300:] or out[-300:]))
    rep = json.loads(out[out.index("{"):])
    job = rep["report"]["jobs"][0]
    v = job.get("validationResult")
    v = v[0] if isinstance(v, list) else v
    if not v:
        raise VeraUnavailable("veraPDF could not validate the file: " + json.dumps(job.get("taskResult"))[:300])
    failed = [{"rule": f"{s['clause']}-{s['testNumber']}", "checks": s["failedChecks"],
               "message": ((s.get("checks") or [{}])[0].get("errorMessage") or s.get("description", ""))[:200]}
              for s in v["details"].get("ruleSummaries", [])
              if s.get("ruleStatus") == "FAILED" or s.get("status") == "failed"]
    return {"compliant": bool(v["compliant"]), "failed": failed,
            "version": rep.get("buildInformation", {}).get("releaseDetails", [{}])[0].get("version", "")}
