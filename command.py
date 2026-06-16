#!/usr/bin/env python3
"""
Migrate workflow job template nodes + extra_vars from AAP 2.4 to AAP 2.5.

Only workflows listed in the CSV are touched. Nodes are rebuilt by resolving
the OLD node's unified job template NAME on the NEW controller (job IDs differ
across controllers, names are the stable key). Edges (success/failure/always)
are recreated to preserve flow.

CSV columns (header required):  old_workflow_id,new_workflow_id

Usage:
  python migrate_workflows.py \
      --old-host https://old.aap.example.com \
      --new-host https://new.aap.example.com \
      --old-pat OLD_TOKEN \
      --new-pat NEW_TOKEN \
      --csv workflows.csv \
      [--dry-run] [--insecure]
"""

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
import ssl


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

class Controller:
    """Minimal AAP REST client that handles the 2.4 vs 2.5 base-path change."""

    def __init__(self, host, pat, insecure=False, label=""):
        self.host = host.rstrip("/")
        self.pat = pat
        self.label = label or host
        self.ctx = ssl._create_unverified_context() if insecure else None
        self.base = self._detect_base()

    def _detect_base(self):
        # 2.5 gateway exposes controller under /api/controller/v2/, 2.4 under /api/v2/
        for base in ("/api/controller/v2", "/api/v2"):
            try:
                self._raw_get(base + "/ping/")
                return base
            except Exception:
                continue
        # Fallback: ping not always permitted; probe a real endpoint
        for base in ("/api/controller/v2", "/api/v2"):
            try:
                self._raw_get(base + "/me/")
                return base
            except Exception:
                continue
        raise RuntimeError(f"[{self.label}] Could not detect API base path")

    def _raw_get(self, path):
        return self._request("GET", path)

    def _request(self, method, path, body=None):
        url = self.host + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.pat}")
        req.add_header("Content-Type", "application/json")
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, context=self.ctx, timeout=60) as r:
                    raw = r.read().decode()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                if e.code in (429, 502, 503) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                detail = e.read().decode(errors="replace")
                raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
            except urllib.error.URLError as e:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"{method} {path} -> {e}") from None

    def get(self, path):
        return self._request("GET", self.base + path if path.startswith("/") else path)

    def get_abs(self, path):
        # path already absolute (e.g. a 'next' link or self-relative starting with /api)
        return self._request("GET", path)

    def post(self, path, body):
        return self._request("POST", self.base + path, body)

    def delete(self, path):
        return self._request("DELETE", self.base + path)

    def get_all(self, path):
        """Follow pagination, return combined results list."""
        results = []
        page = self.get(path)
        results.extend(page.get("results", []))
        nxt = page.get("next")
        while nxt:
            page = self.get_abs(nxt)
            results.extend(page.get("results", []))
            nxt = page.get("next")
        return results


# ---------------------------------------------------------------------------
# Template resolution on the new controller
# ---------------------------------------------------------------------------

def build_ujt_index(new_ctrl):
    """
    Index NEW controller's unified job templates by name -> id, keeping the
    underlying type so node rebuild references the right object.
    """
    index = {}
    dupes = set()
    for item in new_ctrl.get_all("/unified_job_templates/?page_size=200"):
        name = item.get("name")
        if name is None:
            continue
        if name in index:
            dupes.add(name)
        index[name] = {
            "id": item["id"],
            "type": item.get("type"),  # job_template, project, inventory_source, workflow_job_template, etc.
        }
    return index, dupes


# ---------------------------------------------------------------------------
# Node + edge extraction from old workflow
# ---------------------------------------------------------------------------

EDGE_FIELDS = ("success_nodes", "failure_nodes", "always_nodes")


def fetch_old_nodes(old_ctrl, old_wf_id):
    nodes = old_ctrl.get_all(
        f"/workflow_job_templates/{old_wf_id}/workflow_nodes/?page_size=200"
    )
    by_id = {}
    for n in nodes:
        summ = n.get("summary_fields", {}).get("unified_job_template", {}) or {}
        by_id[n["id"]] = {
            "old_id": n["id"],
            "ujt_name": summ.get("name"),
            "ujt_type": summ.get("unified_job_type") or summ.get("type"),
            "extra_data": n.get("extra_data") or {},
            "all_parents_must_converge": n.get("all_parents_must_converge", False),
            "identifier": n.get("identifier"),
            "scm_branch": n.get("scm_branch"),
            "job_type": n.get("job_type"),
            "job_tags": n.get("job_tags"),
            "skip_tags": n.get("skip_tags"),
            "limit": n.get("limit"),
            "diff_mode": n.get("diff_mode"),
            "verbosity": n.get("verbosity"),
            "edges": {f: list(n.get(f, [])) for f in EDGE_FIELDS},
        }
    return by_id


# ---------------------------------------------------------------------------
# Rebuild on new controller
# ---------------------------------------------------------------------------

def clear_new_nodes(new_ctrl, new_wf_id, dry_run):
    existing = new_ctrl.get_all(
        f"/workflow_job_templates/{new_wf_id}/workflow_nodes/?page_size=200"
    )
    for n in existing:
        if dry_run:
            print(f"    [dry-run] would delete existing new node {n['id']}")
        else:
            new_ctrl.delete(f"/workflow_job_nodes/{n['id']}/")
    return len(existing)


