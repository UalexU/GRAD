"""Exercise local PDF storage, review-only answers, and repeated unnumbered employer dialogs."""

import os
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from test_extension import PROFILE, open_gradfill, panel, serve, test_copy


def sample_pdf(path):
    text = (
        "Lafayette College Transcript Totals Undergraduate Attempt Hours Passed Hours Earned Hours "
        "GPA Hours Quality Points GPA Overall 34 33 32 31 110 3.54"
    )
    stream = f"BT /F1 7 Tf 20 200 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1000 400] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(body)
    body += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets)
    body += f"trailer\n<< /Root 1 0 R /Size {len(objects)+1} >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(body)


srv, base = serve()
ext = test_copy(base)
with sync_playwright() as pw:
    ctx=pw.chromium.launch_persistent_context(tempfile.mkdtemp(), executable_path=os.environ['GF_CHROMIUM'], headless=True,args=[f'--disable-extensions-except={ext}',f'--load-extension={ext}'])
    sw=ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event('serviceworker')
    settings=ctx.pages[0]
    settings.goto(sw.url.rsplit('/',1)[0]+'/options.html')
    transcript=Path(tempfile.mkdtemp())/'sample-transcript.pdf'
    sample_pdf(transcript)
    settings.locator('#transcript-files').set_input_files(str(transcript))
    expect(settings.locator('#document-status')).to_have_text('PDFs saved locally.',timeout=25000)
    details=settings.locator('#saved-documents').inner_text()
    assert '32 Lafayette course units' in details and '128 semester credit hours' in details, details
    cv = transcript.with_name('sample-cv.pdf')
    sample_pdf(cv)
    settings.locator('#cv-file').set_input_files(str(cv))
    expect(settings.locator('#saved-documents .entry')).to_have_count(2)
    PROFILE['employment']=[{'employer':'First University','title':'Assistant'},{'employer':'Second Company','title':'Intern','website':'https://employer.example/'}]
    PROFILE['contact']['linkedin']='https://www.linkedin.com/in/example'
    PROFILE['application']={'academic_discipline':'No','english_waiver':'Yes'}
    PROFILE['funding']={'external_funding':'Example Fellowship','nsf_grfp_applied':'No'}
    sw.evaluate('(profile)=>chrome.storage.local.set({profile,settings:{autoFill:true}})',PROFILE)
    page=ctx.new_page()
    sample='''<h1>Resume</h1><form><label for="cv">Upload CV</label><input id="cv" type="file" accept=".pdf"><label for="link">LinkedIn</label><input id="link"><fieldset><legend>Have you ever been issued discipline at an educational institution?</legend><label><input type="radio" name="discipline" value="yes">Yes</label><label><input id="discipline" type="radio" name="discipline" value="no">No</label></fieldset><fieldset><legend>Have you been convicted of a crime?</legend><label><input type="radio" name="crime" value="yes">Yes</label><label><input id="crime" type="radio" name="crime" value="no">No</label></fieldset></form><div id="jobs"></div><script>function addJob(){document.querySelector('#jobs').innerHTML='<div role="dialog" aria-label="Add Employer"><form><label for="org">Organization Name</label><input id="org"><label for="job">Position/Title</label><input id="job"><label for="site">Website</label><input id="site" type="url"></form></div>'}addJob()</script>'''
    page.route(base+'/local-tests',lambda route:route.fulfill(body=sample,content_type='text/html'))
    page.goto(base+'/local-tests')
    open_gradfill(sw)
    expect(page.locator('#link')).to_have_value(PROFILE['contact']['linkedin'])
    expect(page.locator('#org')).to_have_value('')
    assert not page.locator('#discipline').is_checked()
    assert not page.locator('#crime').is_checked()
    picker=panel(page).get_by_label('Which work experience entry')
    expect(picker).to_have_value('')
    picker.select_option('1')
    expect(page.locator('#org')).to_have_value('Second Company')
    expect(page.locator('#site')).to_have_value('https://employer.example/')
    page.evaluate('addJob()')
    panel(page).get_by_role('button',name='Rescan page').click()
    expect(picker).to_have_value('')
    expect(page.locator('#org')).to_have_value('')
    file_picker=panel(page).get_by_label('PDF for Upload CV')
    file_picker.select_option(label='sample-cv.pdf')
    page.once('dialog',lambda dialog:dialog.accept())
    panel(page).get_by_role('button',name='Attach selected PDF').click()
    expect(page.locator('#cv')).to_have_value('C:\\fakepath\\sample-cv.pdf')
    PROFILE["application"]["auto_academic_no"] = "Yes"
    sw.evaluate("(profile) => chrome.storage.local.set({profile})", PROFILE)
    page.reload()
    open_gradfill(sw)
    expect(page.locator("#discipline")).to_be_checked()
    assert not page.locator("#crime").is_checked()
    print('PASS: earned credit extraction, local CV selection, discipline review, and repeated Add Employer forms')
    ctx.close()
