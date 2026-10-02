#!/usr/bin/env python3
"""Browser GUI for the bagASM pipeline, served on localhost. Standard library
only. Usage:  python3 gui/bagasm_web.py [--port 8765]
Binds 127.0.0.1 only: the server launches processes, never expose it.
"""
import argparse
import json
import os
import re
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
HTML = Path(__file__).with_name("bagasm_web.html")

# Reuse the QC parsers the pipeline's own final report uses.
import importlib.util
_spec = importlib.util.spec_from_file_location("combine_qc_report", PIPELINE_DIR / "bin" / "combine_qc_report.py")
qc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qc)

# Same status-line format the Tk GUI parses (see bagasm_gui.py).
STATUS_RE = re.compile(
    r"^\[(?P<hash>[^\]]*)\]\s+(?P<name>\S+)(?:\s+\((?P<tag>[^)]*)\))?\s*\|\s*"
    r"(?P<done>\d+)\s+of\s+(?P<total>\d+)(?:,\s*(?P<extra>[\w\s:]+))?\s*(?P<check>✔)?\s*$"
)
FAILED_RE = re.compile(r"Error executing process\s*>\s*'([^']+)'")

# name, label, default ("" = omit when empty), kind: text|select|bool, options/group
FIELDS = [
    ("strain", "Strain / sample ID", "", "text", "Required"),
    ("outdir", "Output directory", "", "text", "Required"),
    ("r1", "R1 (comma-sep for multi-lane)", "", "text", "Short reads"),
    ("r2", "R2 (comma-sep for multi-lane)", "", "text", "Short reads"),
    ("lr", "Long reads (comma-sep)", "", "text", "Long reads"),
    ("lr_type", "lr_type", "", ["", "ont", "pacbio-clr", "pacbio-hifi"], "Long reads"),
    ("threads", "Threads", "20", "text", "Run settings"),
    ("max_memory", "Max memory (e.g. 50GB)", "", "text", "Run settings"),
    ("species", "species (GetOrganelle -F)", "fungus_mt", "text", "Advanced: organelle"),
    ("skip_decontam", "skip_decontam", False, "bool", "Advanced: organelle"),
    ("decontam_alcr_cutoff", "decontam_alcr_cutoff", "0.1", "text", "Advanced: organelle"),
    ("decontam_sdr_cutoff", "decontam_sdr_cutoff", "0.1", "text", "Advanced: organelle"),
    ("getorganelle_db", "getorganelle_db (override)", "", "text", "Advanced: organelle"),
    ("skip_trimming", "skip_trimming (short reads)", False, "bool", "Advanced: short-read assembly"),
    ("no_careful", "no_careful (SPAdes without --careful)", False, "bool", "Advanced: short-read assembly"),
    ("redundans_limit", "redundans_limit (0-1]", "1", "text", "Advanced: short-read assembly"),
    ("filtlong_min_length", "filtlong_min_length", "1000", "text", "Advanced: long-read assembly"),
    ("filtlong_keep_percent", "filtlong_keep_percent", "90", "text", "Advanced: long-read assembly"),
    ("ont_mode", "ont_mode", "hq", ["hq", "raw"], "Advanced: long-read assembly"),
    ("flye_genome_size", "flye_genome_size (e.g. 35m)", "", "text", "Advanced: long-read assembly"),
    ("flye_asm_coverage", "flye_asm_coverage", "", "text", "Advanced: long-read assembly"),
    ("medaka_model", "medaka_model (override)", "", "text", "Advanced: long-read assembly"),
    ("polish_rounds", "polish_rounds", "3", "text", "Advanced: polishing / QC"),
    ("runmerqury", "runmerqury (short-read mode only)", False, "bool", "Advanced: polishing / QC"),
    ("busco_lineage", "busco_lineage (e.g. fungi_odb12)", "", "text", "Advanced: polishing / QC"),
    ("compleasm_db", "compleasm_db (override)", "", "text", "Advanced: polishing / QC"),
]
DEFAULTS = {f[0]: f[2] for f in FIELDS}
BROWSE = {"outdir": "dir", "r1": "files", "r2": "files", "lr": "files",
          "getorganelle_db": "dir", "compleasm_db": "dir"}


def list_dir(path):
    p = Path(path or Path.home()).expanduser()
    if p.is_file():
        p = p.parent
    while not p.is_dir() and p != p.parent:
        p = p.parent
    out = []
    try:
        for e in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if not e.name.startswith("."):
                out.append({"name": e.name, "dir": e.is_dir()})
    except OSError:
        pass
    return {"path": str(p.resolve()), "parent": str(p.resolve().parent), "entries": out}


