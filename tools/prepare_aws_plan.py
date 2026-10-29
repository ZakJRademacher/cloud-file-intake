"""Prepare an authenticated Terraform plan; never apply or create AWS resources.

Private variables, provider cache, state, full plan and logs remain outside OneDrive.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'cloud-file-intake-tools')
    parser.add_argument('--profile', default='zak-aws')
    args = parser.parse_args()
    private = args.private_dir.resolve()
    if private.is_relative_to(ROOT.parent.parent.resolve()):
        raise SystemExit('Private state and plan files must stay outside the project library.')
    variables = private / 'private.tfvars.json'
    config = json.loads(variables.read_text(encoding='utf-8'))
    if config['aws_region'] != 'us-east-2':
        raise SystemExit('This project is assigned us-east-2.')
    package = ROOT / 'build/lambda.zip'
    expected = json.loads((ROOT / 'evidence/lambda-package.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(package.read_bytes()).hexdigest() == expected['zip_sha256'], 'Package hash mismatch'
    with zipfile.ZipFile(package) as archive:
        for source in (ROOT / 'src').glob('*.py'):
            if source.name not in ('cli.py', 'local_web.py'):
                assert archive.read('src/' + source.name) == source.read_bytes(), f'Rebuild package: {source.name}'
    state = private / 'state'
    state.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(AWS_PROFILE=args.profile, AWS_REGION=config['aws_region'],
               AWS_EC2_METADATA_DISABLED='true', TF_DATA_DIR=str(private / 'terraform-live-data'))
    executable = private / 'terraform-1.17.0/terraform.exe'
    commands = [
        ('init', ['init', '-input=false', '-no-color', '-reconfigure', f'-backend-config=path={(state / "terraform.tfstate").as_posix()}']),
        ('plan', ['plan', '-input=false', '-no-color', '-lock-timeout=30s', f'-var-file={variables}', f'-out={private / "review.tfplan"}']),
    ]
    for name, command in commands:
        run = subprocess.run([str(executable), *command], cwd=ROOT / 'infra', env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
        (private / f'authenticated-{name}.log').write_text(run.stdout, encoding='utf-8')
        print(f'{name}: exit {run.returncode}', flush=True)
        if run.returncode:
            print(run.stdout[-6000:])
            raise SystemExit(run.returncode)
    shown = subprocess.run([str(executable), 'show', '-json', str(private / 'review.tfplan')],
                           cwd=ROOT / 'infra', env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           encoding='utf-8', errors='replace', check=True)
    (private / 'review-plan.json').write_text(shown.stdout, encoding='utf-8')
    plan = json.loads(shown.stdout)
    changes = [item for item in plan.get('resource_changes', []) if item.get('mode') == 'managed']
    summary = {
        'verified_at_utc': datetime.now(timezone.utc).isoformat(),
        'region': config['aws_region'], 'profile': args.profile,
        'stage': 'Authenticated Terraform plan only', 'applied': False,
        'changes_by_action': dict(Counter(','.join(item['change']['actions']) for item in changes)),
        'resources_by_type': dict(Counter(item['type'] for item in changes)),
        'addresses': [item['address'] for item in changes],
        'lambda_zip_sha256': expected['zip_sha256'],
        'plan_sha256': hashlib.sha256((private / 'review.tfplan').read_bytes()).hexdigest(),
        'private_plan_location': 'Windows local application data, outside OneDrive',
    }
    (ROOT / 'evidence/authenticated-plan-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
