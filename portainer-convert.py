#!/usr/bin/env python3
"""Docker Compose <-> Portainer Stack converter and deployer.

Supports Portainer Compose mode (standalone, not Swarm).

Usage:
  portainer-convert.py to-portainer -i docker-compose.yml --stack-name myapp --deploy
  portainer-convert.py from-portainer --stack-name myapp -o docker-compose.yml
  portainer-convert.py list
  portainer-convert.py config --url http://portainer:9000 --token ptr_xxx
"""

import argparse
import json
import os
import sys

try:
    import yaml
except ImportError:
    print("Error: PyYAML required.  Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests required.  Run: pip install requests", file=sys.stderr)
    sys.exit(1)


CONFIG_FILE = os.path.expanduser("~/.portainer-convert.json")

# Keys that are valid in docker compose but silently ignored or broken in
# Portainer Compose mode.
PORTAINER_UNSUPPORTED = {
    "services": {
        "build",       # Portainer cannot build images
        "stdin_open",  # Compose-only interactive flag
    }
}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    config = {"url": "", "token": "", "endpoint_id": 1}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config.update(json.load(f))
    for env, key in [("PORTAINER_URL", "url"), ("PORTAINER_TOKEN", "token"),
                     ("PORTAINER_ENDPOINT_ID", "endpoint_id")]:
        val = os.environ.get(env)
        if val:
            config[key] = int(val) if key == "endpoint_id" else val
    return config


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Config saved to {CONFIG_FILE}")


# ---------------------------------------------------------------------------
# YAML normalisation
# ---------------------------------------------------------------------------

def normalize_for_portainer(data: dict) -> list[str]:
    """
    Mutate *data* in-place to make it Portainer-Compose-safe.
    Returns a list of human-readable warnings.
    """
    warnings = []
    services = data.get("services") or {}

    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue

        # build: is the main blocker — Portainer can't build images
        if "build" in svc:
            image = (svc.get("image") or
                     f"<replace-with-image-for-{name}>")
            warnings.append(
                f"Service '{name}': 'build:' removed. "
                f"Push the image and set 'image: {image}' manually."
            )
            del svc["build"]
            if "image" not in svc:
                svc["image"] = image

    return warnings


def normalize_for_compose(data: dict) -> list[str]:
    """
    Mutate *data* in-place to make it docker-compose-safe.
    In Compose mode the YAML is already compatible; this is a no-op that
    returns warnings for anything Swarm-specific that was left in.
    """
    warnings = []
    services = data.get("services") or {}

    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        deploy = svc.get("deploy")
        if deploy:
            warnings.append(
                f"Service '{name}': 'deploy:' section is present. "
                "'docker compose up' ignores most deploy keys."
            )

    return warnings


def parse_yaml(content: str) -> dict:
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as e:
        print(f"YAML parse error: {e}", file=sys.stderr)
        sys.exit(1)


def dump_yaml(data: dict) -> str:
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Portainer API helpers
# ---------------------------------------------------------------------------

def api_headers(token: str) -> dict:
    return {"X-API-Key": token, "Content-Type": "application/json"}


def require_connection(args, config: dict) -> tuple[str, str, int]:
    url   = getattr(args, "portainer_url", None) or config.get("url")
    token = getattr(args, "token", None)         or config.get("token")
    eid   = getattr(args, "endpoint_id", None)   or config.get("endpoint_id", 1)
    if not url:
        sys.exit("Error: Portainer URL required. Use --portainer-url or run: config --url <url>")
    if not token:
        sys.exit("Error: API token required. Use --token or run: config --token <token>")
    no_verify = getattr(args, "no_verify_ssl", False) or config.get("no_verify_ssl", False)
    if no_verify:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    verify = not no_verify
    return url.rstrip("/"), token, int(eid), verify


def api_get(url: str, token: str, path: str, verify: bool = True) -> dict | list:
    resp = requests.get(f"{url}{path}", headers=api_headers(token), timeout=15, verify=verify)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        sys.exit(f"API error {resp.status_code}: {resp.text}")
    return resp.json()


def find_stack(stacks: list, name: str) -> dict | None:
    return next((s for s in stacks if s["Name"] == name), None)