def build_command(p):
    """p: dict of field values + profile/resume/stub. Returns (args, errors)."""
    g = lambda k: str(p.get(k) or "").strip()
    errors = []
    if not g("strain"): errors.append("Strain / sample ID is required.")
    if not g("outdir"): errors.append("Output directory is required.")
    r1, r2, lr = g("r1"), g("r2"), g("lr")
    if not (r1 and r2) and not lr:
        errors.append("Provide short reads (R1+R2), long reads, or both.")
    if bool(r1) != bool(r2): errors.append("R1 and R2 must both be set, or both empty.")
    if r1 and r2 and len(r1.split(",")) != len(r2.split(",")):
        errors.append("R1 and R2 must list the same number of files.")
    if lr and not g("lr_type"): errors.append("lr_type is required with long reads.")
    if g("flye_asm_coverage") and not g("flye_genome_size"):
        errors.append("flye_asm_coverage requires flye_genome_size.")
    if errors:
        return None, errors

    args = ["nextflow", "run", "main.nf"]
    for name, _, default, kind, _ in FIELDS:
        if kind == "bool":
            if p.get(name): args.append(f"--{name}")
        elif g(name) and g(name) != default:
            args += [f"--{name}", g(name)]
    # Required/always-sent fields whose default is also "" are covered above.
    if g("profile") not in ("", "standard"): args += ["-profile", g("profile")]
    if p.get("resume"): args.append("-resume")
    if p.get("stub"): args.append("-stub-run")
    return args, []


# Nextflow ellipsizes long process names ("GET…NELLE_FROM_ASSEMBLY") and
# varies the truncation between reprints; match them back to real names.
KNOWN = [n + suf for n in (
    "ALIGN_SR_FOR_QC ALIGN_LR_FOR_QC COMPLEASM DECONTAM_ORGANELLE FASTP FILTLONG "
    "FINAL_QC_REPORT FINALIZE_MITOGENOME FLYE GET_ORGANELLE_FROM_ASSEMBLY "
    "GET_ORGANELLE_FROM_READS GET_ORGANELLE_SETUP MEDAKA POLYPOLISH QUALIMAP_BAMQC "
    "QUAST QUAST_ROUNDS RACON REDUNDANS RENAME_SORT SPADES").split()
    for suf in ("", "_LR", "_SR", "_HYBRID")]


def canon(name):
    if "…" not in name:
        return name
    pre, _, post = name.partition("…")
    m = [n for n in KNOWN if n.startswith(pre) and n.endswith(post)]
    return m[0] if len(m) == 1 else name


def read_failure(workdir):
    """Tail of the failed task's stderr and its command, from the work dir
    Nextflow printed in its own error message."""
    d = Path(workdir)
    out = {"err": "", "cmd": ""}
    for key, name, tail in (("err", ".command.err", True), ("cmd", ".command.sh", False)):
        try:
            lines = (d / name).read_text(errors="replace").splitlines()
            out[key] = "\n".join(lines[-40:] if tail else lines[:40])
        except OSError:
            pass
    return out


_cpu_prev = [None]


def sys_stats():
    """Whole-machine CPU% (since last call) and RAM%; Linux only."""
    try:
        f = [int(x) for x in open("/proc/stat").readline().split()[1:]]
        tot, idle = sum(f), f[3] + f[4]
        prev, _cpu_prev[0] = _cpu_prev[0], (tot, idle)
        cpu = 100 * (1 - (idle - prev[1]) / max(1, tot - prev[0])) if prev else 0
        mem = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
        used = 100 * (1 - mem["MemAvailable"] / mem["MemTotal"])
        return {"cpu": round(cpu), "ram": round(used), "ram_gb": round(mem["MemTotal"] / 1048576)}
    except Exception:
        return None


def _num(v):
    m = re.search(r"[\d,]+\.?\d*", str(v))
    return float(m.group().replace(",", "")) if m else None


def fasta_lengths(path):
    lens, n = [], 0
    try:
        with open(path) as fh:
            for line in fh:
                if line.startswith(">"):
                    if n: lens.append(n)
                    n = 0
                else:
                    n += len(line.strip())
        if n: lens.append(n)
    except OSError:
        return []
    return lens


