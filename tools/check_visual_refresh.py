"""Verify both actual local interfaces and capture their presentation.

Start src.local_web with a disposable --store outside the project first.
"""
import argparse,csv,io,json
from decimal import Decimal
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8821');p.add_argument('--evidence',type=Path,required=True);p.add_argument('--workdir',type=Path,required=True);a=p.parse_args()
    out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True);scratch=a.workdir.resolve();scratch.mkdir(parents=True,exist_ok=True)
    errors=[];checks={}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1050},record_video_dir=str(scratch/'video-cache'),record_video_size={'width':1440,'height':1050},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(a.url+'/workspace');expect(page.locator('#demo-sales')).to_be_visible();page.wait_for_timeout(1100)
        page.screenshot(path=str(out/'files.png'),full_page=True)
        page.locator('#demo-sales').click();page.locator('#to-rules').click();expect(page.locator('#field-rows tr')).to_have_count(4);page.wait_for_timeout(800)
        page.screenshot(path=str(out/'mapping.png'),full_page=True)
        page.locator('#run-batch').click();expect(page.locator('#result-content .metric')).to_have_count(4);page.wait_for_timeout(900)
        assert page.locator('#result-content .metric strong').all_text_contents()==['9','5','3','1']
        assert '1247.4428' in page.locator('#result-content').inner_text()
        with page.expect_download() as request:page.get_by_role('link',name='accepted.csv').click()
        download=request.value;destination=scratch/'accepted.csv';download.save_as(destination)
        rows=list(csv.DictReader(io.StringIO(destination.read_text(encoding='utf-8-sig'))))
        assert len(rows)==5 and sum(Decimal(r['amount']) for r in rows)==Decimal('1247.4428')
        assert any(r['line_id']=='0007' and Decimal(r['amount'])==0 for r in rows)
        page.screenshot(path=str(out/'results.png'),full_page=True)
        checks['reusable_batch']={'input':9,'accepted':5,'review':3,'skipped':1,'exact_accepted_total':'1247.4428','leading_zero_ids_and_known_zero_preserved':True,'download_verified':True}
        # Safe repeat goes through the same working form, not a mocked API.
        page.locator('#edit-rules').click();page.locator('#run-batch').click();expect(page.locator('#notice')).to_contain_text('Safe replay')
        checks['replay_reuses_saved_result']=True
        assert not page.evaluate('() => document.documentElement.scrollWidth > innerWidth')
        page.goto(a.url+'/');expect(page.locator('[data-sample="weekly-sales.csv"]')).to_be_visible();page.locator('[data-sample="weekly-sales.csv"]').click()
        expect(page.locator('#metrics .metric')).to_have_count(4)
        assert page.locator('#metrics strong').all_text_contents()==['14','6','7','1']
        assert '2,050 cents' in page.locator('#job-detail').inner_text()
        page.screenshot(path=str(out/'sales-lab.png'),full_page=True)
        page.locator('[data-sample="weekly-sales.csv"]').click();expect(page.locator('#result-message')).to_contain_text('Safe replay')
        page.locator('[data-sample="bad-schema.csv"]').click();expect(page.locator('#result-message')).to_contain_text('quarantine.json');expect(page.locator('#metrics .metric')).to_have_count(0)
        page.screenshot(path=str(out/'quarantine.png'))
        checks['sales_contract']={'input':14,'accepted':6,'review':7,'skipped':1,'net_cents':2050,'safe_replay':True,'quarantine_has_no_fabricated_metrics':True}
        awaitable=page.video;context.close();awaitable.save_as(str(out/'cloud-intake-motion.webm'))
        mobile=browser.new_context(viewport={'width':390,'height':844},reduced_motion='reduce');page=mobile.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        for route,name in [('/workspace','mobile-workspace.png'),('/','mobile-sales-lab.png')]:
            page.goto(a.url+route);page.wait_for_timeout(500)
            assert not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'),route
            assert page.evaluate('() => document.getAnimations().filter(a=>a.playState==="running").length')==0
            page.screenshot(path=str(out/name),full_page=True)
        checks['mobile_390px_no_page_overflow']=True;checks['reduced_motion_no_running_animations']=True
        mobile.close();browser.close()
    assert not errors,errors
    result={'passed':True,'checks':checks,'javascript_errors':errors,'scope':'Local interfaces only. No AWS resources changed or cloud deployment retested.'}
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
