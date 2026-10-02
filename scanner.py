#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

STATIC_EXT = {
    "png", "jpg", "jpeg", "gif", "svg", "ico", "webp", "bmp", "tif", "tiff",
    "css", "woff", "woff2", "ttf", "eot", "otf",
    "mp3", "mp4", "avi", "mov", "webm", "wav", "flv",
}


class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    BLUE = "\033[34m"; MAGENTA = "\033[35m"; CYAN = "\033[36m"; GREY = "\033[90m"

    @classmethod
    def disable(cls):
        for k in list(vars(cls)):
            if k.isupper():
                setattr(cls, k, "")


TTY = sys.stderr.isatty()
if not TTY or os.environ.get("NO_COLOR"):
    C.disable()


def banner(domain):
    print(f"{C.BOLD}{C.CYAN}", file=sys.stderr)
    print("  ╔═══════════════════════════════════════════╗", file=sys.stderr)
    print("  ║              recon scanner                ║", file=sys.stderr)
    print("  ╚═══════════════════════════════════════════╝", file=sys.stderr)
    print(f"{C.RESET}   objetivo: {C.BOLD}{domain}{C.RESET}\n", file=sys.stderr)


CURRENT_BAR = None


def _emit(line):
    if CURRENT_BAR is not None:
        CURRENT_BAR.emit(line)
    else:
        print(line, file=sys.stderr, flush=True)


def step_header(n, total, title):
    _emit(f"\n{C.BOLD}{C.BLUE}[{n}/{total}]{C.RESET} {C.BOLD}{title}{C.RESET}")


def info(msg):
    _emit(f"   {C.GREY}·{C.RESET} {msg}")


def found(msg):
    _emit(f"   {C.GREEN}+{C.RESET} {msg}")


def skip(msg):
    _emit(f"   {C.YELLOW}-{C.RESET} {C.DIM}{msg}{C.RESET}")


def resumed(msg):
    _emit(f"   {C.MAGENTA}↻{C.RESET} {msg}")


def warn(msg):
    _emit(f"   {C.YELLOW}{C.BOLD}!{C.RESET} {C.YELLOW}{msg}{C.RESET}")


def saved(path):
    _emit(f"   {C.CYAN}💾 output guardado en {C.BOLD}{path}{C.RESET}")


def _build_big_spinner():
    bit = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (0, 3): 0x40,
           (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (1, 3): 0x80}
    perim = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2),
             (3, 3), (2, 3), (1, 3), (0, 3), (0, 2), (0, 1)]
    frames = []
    arc = 6
    for start in range(len(perim)):
        left = right = 0
        for k in range(arc):
            x, y = perim[(start + k) % len(perim)]
            cell, col = (0, x) if x < 2 else (1, x - 2)
            b = bit[(col, y)]
            if cell == 0:
                left |= b
            else:
                right |= b
        frames.append(chr(0x2800 + left) + chr(0x2800 + right))
    return frames