def quast_rounds(report_dir):
    tsv = Path(report_dir) / "report.tsv"
    if not tsv.is_file():
        return None
    rows = [l.rstrip("\n").split("\t") for l in tsv.read_text().splitlines()]
    hdr = rows[0][1:]
    by = {r[0]: r[1:] for r in rows[1:]}
    pick = lambda k: [_num(x) for x in by.get(k, [])]
    return {"labels": hdr, "N50": pick("N50"), "contigs": pick("# contigs"),
            "length": pick("Total length")}


def results(outdir, strain):
    o = Path(outdir).expanduser()
    if not strain or not o.is_dir():
        return {"found": False}
    q = lambda *p: str(o.joinpath(*p))
    quast = qc.parse_quast(q("qc", "quast", f"{strain}_quast"))
    qmap = qc.parse_qualimap(q("qc", "qualimap", f"{strain}_qualimap"))
    comp_dir = o / "qc" / "compleasm" / f"{strain}_compleasm"
    comp = qc.parse_compleasm(comp_dir) if comp_dir.is_dir() else None
    busco = None
    if comp:
        pcts = {k: _num(comp[k]) for k in ("Single", "Duplicated", "Fragmented", "Interspersed", "Missing") if k in comp}
        busco = {"lineage": comp.get("Lineage"), "total": comp.get("Total BUSCOs"), "pct": pcts}
    contigs = sorted(fasta_lengths(q("assembly", f"{strain}_genome.fasta")), reverse=True)
    mito = fasta_lengths(q("mitochondrion", f"{strain}_mitogenome.fasta"))
    rep = o / "qc" / "final_report" / f"{strain}_final_report.md"
    return {
        "found": bool(quast or qmap or comp or contigs or mito),
        "quast": {k: _num(v) for k, v in (quast or {}).items()},
        "qualimap": qmap, "busco": busco,
        "contigs": contigs[:40], "n_contigs": len(contigs),
        "mito": mito,
        "rounds": quast_rounds(q("qc", "quast_rounds", f"{strain}_quast_rounds")),
        "report": rep.read_text() if rep.is_file() else None,
    }


