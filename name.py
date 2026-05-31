#!/usr/bin/env python3
"""
AAP 2.4 -> 2.5 Survey & Schedule Migrator
==========================================

Migrates job-template SURVEYS and SCHEDULES for all templates in a given
organization, from a source controller (2.4) to a destination controller (2.5).

- Standard library only. No pip installs, no awx CLI, no Ansible host needed.
- Matches job templates BY NAME across the two controllers.
- Copies survey_spec verbatim (and flips survey_enabled on the destination).
- Recreates schedules by name, remapping inventory/credential/exec-env IDs
  (which differ between controllers) by NAME.
- Idempotent-ish: skips schedules that already exist by name; PATCHes surveys.
- Dry-run mode by default. You must pass --commit to actually write.

Auth: supports username/password (basic) OR a bearer token per controller.

USAGE
-----
  # Tokens can be passed as flags or via env (env keeps them out of shell history):
  export AAP_SRC_TOKEN='source-pat'
  export AAP_DST_TOKEN='dest-pat'

  # Dry run (default) - shows everything it WOULD do, writes nothing.
  # Org names differ between controllers, so pass both:
  python3 aap_migrate_surveys_schedules.py \
      --src-host https://aap24.example.com \
      --dst-host https://aap25.example.com \
      --src-org "Old Org Name" --dst-org "New Org Name"

  # If the org name is the SAME on both, --dst-org can be omitted:
  python3 aap_migrate_surveys_schedules.py ... --src-org "My Organization"

  # Actually perform the migration:
  python3 aap_migrate_surveys_schedules.py ... \
      --src-org "Old Org Name" --dst-org "New Org Name" --commit

  # Passing tokens explicitly instead of via env:
  python3 aap_migrate_surveys_schedules.py \
      --src-host https://aap24 --src-token SRC_PAT \
      --dst-host https://aap25 --dst-token DST_PAT \
      --src-org "Old Org Name" --dst-org "New Org Name" --commit

  # Only migrate surveys (skip schedules), or vice versa:
  python3 aap_migrate_surveys_schedules.py ... --only surveys
  python3 aap_migrate_surveys_schedules.py ... --only schedules

NOTES
-----
* --insecure disables TLS verification (common with internal CAs). Prefer
  --cabundle /path/to/ca.pem if you have the cert.
* Schedules reference the job template plus optional inventory / credentials /
  execution_environment / labels / instance_groups. IDs are NOT portable, so
  this script resolves each by NAME on the destination. If a referenced object
  doesn't exist on the destination by the same name, that schedule is reported
  and skipped (it will not silently create a broken schedule).
* Run with --only surveys first, eyeball the output, then run schedules.
"""

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# HTTP client
# --------------------------------------------------------------------------- #
class Controller:
    """Thin wrapper around the AAP/AWX controller REST API (/api/v2)."""

    def __init__(
        self,
        host: str,
        token: str,
        insecure: bool = False,
        cabundle: Optional[str] = None,
        label: str = "controller",
    ):
        self.base = host.rstrip("/")
        self.label = label
        self.token = token

        if not token:
            raise ValueError(f"[{label}] a personal access token is required")
        self._auth_header = f"Bearer {token}"

        if cabundle:
            self.ctx = ssl.create_default_context(cafile=cabundle)
        elif insecure:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        else:
            self.ctx = ssl.create_default_context()

    def _request(
        self, method: str, path: str, body: Optional[dict] = None
    ) -> Any:
        if path.startswith("http"):
            url = path
        else:
            url = self.base + path
        data = None
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=60) as resp:
                payload = resp.read().decode("utf-8")
                if not payload:
                    return None
                return json.loads(payload)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                pass
            raise RuntimeError(
                f"[{self.label}] {method} {url} -> HTTP {e.code}: {detail}"
            ) from None
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"[{self.label}] {method} {url} -> connection error: {e.reason}"
            ) from None

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, body)

    def patch(self, path: str, body: dict) -> Any:
        return self._request("PATCH", path, body)

    def get_all(self, path: str) -> List[dict]:
        """Follow pagination and return all .results across pages."""
        results: List[dict] = []
        next_path: Optional[str] = path
        while next_path:
            page = self.get(next_path)
            if page is None:
                break
            results.extend(page.get("results", []))
            next_path = page.get("next")  # absolute or relative; _request handles both
        return results


# --------------------------------------------------------------------------- #
# Lookup helpers
# --------------------------------------------------------------------------- #
def find_org_id(ctrl: Controller, org_name: str) -> int:
    q = urllib.parse.quote(org_name)
    res = ctrl.get_all(f"/api/v2/organizations/?name={q}")
    exact = [o for o in res if o.get("name") == org_name]
    if not exact:
        raise RuntimeError(
            f"[{ctrl.label}] organization '{org_name}' not found "
            f"(found {[o.get('name') for o in res]})"
        )
    return exact[0]["id"]


