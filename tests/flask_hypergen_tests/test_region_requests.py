from contextlib import contextmanager
from html import unescape

from flask import request
import pytest

from flask_hypergen import (
    hypergen_partial_response,
    is_hypergen_partial_request,
    loads,
    region,
    write,
)
from flask_hypergen.tags import p


PARTIAL_HEADERS = {'X-Hypergen-Partial': '1'}


class TestExplicitRegionRoutes:
    @pytest.mark.parametrize(
        ('header_value', 'expected'),
        [(None, False), ('0', False), ('1', True)],
    )
    def test_partial_request_detection(self, region_app, header_value, expected):
        headers = {} if header_value is None else {'X-Hypergen-Partial': header_value}

        with region_app.test_request_context(headers=headers):
            assert is_hypergen_partial_request(request) is expected

    def test_normal_get_returns_complete_document(self, region_client):
        response = region_client.get('/regions/one')
        body = response.get_data(as_text=True)

        assert response.status_code == 200
        assert response.mimetype == 'text/html'
        assert body.startswith('<!DOCTYPE html><html>')
        assert body.count('data-hypergen-region=') == 5
        assert (
            '<title data-hypergen-region="document-title">Page one | Region tests</title>' in body
        )
        assert 'data-hypergen-region="navigation"' in body
        assert 'data-hypergen-region="messages"' in body
        assert 'data-hypergen-region="untouched"' in body
        assert 'data-hypergen-region="page-content"' in body
        assert 'Current page: one' in body

    def test_partial_get_returns_one_ordered_batch(self, region_client):
        response = region_client.get('/regions/two', headers=PARTIAL_HEADERS)

        assert response.status_code == 200
        assert response.mimetype == 'application/json'
        commands = loads(response.get_data(as_text=True))
        batches = [command for command in commands if command[0] == 'hypergen.applyUpdates']
        assert len(batches) == 1

        updates = batches[0][1]
        assert [update['region'] for update in updates] == [
            'document-title',
            'navigation',
            'messages',
            'page-content',
        ]
        assert all(update['swap'] == 'inner-morph' for update in updates)
        assert updates[0]['html'] == (
            '<title data-hypergen-region="document-title">Page two | Region tests</title>'
        )
        assert updates[2]['html'] == (
            '<div data-hypergen-region="messages" style="display: contents"></div>'
        )
        assert 'Current page: two' in updates[3]['html']
        callbacks = batches[0][2]
        assert sorted(callbacks) == [
            'navigation-callback__onclick',
            'updated-callback__onclick',
        ]

    def test_main_target_and_regions_discard_base_scaffolding(self, region_app):
        @contextmanager
        def base_template():
            write('Discarded document start')
            with region('messages'):
                p('Saved')
            yield
            write('Discarded document end')

        def main_template():
            p('Main content')

        @region_app.get('/main-plus-regions')
        def main_plus_regions():
            return hypergen_partial_response(
                main_template,
                base_template=base_template,
                target_id='main-target',
            )

        response = region_app.test_client().get('/main-plus-regions')
        commands = loads(response.get_data(as_text=True))
        batch = next(command for command in commands if command[0] == 'hypergen.applyUpdates')

        assert response.status_code == 200
        assert [update['region'] for update in batch[1]] == ['messages']
        assert batch[3] == {
            'target': 'main-target',
            'swap': 'inner-morph',
            'html': '<p>Main content</p>',
        }
        assert all(command[0] != 'hypergen.morph' for command in commands)

    def test_partial_navigation_routes_are_get_only(self, region_client):
        response = region_client.post('/regions/two', headers=PARTIAL_HEADERS)

        assert response.status_code == 405

    def test_links_retain_normal_href_fallbacks(self, region_client):
        body = unescape(region_client.get('/regions/one').get_data(as_text=True))

        assert '<a href="/regions/two" id="push-two"' in body
        assert "hypergen.navigate(event, this.href, 'push')" in body
        assert '<a href="/regions/three" id="replace-three"' in body
        assert '<a href="/regions/three" id="no-history-three"' in body