class Run:
    """Single pipeline run; state is polled by the page."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.proc = None
        self.log = []          # list of [text, is_error]
        self.rows = {}         # name -> dict
        self.order = []
        self.failed = set()
        self.status = "idle"   # idle|running|done|failed
        self.code = None
        self.cmd = ""
        self.t0 = None
        self.times = {}        # name -> [start, end|None]  (epoch seconds)
        self.failures = []     # [{"proc","workdir"}]
        self._last_fail = ""
        self._wd_next = False
        self._err_cache = {}
        self.outdir = ""
        self.strain = ""

    def start(self, params):
        with self.lock:
            if self.status == "running":
                return ["A run is already in progress."]
            args, errors = build_command(params)
            if errors:
                return errors
            env = os.environ.copy()
            for k, key in (("NXF_VER", "nxf_ver"), ("JAVA_HOME", "java_home")):
                if str(params.get(key) or "").strip():
                    env[k] = params[key].strip()
            self.reset()
            self.cmd = " ".join(args)
            self.log.append(["$ " + self.cmd + "\n", False])
            try:
                self.proc = subprocess.Popen(
                    args, cwd=PIPELINE_DIR, env=env, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1,
                )
            except FileNotFoundError:
                self.status = "idle"
                return ["Could not launch `nextflow`. Is it on your PATH?"]
            self.status = "running"
            self.outdir = str(params.get("outdir", "")).strip()
            self.strain = str(params.get("strain", "")).strip()
            self.t0 = time.time()
            threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        return []

    def _read(self, proc):
        for line in proc.stdout:
            with self.lock:
                self._line(line)
        proc.wait()
        with self.lock:
            self.code = proc.returncode
            self.status = "done" if proc.returncode == 0 else "failed"

    def _line(self, line):
        err = line.startswith("ERROR") or "Error executing process" in line
        self.log.append([line if line.endswith("\n") else line + "\n", err])
        m = FAILED_RE.search(line)
        if m:
            self._last_fail = m.group(1)
            self.failed.add(m.group(1).split(" (")[0].strip())
        if line.strip() == "Work dir:":
            self._wd_next = True
        elif self._wd_next and line.strip():
            self._wd_next = False
            self.failures.append({"proc": self._last_fail, "workdir": line.strip()})
        s = STATUS_RE.match(line.strip())
        if s:
            d = s.groupdict()
            d["name"] = canon(d["name"])
            if d["name"] not in self.rows:
                self.order.append(d["name"])
            self.rows[d["name"]] = {
                "name": d["name"], "tag": d["tag"] or "", "done": int(d["done"]),
                "total": int(d["total"]), "hash": d["hash"].strip(),
                "extra": (d["extra"] or "").strip(),
            }
            t = self.times.setdefault(d["name"], [time.time(), None])
            if t[1] is None and 0 < int(d["total"]) <= int(d["done"]):
                t[1] = time.time()

    def stop(self):
        with self.lock:
            if self.proc and self.status == "running":
                self.proc.terminate()
                self.log.append(["\n[GUI] Sent terminate signal to nextflow.\n", True])

    def snapshot(self, since):
        with self.lock:
            rows = []
            for n in self.order:
                r = dict(self.rows[n])
                if n in self.failed: st = "failed"
                elif r["hash"] == "skipped" or "cached" in r["extra"] or "stored" in r["extra"]: st = "cached"
                elif r["total"] and r["done"] >= r["total"]: st = "done"
                elif r["total"]: st = "running"
                else: st = "pending"
                r["state"] = st
                t0 = self.t0 or 0
                st_, en_ = self.times.get(n, [None, None])
                r["start"] = round(st_ - t0, 1) if st_ else None
                r["end"] = round(en_ - t0, 1) if en_ else None
                rows.append(r)
            fails = []
            for f in self.failures:
                if f["workdir"] not in self._err_cache:
                    self._err_cache[f["workdir"]] = read_failure(f["workdir"])
                fails.append({**f, **self._err_cache[f["workdir"]]})
            now = time.time()
            return {
                "elapsed": round(now - self.t0, 1) if self.t0 else 0,
                "sys": sys_stats(), "failures": fails,
                "strain": self.strain, "outdir": self.outdir,
                "status": self.status, "code": self.code, "cmd": self.cmd,
                "rows": rows, "done": sum(r["done"] for r in rows),
                "total": sum(r["total"] for r in rows),
                "log": self.log[since:], "next": len(self.log),
            }


RUN = Run()


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json", code=200):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _local_host(self):
        # Host check blocks DNS-rebinding reads of the directory listing.
        return re.match(r"^(127\.0\.0\.1|localhost)(:\d+)?$", self.headers.get("Host", ""))

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if not self._local_host():
            return self._send("forbidden", "text/plain", 403)
        if path == "/":
            page = HTML.read_text().replace("__FIELDS__", json.dumps(FIELDS)).replace("__BROWSE__", json.dumps(BROWSE)).replace(
                "__ENV__", json.dumps({
                    "nxf_ver": os.environ.get("NXF_VER", "25.04.6"),
                    "java_home": os.environ.get("JAVA_HOME", "/usr/lib/jvm/java-21-openjdk-amd64"),
                }))
            self._send(page, "text/html; charset=utf-8")
        elif path == "/api/state":
            m = re.search(r"since=(\d+)", query)
            self._send(json.dumps(RUN.snapshot(int(m.group(1)) if m else 0)))
        elif path == "/api/results":
            from urllib.parse import parse_qs
            qs = parse_qs(query)
            self._send(json.dumps(results(qs.get("outdir", [""])[0], qs.get("strain", [""])[0])))
        elif path == "/api/ls":
            from urllib.parse import parse_qs
            self._send(json.dumps(list_dir(parse_qs(query).get("path", [""])[0])))
        elif path == "/icon.png":
            self._send((Path(__file__).parent / "icon.png").read_bytes(), "image/png")
        else:
            self._send("not found", "text/plain", 404)

    def do_POST(self):
        # Reject cross-site POSTs: any web page could otherwise hit localhost
        # and launch a pipeline run.
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if not re.match(r"^(127\.0\.0\.1|localhost)(:\d+)?$", host) or (
            origin and not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin)
        ):
            return self._send('{"errors":["forbidden"]}', code=403)
        if self.path == "/api/run":
            n = int(self.headers.get("Content-Length", 0))
            try:
                params = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send('{"errors":["bad JSON"]}', code=400)
            errors = RUN.start(params)
            self._send(json.dumps({"errors": errors}), code=400 if errors else 200)
        elif self.path == "/api/stop":
            RUN.stop()
            self._send("{}")
        elif self.path == "/api/open":
            outdir = Path(RUN.outdir) if getattr(RUN, "outdir", "") else None
            if outdir and outdir.exists():
                subprocess.Popen(["xdg-open", str(outdir)])
            self._send("{}")
        else:
            self._send("not found", "text/plain", 404)

    def log_message(self, *a):
        pass



if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://localhost:{a.port}"
    print(f"bagASM GUI on {url}  (Ctrl+C to quit)")
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