def deploy_stack(url: str, token: str, endpoint_id: int,
                 name: str, content: str, update: bool, verify: bool = True):
    """Create or update a Compose-mode stack in Portainer."""
    stacks = api_get(url, token, "/api/stacks", verify=verify)
    existing = find_stack(stacks, name)

    if existing and not update:
        sys.exit(
            f"Stack '{name}' already exists. Add --update to update it, "
            "or choose a different --stack-name."
        )

    headers = api_headers(token)

    if existing:
        stack_id = existing["Id"]
        payload = {
            "stackFileContent": content,
            "env": existing.get("Env") or [],
            "prune": False,
            "pullImage": True,
        }
        resp = requests.put(
            f"{url}/api/stacks/{stack_id}",
            headers=headers,
            json=payload,
            params={"endpointId": endpoint_id},
            timeout=30,
            verify=verify,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            sys.exit(f"Update failed {resp.status_code}: {resp.text}")
        print(f"Stack '{name}' updated successfully (id={stack_id}).")
    else:
        payload = {
            "name": name,
            "stackFileContent": content,
            "env": [],
        }
        # Try current Portainer 2.x endpoint first, fall back to legacy
        for endpoint_path in [
            f"/api/stacks/create/standalone/string?endpointId={endpoint_id}",
            f"/api/stacks?type=2&method=string&endpointId={endpoint_id}",
        ]:
            resp = requests.post(
                f"{url}{endpoint_path}",
                headers=headers,
                json=payload,
                timeout=30,
                verify=verify,
            )
            if resp.status_code != 404:
                break
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            sys.exit(f"Deploy failed {resp.status_code}: {resp.text}")
        stack_id = resp.json().get("Id", "?")
        print(f"Stack '{name}' deployed successfully (id={stack_id}).")


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_to_portainer(args, config: dict):
    # Read input
    if args.input == "-":
        content = sys.stdin.read()
    else:
        if not os.path.exists(args.input):
            sys.exit(f"File not found: {args.input}")
        with open(args.input) as f:
            content = f.read()

    data = parse_yaml(content)
    warnings = normalize_for_portainer(data)
    normalized = dump_yaml(data)

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    # Write output file
    if args.output:
        with open(args.output, "w") as f:
            f.write(normalized)
        print(f"Converted file written to {args.output}")

    # Deploy
    if args.deploy:
        if not args.stack_name:
            sys.exit("Error: --stack-name is required when using --deploy")
        if warnings and not args.force:
            sys.exit(
                "Refusing to deploy because warnings were found (see above).\n"
                "Fix the issues or re-run with --force to deploy anyway."
            )
        url, token, eid, verify = require_connection(args, config)
        deploy_stack(url, token, eid, args.stack_name, normalized, args.update, verify=verify)
    elif not args.output:
        # Default: print to stdout
        print(normalized, end="")


def cmd_from_portainer(args, config: dict):
    url, token, eid, verify = require_connection(args, config)

    stacks = api_get(url, token, "/api/stacks", verify=verify)
    stack = find_stack(stacks, args.stack_name)
    if not stack:
        names = ", ".join(s["Name"] for s in stacks) or "(none)"
        sys.exit(
            f"Stack '{args.stack_name}' not found.\n"
            f"Available stacks: {names}"
        )

    stack_id = stack["Id"]
    file_resp = api_get(url, token, f"/api/stacks/{stack_id}/file", verify=verify)
    content = file_resp["StackFileContent"]

    data = parse_yaml(content)
    warnings = normalize_for_compose(data)
    normalized = dump_yaml(data)

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    if args.output and args.output != "-":
        with open(args.output, "w") as f:
            f.write(normalized)
        print(f"Stack '{args.stack_name}' saved to {args.output}")
    else:
        print(normalized, end="")


def cmd_list(args, config: dict):
    url, token, _, verify = require_connection(args, config)
    stacks = api_get(url, token, "/api/stacks", verify=verify)

    if not stacks:
        print("No stacks found.")
        return

    STATUS = {1: "running", 2: "stopped"}
    print(f"{'ID':<6}  {'Name':<35}  {'Status':<10}  {'Endpoint'}")
    print("-" * 62)
    for s in sorted(stacks, key=lambda x: x["Name"]):
        status = STATUS.get(s.get("Status", 0), "unknown")
        print(f"{s['Id']:<6}  {s['Name']:<35}  {status:<10}  {s.get('EndpointId', '?')}")


def cmd_config(args, config: dict):
    if args.show:
        safe = dict(config)
        if safe.get("token"):
            safe["token"] = safe["token"][:8] + "..."
        print(json.dumps(safe, indent=2))
        return

    changed = False
    for attr, key in [("url", "url"), ("token", "token"), ("endpoint_id", "endpoint_id")]:
        val = getattr(args, attr, None)
        if val is not None:
            config[key] = val
            changed = True
    if getattr(args, "no_verify_ssl", False):
        config["no_verify_ssl"] = True
        changed = True

    if changed:
        save_config(config)
    else:
        print("Nothing to set. Use --show to view current config.")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def add_connection_args(p: argparse.ArgumentParser):
    p.add_argument("--portainer-url", metavar="URL",
                   help="Portainer base URL  (env: PORTAINER_URL)")
    p.add_argument("--token", metavar="TOKEN",
                   help="Portainer API key ptr_…  (env: PORTAINER_TOKEN)")
    p.add_argument("--endpoint-id", type=int, metavar="ID",
                   help="Portainer endpoint ID  (env: PORTAINER_ENDPOINT_ID, default: 1)")
    p.add_argument("--no-verify-ssl", action="store_true",
                   help="Disable SSL certificate verification (for self-signed certs)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portainer-convert",
        description="Convert and sync Docker Compose files with Portainer stacks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Preview what a compose file looks like for Portainer (stdout)
  %(prog)s to-portainer -i docker-compose.yml

  # Save the normalised file
  %(prog)s to-portainer -i docker-compose.yml -o portainer-stack.yml

  # Deploy (create) a new stack
  %(prog)s to-portainer -i docker-compose.yml --stack-name myapp --deploy

  # Update an existing stack
  %(prog)s to-portainer -i docker-compose.yml --stack-name myapp --deploy --update

  # Pull a stack from Portainer as a compose file
  %(prog)s from-portainer --stack-name myapp -o docker-compose.yml

  # Print a stack to stdout
  %(prog)s from-portainer --stack-name myapp

  # List all stacks in Portainer
  %(prog)s list

  # Save connection settings (avoid repeating flags)
  %(prog)s config --url http://portainer:9000 --token ptr_abc123
  %(prog)s config --show
""",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- to-portainer ---
    p_to = sub.add_parser(
        "to-portainer",
        help="Convert a local Compose file for Portainer, and optionally deploy it.",
    )
    p_to.add_argument("-i", "--input", default="-",
                      metavar="FILE",
                      help="Compose file to read (default: stdin)")
    p_to.add_argument("-o", "--output", metavar="FILE",
                      help="Write normalised YAML here (default: stdout unless --deploy)")
    p_to.add_argument("--stack-name", metavar="NAME",
                      help="Stack name in Portainer (required for --deploy)")
    p_to.add_argument("--deploy", action="store_true",
                      help="Deploy the stack to Portainer")
    p_to.add_argument("--update", action="store_true",
                      help="Update stack if it already exists (requires --deploy)")
    p_to.add_argument("--force", action="store_true",
                      help="Deploy even if there are conversion warnings")
    add_connection_args(p_to)

    # --- from-portainer ---
    p_from = sub.add_parser(
        "from-portainer",
        help="Pull a Portainer stack and save it as a Compose file.",
    )
    p_from.add_argument("--stack-name", required=True, metavar="NAME",
                        help="Name of the Portainer stack to pull")
    p_from.add_argument("-o", "--output", default="-", metavar="FILE",
                        help="Output file (default: stdout)")
    add_connection_args(p_from)

    # --- list ---
    p_list = sub.add_parser("list", help="List stacks in Portainer.")
    add_connection_args(p_list)

    # --- config ---
    p_cfg = sub.add_parser("config", help="Save default Portainer connection settings.")
    p_cfg.add_argument("--url", metavar="URL", help="Portainer base URL")
    p_cfg.add_argument("--token", metavar="TOKEN", help="API key (ptr_…)")
    p_cfg.add_argument("--endpoint-id", type=int, metavar="ID",
                       help="Default endpoint ID")
    p_cfg.add_argument("--no-verify-ssl", action="store_true",
                       help="Disable SSL verification by default (for self-signed certs)")
    p_cfg.add_argument("--show", action="store_true", help="Print current config")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    config = load_config()

    dispatch = {
        "to-portainer":   cmd_to_portainer,
        "from-portainer": cmd_from_portainer,
        "list":           cmd_list,
        "config":         cmd_config,
    }
    dispatch[args.command](args, config)


if __name__ == "__main__":
    main()