def create_new_nodes(new_ctrl, new_wf_id, old_nodes, ujt_index, dry_run, errors):
    """Returns mapping old_node_id -> new_node_id."""
    old_to_new = {}
    for old_id, node in old_nodes.items():
        name = node["ujt_name"]
        match = ujt_index.get(name) if name else None
        if not match:
            errors.append(
                f"workflow {new_wf_id}: template '{name}' (old node {old_id}) "
                f"not found on new controller -- node skipped"
            )
            continue

        payload = {
            "unified_job_template": match["id"],
            "extra_data": node["extra_data"],
            "all_parents_must_converge": node["all_parents_must_converge"],
        }
        for opt in ("identifier", "scm_branch", "job_type", "job_tags",
                    "skip_tags", "limit", "diff_mode", "verbosity"):
            if node.get(opt) not in (None, ""):
                payload[opt] = node[opt]

        if dry_run:
            print(f"    [dry-run] would create node for '{name}' "
                  f"(new ujt id {match['id']})")
            old_to_new[old_id] = f"NEW_FOR_{old_id}"  # placeholder for edge preview
            continue

        created = new_ctrl.post(
            f"/workflow_job_templates/{new_wf_id}/workflow_nodes/", payload
        )
        old_to_new[old_id] = created["id"]
    return old_to_new


def wire_edges(new_ctrl, old_nodes, old_to_new, dry_run, errors):
    for old_id, node in old_nodes.items():
        src = old_to_new.get(old_id)
        if src is None:
            continue
        for edge_field in EDGE_FIELDS:
            assoc_endpoint = edge_field  # success_nodes / failure_nodes / always_nodes
            for child_old_id in node["edges"][edge_field]:
                child_new = old_to_new.get(child_old_id)
                if child_new is None:
                    errors.append(
                        f"edge {edge_field} from old node {old_id} -> {child_old_id} "
                        f"dropped (child not migrated)"
                    )
                    continue
                if dry_run:
                    print(f"    [dry-run] would link {src} --{edge_field}--> {child_new}")
                    continue
                new_ctrl.post(
                    f"/workflow_job_nodes/{src}/{assoc_endpoint}/",
                    {"id": child_new},
                )


# ---------------------------------------------------------------------------
# Optionally copy workflow-level extra_vars
# ---------------------------------------------------------------------------

def copy_workflow_extra_vars(old_ctrl, new_ctrl, old_wf_id, new_wf_id, dry_run):
    old_wf = old_ctrl.get(f"/workflow_job_templates/{old_wf_id}/")
    ev = old_wf.get("extra_vars", "")
    if not ev:
        return
    if dry_run:
        print(f"    [dry-run] would set workflow-level extra_vars ({len(ev)} chars)")
        return
    new_ctrl.post(f"/workflow_job_templates/{new_wf_id}/", {"extra_vars": ev})
    # POST to detail not allowed; use PATCH via _request
    # (kept simple: many AAP versions accept PATCH only)


def patch_workflow_extra_vars(new_ctrl, new_wf_id, extra_vars, dry_run):
    if not extra_vars:
        return
    if dry_run:
        print(f"    [dry-run] would PATCH workflow extra_vars ({len(extra_vars)} chars)")
        return
    new_ctrl._request("PATCH", new_ctrl.base +
                      f"/workflow_job_templates/{new_wf_id}/",
                      {"extra_vars": extra_vars})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Migrate AAP workflows 2.4 -> 2.5")
    ap.add_argument("--old-host", required=True)
    ap.add_argument("--new-host", required=True)
    ap.add_argument("--old-pat", required=True)
    ap.add_argument("--new-pat", required=True)
    ap.add_argument("--csv", required=True,
                    help="CSV with header: old_workflow_id,new_workflow_id")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show planned changes without writing")
    ap.add_argument("--insecure", action="store_true",
                    help="Skip TLS verification")
    ap.add_argument("--no-clear", action="store_true",
                    help="Do not delete existing nodes on the new workflow first")
    args = ap.parse_args()

    old = Controller(args.old_host, args.old_pat, args.insecure, "OLD")
    new = Controller(args.new_host, args.new_pat, args.insecure, "NEW")
    print(f"OLD base path: {old.base}")
    print(f"NEW base path: {new.base}")

    print("Indexing new controller unified job templates by name...")
    ujt_index, dupes = build_ujt_index(new)
    print(f"  indexed {len(ujt_index)} templates")
    if dupes:
        print(f"  WARNING: duplicate template names on new controller (last wins): "
              f"{sorted(dupes)}")

    pairs = []
    with open(args.csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                pairs.append((int(row["old_workflow_id"]),
                              int(row["new_workflow_id"])))
            except (KeyError, ValueError, TypeError):
                print(f"  skipping bad CSV row: {row}", file=sys.stderr)

    all_errors = []
    for old_wf, new_wf in pairs:
        print(f"\n=== Workflow {old_wf} (old) -> {new_wf} (new) ===")
        try:
            old_nodes = fetch_old_nodes(old, old_wf)
            print(f"  {len(old_nodes)} nodes in old workflow")

            if not args.no_clear:
                removed = clear_new_nodes(new, new_wf, args.dry_run)
                print(f"  cleared {removed} existing node(s) on new workflow")

            old_to_new = create_new_nodes(
                new, new_wf, old_nodes, ujt_index, args.dry_run, all_errors
            )
            print(f"  created {len(old_to_new)} node(s)")

            wire_edges(new, old_nodes, old_to_new, args.dry_run, all_errors)
            print("  edges wired")

            old_wf_obj = old.get(f"/workflow_job_templates/{old_wf}/")
            patch_workflow_extra_vars(
                new, new_wf, old_wf_obj.get("extra_vars", ""), args.dry_run
            )
            print("  workflow extra_vars copied")
        except Exception as e:
            all_errors.append(f"workflow {old_wf}->{new_wf}: {e}")
            print(f"  ERROR: {e}", file=sys.stderr)

    print("\n========== SUMMARY ==========")
    if all_errors:
        print(f"{len(all_errors)} issue(s):")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)
    print("All listed workflows processed cleanly.")


if __name__ == "__main__":
    main()