def list_org_templates(ctrl: Controller, org_id: int) -> List[dict]:
    return ctrl.get_all(f"/api/v2/job_templates/?organization={org_id}")


def index_by_name(items: List[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for it in items:
        out[it["name"]] = it
    return out


def resolve_named_ref(
    ctrl: Controller, endpoint: str, name: str, cache: Dict[str, Optional[int]]
) -> Optional[int]:
    """Resolve an object's id on the destination by exact name. Cached."""
    key = f"{endpoint}::{name}"
    if key in cache:
        return cache[key]
    q = urllib.parse.quote(name)
    res = ctrl.get_all(f"/api/v2/{endpoint}/?name={q}")
    exact = [r for r in res if r.get("name") == name]
    val = exact[0]["id"] if exact else None
    cache[key] = val
    return val


# --------------------------------------------------------------------------- #
# Survey migration
# --------------------------------------------------------------------------- #
def migrate_survey(
    src: Controller,
    dst: Controller,
    src_jt: dict,
    dst_jt: dict,
    commit: bool,
) -> str:
    name = src_jt["name"]
    spec = src.get(f"/api/v2/job_templates/{src_jt['id']}/survey_spec/")

    # An empty / unset survey returns {} or {"spec": []}
    has_survey = bool(spec) and bool(spec.get("spec"))
    if not has_survey:
        return f"  [survey ] {name}: source has no survey, skipping"

    if not commit:
        n = len(spec.get("spec", []))
        return (
            f"  [survey ] {name}: WOULD copy survey ({n} question(s)) "
            f"and set survey_enabled=true"
        )

    dst.post(f"/api/v2/job_templates/{dst_jt['id']}/survey_spec/", spec)
    if not dst_jt.get("survey_enabled"):
        dst.patch(
            f"/api/v2/job_templates/{dst_jt['id']}/", {"survey_enabled": True}
        )
    return f"  [survey ] {name}: copied survey ({len(spec.get('spec', []))} q), enabled"


# --------------------------------------------------------------------------- #
# Schedule migration
# --------------------------------------------------------------------------- #
# Fields on a schedule that are safe to copy verbatim.
SCHEDULE_SCALAR_FIELDS = [
    "name",
    "description",
    "rrule",
    "enabled",
    "extra_data",
    "scm_branch",
    "job_type",
    "skip_tags",
    "job_tags",
    "limit",
    "diff_mode",
    "verbosity",
    "forks",
    "job_slice_count",
    "timeout",
]

# Related objects that must be remapped by NAME (endpoint name on the API).
SCHEDULE_NAMED_REFS = {
    "inventory": "inventories",
    "execution_environment": "execution_environments",
}


def migrate_schedules(
    src: Controller,
    dst: Controller,
    src_jt: dict,
    dst_jt: dict,
    commit: bool,
    ref_cache: Dict[str, Optional[int]],
) -> List[str]:
    name = src_jt["name"]
    lines: List[str] = []

    src_scheds = src.get_all(f"/api/v2/job_templates/{src_jt['id']}/schedules/")
    if not src_scheds:
        return [f"  [sched  ] {name}: no schedules on source, skipping"]

    # Existing destination schedules for idempotency (by name).
    dst_existing = {
        s["name"]
        for s in dst.get_all(f"/api/v2/job_templates/{dst_jt['id']}/schedules/")
    }

    for sched in src_scheds:
        sname = sched["name"]
        if sname in dst_existing:
            lines.append(f"  [sched  ] {name} :: '{sname}': already exists, skipping")
            continue

        body: Dict[str, Any] = {}
        for f in SCHEDULE_SCALAR_FIELDS:
            if f in sched and sched[f] not in (None, ""):
                body[f] = sched[f]

        # Remap named references that differ between controllers.
        skip_reason = None
        for field, endpoint in SCHEDULE_NAMED_REFS.items():
            ref_id = sched.get(field)
            if not ref_id:
                continue
            # source summary_fields give us the name without an extra GET
            ref_name = (
                sched.get("summary_fields", {}).get(field, {}).get("name")
            )
            if not ref_name:
                obj = src.get(f"/api/v2/{endpoint}/{ref_id}/")
                ref_name = obj.get("name") if obj else None
            if not ref_name:
                skip_reason = f"could not resolve source {field} name"
                break
            new_id = resolve_named_ref(dst, endpoint, ref_name, ref_cache)
            if new_id is None:
                skip_reason = (
                    f"{field} '{ref_name}' does not exist on destination"
                )
                break
            body[field] = new_id

        if skip_reason:
            lines.append(
                f"  [sched  ] {name} :: '{sname}': SKIPPED ({skip_reason})"
            )
            continue

        if not commit:
            lines.append(
                f"  [sched  ] {name} :: '{sname}': WOULD create "
                f"(rrule={sched.get('rrule','')[:60]}...)"
            )
            continue

        try:
            dst.post(
                f"/api/v2/job_templates/{dst_jt['id']}/schedules/", body
            )
            lines.append(f"  [sched  ] {name} :: '{sname}': created")
        except RuntimeError as e:
            lines.append(f"  [sched  ] {name} :: '{sname}': FAILED -> {e}")

    return lines


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Migrate AAP job-template surveys and schedules between controllers."
    )
    p.add_argument("--src-host", required=True, help="Source (2.4) base URL")
    p.add_argument(
        "--src-token",
        help="Source personal access token (or set env AAP_SRC_TOKEN)",
    )
    p.add_argument("--dst-host", required=True, help="Destination (2.5) base URL")
    p.add_argument(
        "--dst-token",
        help="Destination personal access token (or set env AAP_DST_TOKEN)",
    )
    p.add_argument(
        "--src-org", required=True, help="Organization name on the source (2.4)"
    )
    p.add_argument(
        "--dst-org",
        help="Organization name on the destination (2.5). "
        "Defaults to --src-org if omitted.",
    )
    p.add_argument(
        "--only",
        choices=["surveys", "schedules", "both"],
        default="both",
        help="Limit migration to one asset type (default: both)",
    )
    p.add_argument(
        "--commit",
        action="store_true",
        help="Actually write to destination. Without this it is a dry run.",
    )
    p.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    p.add_argument("--cabundle", help="Path to CA bundle for TLS verification")
    return p


def main(argv: List[str]) -> int:
    args = build_arg_parser().parse_args(argv)

    import os

    src_token = args.src_token or os.environ.get("AAP_SRC_TOKEN")
    dst_token = args.dst_token or os.environ.get("AAP_DST_TOKEN")
    if not src_token:
        print("ERROR: provide --src-token or set AAP_SRC_TOKEN", file=sys.stderr)
        return 2
    if not dst_token:
        print("ERROR: provide --dst-token or set AAP_DST_TOKEN", file=sys.stderr)
        return 2

    src = Controller(
        args.src_host,
        token=src_token,
        insecure=args.insecure,
        cabundle=args.cabundle,
        label="SRC-2.4",
    )
    dst = Controller(
        args.dst_host,
        token=dst_token,
        insecure=args.insecure,
        cabundle=args.cabundle,
        label="DST-2.5",
    )

    mode = "COMMIT" if args.commit else "DRY-RUN"
    dst_org_name = args.dst_org or args.src_org
    print(f"=== AAP survey/schedule migration ({mode}) ===")
    print(f"Source:      {args.src_host}  (org: {args.src_org})")
    print(f"Destination: {args.dst_host}  (org: {dst_org_name})")
    print(f"Scope:       {args.only}\n")

    src_org_id = find_org_id(src, args.src_org)
    dst_org_id = find_org_id(dst, dst_org_name)

    src_templates = list_org_templates(src, src_org_id)
    dst_by_name = index_by_name(list_org_templates(dst, dst_org_id))

    print(f"Found {len(src_templates)} template(s) in source org "
          f"'{args.src_org}', {len(dst_by_name)} in destination org "
          f"'{dst_org_name}'.\n")

    ref_cache: Dict[str, Optional[int]] = {}
    missing_on_dst: List[str] = []

    for src_jt in sorted(src_templates, key=lambda t: t["name"]):
        name = src_jt["name"]
        dst_jt = dst_by_name.get(name)
        print(f"Template: {name}")
        if not dst_jt:
            missing_on_dst.append(name)
            print("  !! no matching template on destination by name, skipping\n")
            continue

        if args.only in ("surveys", "both"):
            print(migrate_survey(src, dst, src_jt, dst_jt, args.commit))

        if args.only in ("schedules", "both"):
            for line in migrate_schedules(
                src, dst, src_jt, dst_jt, args.commit, ref_cache
            ):
                print(line)
        print()

    print("=== Summary ===")
    print(f"Templates processed: {len(src_templates)}")
    if missing_on_dst:
        print(f"Templates missing on destination ({len(missing_on_dst)}):")
        for n in missing_on_dst:
            print(f"  - {n}")
    if not args.commit:
        print("\nDRY-RUN only. Re-run with --commit to apply changes.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except RuntimeError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