class Progress:
    WIDTH = 32
    SPIN = _build_big_spinner()

    def __init__(self, total, label):
        global CURRENT_BAR
        self.total = None if total is None else max(total, 1)
        self.label = label
        self.n = 0
        self.frame = 0
        self.lock = threading.Lock()
        self.active = TTY
        self._stop = threading.Event()
        self._thread = None
        self._last_pct = -1
        CURRENT_BAR = self
        if self.active:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        elif self.total:
            self._print_plain(0)

    def _render(self):
        self.frame += 1
        spin = self.SPIN[self.frame % len(self.SPIN)]
        if self.total is None:
            sys.stderr.write(f"\r\033[K   {C.BOLD}{C.CYAN}{spin}{C.RESET} "
                             f"{C.BOLD}{self.n}{C.RESET} {C.DIM}{self.label}{C.RESET}")
        else:
            pct = int(self.n * 100 / self.total)
            filled = int(self.WIDTH * self.n / self.total)
            bar = "█" * filled + C.GREY + "░" * (self.WIDTH - filled) + C.RESET
            color = C.GREEN if self.n >= self.total else C.CYAN
            sys.stderr.write(f"\r\033[K   {C.BOLD}{C.CYAN}{spin}{C.RESET} {color}{bar}{C.RESET} "
                             f"{C.BOLD}{pct:3d}%{C.RESET} "
                             f"{C.DIM}{self.n}/{self.total} {self.label}{C.RESET}")
        sys.stderr.flush()

    def _print_plain(self, pct):
        print(f"   ... {pct:3d}%  {self.n}/{self.total} {self.label}",
              file=sys.stderr, flush=True)

    def _spin(self):
        while not self._stop.wait(0.12):
            with self.lock:
                self._render()

    def update(self, n=None, inc=1):
        with self.lock:
            self.n = n if n is not None else self.n + inc
            if self.total is not None:
                self.n = min(self.n, self.total)
            if self.active:
                self._render()
            elif self.total:
                pct = int(self.n * 100 / self.total)
                if pct != self._last_pct and (pct % 10 == 0 or self.n == self.total):
                    self._last_pct = pct
                    self._print_plain(pct)

    def emit(self, line):
        with self.lock:
            if self.active:
                sys.stderr.write("\r\033[K")
                sys.stderr.write(line + "\n")
                self._render()
            else:
                print(line, file=sys.stderr, flush=True)

    def done(self):
        global CURRENT_BAR
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
        with self.lock:
            if self.active:
                if self.total is not None:
                    self.n = self.total
                self._render()
                sys.stderr.write("\n")
                sys.stderr.flush()
        CURRENT_BAR = None


def find_tool(name):
    path = shutil.which(name)
    if path:
        return path
    go_bin = Path.home() / "go" / "bin" / name
    if go_bin.is_file() and os.access(go_bin, os.X_OK):
        return str(go_bin)
    sys.exit(f"{C.RED}[!]{C.RESET} No se encuentra '{name}'. Instalalo o anadelo al PATH "
             f"(o a ~/go/bin).")


def stream(cmd, stdin_data=None):
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True,
    )

    def feed():
        try:
            if stdin_data:
                proc.stdin.write(stdin_data)
        finally:
            proc.stdin.close()

    threading.Thread(target=feed, daemon=True).start()
    for line in proc.stdout:
        line = line.strip()
        if line:
            yield line
    proc.wait()


def write_lines(path, lines):
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def read_lines(path):
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text().splitlines() if l.strip()]


def host_of(url):
    return (urlsplit(url).hostname or "").lower()


