from threading import Thread

import pytest
from werkzeug.serving import make_server


@pytest.fixture
def live_server(app):
    server = make_server('127.0.0.1', 0, app)
    port = server.socket.getsockname()[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_counter_e2e(page, live_server):
    page.goto(f'{live_server}/hellohypergen/counter')
    expect = pytest.importorskip('playwright.sync_api').expect
    expect(page.locator('#n')).to_have_value('0')
    page.locator('#increment').click()
    expect(page.locator('#n')).to_have_value('1')
    page.locator('#increment').click()
    expect(page.locator('#n')).to_have_value('2')


def test_partialload_history_e2e(page, live_server):
    page.goto(f'{live_server}/partialload/page1')
    expect = pytest.importorskip('playwright.sync_api').expect
    expect(page.locator('#partial-page')).to_have_text('Current page: page1')
    page.locator('#page2').click()
    expect(page.locator('#partial-page')).to_have_text('Current page: page2')
    page.go_back()
    expect(page.locator('#partial-page')).to_have_text('Current page: page1')


class TestNativeFormSubmission:
    def test_submits_native_fields_and_file(self, page, live_server):
        expect = pytest.importorskip('playwright.sync_api').expect
        page.goto(f'{live_server}/forms/demo')
        page.locator('#form-name').fill('Grace')
        page.locator('input[name="subscribed"]').check()
        page.locator('input[name="contact"][value="phone"]').check()
        page.locator('select[name="color"]').select_option('green')
        page.locator('#form-file').set_input_files(
            {'name': 'notes.txt', 'mimeType': 'text/plain', 'buffer': b'hello'},
        )
        page.locator('#form-submit').click()

        expect(page.locator('#form-summary')).to_contain_text('name=Grace; tags=python,flask')
        expect(page.locator('#form-summary')).to_contain_text(
            'subscribed=yes; contact=phone; color=green',
        )
        expect(page.locator('#form-summary')).to_contain_text(
            'csrf=example-token; file=notes.txt; arg=callback argument',
        )

    def test_enter_submits_form(self, page, live_server):
        expect = pytest.importorskip('playwright.sync_api').expect
        page.goto(f'{live_server}/forms/demo')
        page.locator('#form-name').fill('Linus')
        page.locator('#form-name').press('Enter')

        expect(page.locator('#form-summary')).to_contain_text('name=Linus')
