"""Validate Terraform and run mocked plans. Does not deploy or authenticate to AWS."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terraform',default=str(Path(os.environ.get('LOCALAPPDATA','.'))/'cloud-file-intake-tools/terraform-1.17.0/terraform.exe'))
    args=parser.parse_args()
    env=os.environ.copy()
    env['TF_DATA_DIR']=str(Path(os.environ.get('LOCALAPPDATA','.'))/'cloud-file-intake-tools/terraform-data')
    env['AWS_EC2_METADATA_DISABLED']='true'
    evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
    record={'deployed':False,'aws_account_required':False,'checks':[]}
    for name,command in [('terraform-format',['fmt','-check','-recursive']),
                         ('terraform-validate',['validate','-no-color']),
                         ('terraform-mock-test',['test','-no-color'])]:
        result=subprocess.run([args.terraform,*command],cwd=ROOT/'infra',env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        (evidence/(name+'.log')).write_text(result.stdout,encoding='utf-8')
        record['checks'].append({'check':name,'passed':result.returncode==0})
        print(result.stdout)
        if result.returncode:
            (evidence/'infrastructure-verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
            raise SystemExit(result.returncode)
    (evidence/'infrastructure-verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