def archive_reachable(timeout=8):
    import urllib.request
    try:
        req = urllib.request.Request("https://web.archive.org/", method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def load_jsonl_inputs(path):
    done = set()
    if path.exists():
        for l in path.read_text().splitlines():
            try:
                done.add(json.loads(l).get("input", ""))
            except json.JSONDecodeError:
                continue
    return done


def load_state(out_dir):
    f = out_dir / ".state.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_state(out_dir, state):
    (out_dir / ".state.json").write_text(json.dumps(state))


def step_subfinder(domain, out_dir, state, max_subs, sf_maxtime, sf_timeout, sf_all):
    step_header(1, 4, f"subfinder · {domain}")
    f = out_dir / "1_subdomains.txt"
    if state.get("step1") and f.exists():
        subs = read_lines(f)
        resumed(f"reanudado: {len(subs)} subdominios ya guardados")
        return subs

    cmd = [find_tool("subfinder"), "-d", domain, "-silent",
           "-timeout", str(sf_timeout), "-max-time", str(sf_maxtime)]
    if sf_all:
        cmd.append("-all")
    subs = {domain.lower()}
    prog = Progress(None, "subdominios encontrados")
    for line in stream(cmd):
        s = line.lower()
        if s not in subs:
            subs.add(s)
            found(s)
            prog.update(n=len(subs) - 1)
    prog.done()
    subs = sorted(subs)
    if max_subs and len(subs) > max_subs:
        info(f"limitando a {max_subs} de {len(subs)} subdominios (--max-subs)")
        subs = subs[:max_subs]
    write_lines(f, subs)
    state["step1"] = True; save_state(out_dir, state)
    info(f"{C.BOLD}{len(subs)}{C.RESET} subdominios")
    saved(f)
    return subs


def step_alive_hosts(subs, out_dir, state, threads, timeout):
    step_header(2, 4, f"httpx · comprobando {len(subs)} hosts")
    raw = out_dir / "2_alive_raw.jsonl"
    alive_f = out_dir / "2_alive_hosts.txt"

    if state.get("step2") and alive_f.exists():
        alive = read_lines(alive_f)
        resumed(f"reanudado: {len(alive)} hosts vivos ya guardados")
        return alive

    already = load_jsonl_inputs(raw)
    pending = [s for s in subs if s not in already]
    if already:
        resumed(f"{len(already)} ya comprobados, quedan {len(pending)}")

    if pending:
        prog = Progress(len(pending), "hosts")
        with raw.open("a") as fh:
            cmd = [find_tool("httpx"), "-silent", "-nc", "-j", "-probe", "-fr",
                   "-t", str(threads), "-timeout", str(timeout)]
            for line in stream(cmd, stdin_data="\n".join(pending)):
                fh.write(line + "\n"); fh.flush()
                prog.update()
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not r.get("failed"):
                    t = f"  {C.DIM}({r.get('title','')[:40]}){C.RESET}" if r.get("title") else ""
                    found(f"{r.get('url')}  {C.GREY}{r.get('status_code')}{C.RESET}{t}")
        prog.done()

    known = {s.lower() for s in subs}
    seen_final, alive, skipped = set(), [], []
    for line in read_lines(raw):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("failed"):
            continue
        url = r.get("url", "")
        src_host = host_of(url) or r.get("input", "").lower()
        final_host = host_of(r.get("final_url") or url) or src_host
        if final_host != src_host and final_host in known:
            skipped.append(f"{url} -> {r.get('final_url')}  (redirect a host ya listado)")
            continue
        if final_host in seen_final:
            skipped.append(f"{url} -> {r.get('final_url')}  (destino duplicado)")
            continue
        seen_final.add(final_host)
        alive.append(url)

    alive.sort()
    write_lines(alive_f, alive)
    write_lines(out_dir / "2_skipped_redirects.txt", skipped)
    state["step2"] = True; save_state(out_dir, state)
    info(f"{C.BOLD}{C.GREEN}{len(alive)}{C.RESET} hosts vivos "
         f"({C.YELLOW}{len(skipped)}{C.RESET} descartados por redirect)")
    saved(alive_f)
    return alive


def step_wayback(alive, out_dir, state, keep_static):
    hosts = sorted({host_of(u) for u in alive if host_of(u)})
    step_header(3, 4, f"waybackurls · {len(hosts)} hosts")
    out_f = out_dir / "3_wayback_urls.txt"
    done_f = out_dir / ".wayback_hosts.txt"

    if state.get("step3") and out_f.exists():
        urls = read_lines(out_f)
        resumed(f"reanudado: {len(urls)} endpoints ya guardados")
        return urls

    done_hosts = set(read_lines(done_f))
    unique = set(read_lines(out_f))
    pending = [h for h in hosts if h not in done_hosts]
    if done_hosts:
        resumed(f"{len(done_hosts)} hosts ya rastreados, quedan {len(pending)}")

    prog = Progress(len(hosts), "hosts")
    prog.update(n=len(done_hosts))
    for h in pending:
        before = len(unique)
        for u in stream([find_tool("waybackurls"), "-no-subs"], stdin_data=h):
            if not u.startswith(("http://", "https://")):
                continue
            if not keep_static:
                ext = urlsplit(u).path.rsplit(".", 1)
                if len(ext) == 2 and ext[1].lower() in STATIC_EXT:
                    continue
            unique.add(u)
        gained = len(unique) - before
        if gained:
            found(f"{h}  {C.GREY}(+{gained} endpoints){C.RESET}")
        write_lines(out_f, sorted(unique))
        done_hosts.add(h); write_lines(done_f, sorted(done_hosts))
        prog.update()
    prog.done()

    result = sorted(unique)
    info(f"{C.BOLD}{len(result)}{C.RESET} endpoints unicos")

    if not result and hosts:
        if not archive_reachable():
            warn("web.archive.org no responde ahora mismo: waybackurls no ha podido")
            warn("consultar el historico. NO es que no haya endpoints.")
            warn("Reintenta mas tarde relanzando el mismo dominio (se reanudara solo).")
            done_f.unlink(missing_ok=True)
            state["step3"] = False; save_state(out_dir, state)
            return result
        warn("waybackurls no devolvio endpoints (el historico puede estar vacio "
             "para estos hosts).")

    state["step3"] = True; save_state(out_dir, state)
    saved(out_f)
    return result


def step_alive_urls(urls, out_dir, state, threads, timeout, exclude_codes):
    step_header(4, 4, f"httpx · validando {len(urls)} endpoints")
    raw = out_dir / "4_alive_raw.jsonl"
    alive_f = out_dir / "4_alive_urls.txt"

    if state.get("step4") and alive_f.exists():
        alive = read_lines(alive_f)
        resumed(f"reanudado: {len(alive)} endpoints activos ya guardados")
        return alive

    if not urls:
        write_lines(alive_f, [])
        write_lines(out_dir / "4_alive_urls_status.tsv", [])
        state["step4"] = True; save_state(out_dir, state)
        info("sin endpoints que validar")
        return []

    already = load_jsonl_inputs(raw)
    pending = [u for u in urls if u not in already]
    if already:
        resumed(f"{len(already)} ya validados, quedan {len(pending)}")

    if pending:
        prog = Progress(len(pending), "urls")
        cmd = [find_tool("httpx"), "-silent", "-nc", "-j", "-probe", "-sc",
               "-t", str(threads), "-timeout", str(timeout)]
        if exclude_codes:
            cmd += ["-fc", exclude_codes]
        with raw.open("a") as fh:
            for line in stream(cmd, stdin_data="\n".join(pending)):
                fh.write(line + "\n"); fh.flush()
                prog.update()
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not r.get("failed"):
                    found(f"{r.get('url')}  {C.GREY}{r.get('status_code')}{C.RESET}")
        prog.done()

    alive, detailed = [], []
    for line in read_lines(raw):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("failed"):
            continue
        url = r.get("url", "")
        alive.append(url)
        detailed.append(f"{r.get('status_code', '')}\t{r.get('content_length', '')}\t{url}")

    alive = sorted(set(alive))
    detailed.sort(key=lambda l: l.split("\t", 2)[2])
    write_lines(alive_f, alive)
    write_lines(out_dir / "4_alive_urls_status.tsv", detailed)
    state["step4"] = True; save_state(out_dir, state)
    info(f"{C.BOLD}{C.GREEN}{len(alive)}{C.RESET} endpoints activos")
    saved(alive_f)
    return alive


def main():
    p = argparse.ArgumentParser(description="subfinder -> httpx -> waybackurls -> httpx")
    p.add_argument("domain")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("-t", "--threads", type=int, default=50)
    p.add_argument("--timeout", type=int, default=7)
    p.add_argument("--exclude-codes", default="404,410")
    p.add_argument("--keep-static", action="store_true")
    p.add_argument("--max-subs", type=int, default=0)
    p.add_argument("--sf-maxtime", type=int, default=5)
    p.add_argument("--sf-timeout", type=int, default=10)
    p.add_argument("--no-all", action="store_true")
    p.add_argument("--fresh", action="store_true")
    args = p.parse_args()

    domain = args.domain.strip().lower()
    if "://" in domain:
        domain = host_of(domain)

    base = Path(args.output) if args.output else (Path(__file__).resolve().parent / "output")
    out_dir = base / domain
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.fresh:
        for f in out_dir.iterdir():
            f.unlink()

    state = load_state(out_dir)

    banner(domain)
    if state:
        resumed(f"progreso previo encontrado en {out_dir}/ (usa --fresh para reiniciar)")

    subs = step_subfinder(domain, out_dir, state, args.max_subs,
                          args.sf_maxtime, args.sf_timeout, not args.no_all)
    alive = step_alive_hosts(subs, out_dir, state, args.threads, args.timeout)
    urls = step_wayback(alive, out_dir, state, args.keep_static)
    final = step_alive_urls(urls, out_dir, state, args.threads, args.timeout, args.exclude_codes)

    print(f"\n{C.BOLD}{C.GREEN}Hecho.{C.RESET} {len(final)} endpoints activos. "
          f"Resultados en {C.BOLD}{out_dir}/{C.RESET}\n", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{C.YELLOW}[!] Cancelado.{C.RESET} El progreso queda guardado; "
              f"relanza el mismo dominio para reanudar.\n", file=sys.stderr)
        sys.exit(130)
