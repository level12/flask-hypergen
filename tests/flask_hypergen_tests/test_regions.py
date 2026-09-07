from contextlib import contextmanager

import pytest

from flask_hypergen import FULL, RegionUpdate, hypergen, region, write
from flask_hypergen.context import c
from flask_hypergen.tags import p, span, title


pytestmark = pytest.mark.usefixtures('renderer_context')


class TestRegionDocumentRendering:
    def test_default_boundary(self):
        def template():
            with region('page-content'):
                p('Accounts')

        assert hypergen(template) == (
            '<div data-hypergen-region="page-content" style="display: contents">'
            '<p>Accounts</p>'
            '</div>'
        )

    def test_empty_content(self):
        def template():
            with region('messages'):
                pass

        assert hypergen(template) == (
            '<div data-hypergen-region="messages" style="display: contents"></div>'
        )

    def test_multiple_content_roots(self):
        def template():
            with region('messages'):
                p('First')
                span('Second')

        assert hypergen(template) == (
            '<div data-hypergen-region="messages" style="display: contents">'
            '<p>First</p><span>Second</span>'
            '</div>'
        )

    def test_custom_boundary_tag(self):
        def template():
            with region('document-title', tag=title):
                write('Accounts | Hypergen')

        assert hypergen(template) == (
            '<title data-hypergen-region="document-title">Accounts | Hypergen</title>'
        )

    def test_declaration_order(self):
        def template():
            with region('sidebar'):
                span('Navigation')
            with region('page-content'):
                p('Accounts')

        assert hypergen(template) == (
            '<div data-hypergen-region="sidebar" style="display: contents">'
            '<span>Navigation</span>'
            '</div>'
            '<div data-hypergen-region="page-content" style="display: contents">'
            '<p>Accounts</p>'
            '</div>'
        )

    def test_content_is_decoupled_from_region_name(self):
        def messages():
            p('Saved')

        def template():
            with region('notifications'):
                messages()

        assert hypergen(template) == (
            '<div data-hypergen-region="notifications" style="display: contents"><p>Saved</p></div>'
        )


class TestRegionValidation:
    def test_name_is_required(self):
        def template():
            with region(''):
                pass

        with pytest.raises(ValueError, match=r'^Region name must not be empty\.$'):
            hypergen(template)

    def test_names_are_unique(self):
        def template():
            with region('messages'):
                p('First')
            with region('messages'):
                p('Second')

        with pytest.raises(ValueError, match=r'^Duplicate region name: messages$'):
            hypergen(template)

    def test_nesting_is_rejected(self):
        def template():
            with (
                region('page-content'),
                region('messages'),
            ):
                p('Saved')

        with pytest.raises(ValueError, match=r'^Regions must not be nested\.$'):
            hypergen(template)

    def test_unsupported_swap_is_rejected(self):
        def template():
            with region('messages', swap='outer-morph'):
                p('Saved')

        with pytest.raises(ValueError) as exc_info:
            hypergen(template)

        assert str(exc_info.value) == 'Unsupported region swap: outer-morph'

    def test_unsupported_render_mode_is_rejected(self):
        with pytest.raises(ValueError) as exc_info:
            hypergen(lambda: None, settings={'render_mode': 'fragment'})

        assert str(exc_info.value) == 'Unsupported render mode: fragment'

    def test_partial_requires_an_update(self):
        def template():
            p('Discarded output')

        with pytest.raises(ValueError) as exc_info:
            hypergen(template, settings={'render_mode': 'partial-update'})

        assert str(exc_info.value) == (
            'Partial-update rendering requires a main target or at least one region.'
        )


class TestPartialRegionRendering:
    def test_user_plugin_context_sees_partial_command_state(self):
        observed = []

        class UserPlugin:
            @contextmanager
            def context(self):
                observed.append(
                    'commands' in c.hypergen and 'event_handler_callbacks' in c.hypergen,
                )
                yield

        def template():
            with region('messages'):
                p('Saved')

        hypergen(
            template,
            settings={
                'render_mode': 'partial-update',
                'user_plugins': [UserPlugin()],
            },
        )

        assert observed == [True]

    def test_ordered_updates_include_complete_boundaries(self):
        def template():
            with region('document-title', tag=title):
                write('Accounts | Hypergen')
            with region('messages'):
                pass
            with region('page-content'):
                p('First')
                p('Second')

        result = hypergen(
            template,
            settings={'render_mode': 'partial-update', 'returns': FULL},
        )

        assert result.html == ''
        assert result.region_updates == (
            RegionUpdate(
                region_name='document-title',
                html=('<title data-hypergen-region="document-title">Accounts | Hypergen</title>'),
            ),
            RegionUpdate(
                region_name='messages',
                html='<div data-hypergen-region="messages" style="display: contents"></div>',
            ),
            RegionUpdate(
                region_name='page-content',
                html=(
                    '<div data-hypergen-region="page-content" style="display: contents">'
                    '<p>First</p><p>Second</p>'
                    '</div>'
                ),
            ),
        )
        assert all(type(update) is RegionUpdate for update in result.region_updates)

    def test_unmarked_output_is_discarded_without_main_target(self):
        def template():
            p('Discarded layout output')
            with region('messages'):
                p('Saved')
            p('Also discarded')

        result = hypergen(
            template,
            settings={'render_mode': 'partial-update', 'returns': FULL},
        )

        assert result.html == ''
        assert result.region_updates == (
            RegionUpdate(
                region_name='messages',
                html=(
                    '<div data-hypergen-region="messages" style="display: contents">'
                    '<p>Saved</p>'
                    '</div>'
                ),
            ),
        )

    def test_main_target_keeps_unmarked_output(self):
        def template():
            p('Main content')
            with region('messages'):
                p('Saved')
            p('More main content')

        result = hypergen(
            template,
            settings={
                'render_mode': 'partial-update',
                'returns': FULL,
                'target_id': 'page-content',
            },
        )

        assert result.html == '<p>Main content</p><p>More main content</p>'
        assert result.region_updates == (
            RegionUpdate(
                region_name='messages',
                html=(
                    '<div data-hypergen-region="messages" style="display: contents">'
                    '<p>Saved</p>'
                    '</div>'
                ),
            ),
        )

    def test_main_target_discards_unmarked_base_template_output(self):
        @contextmanager
        def base_template():
            write('Discarded document start')
            with region('messages'):
                p('Saved')
            yield
            write('Discarded document end')

        def template():
            p('Main content')

        result = hypergen(
            template,
            settings={
                'base_template': base_template,
                'render_mode': 'partial-update',
                'returns': FULL,
                'target_id': 'page-content',
            },
        )

        assert result.html == '<p>Main content</p>'
        assert result.region_updates == (
            RegionUpdate(
                region_name='messages',
                html=(
                    '<div data-hypergen-region="messages" style="display: contents">'
                    '<p>Saved</p>'
                    '</div>'
                ),
            ),
        )

    def test_base_template_regions_are_rendered(self):
        @contextmanager
        def base_template():
            write('Discarded document start')
            with region('sidebar'):
                span('Navigation')
            yield
            with region('messages'):
                p('Saved')
            write('Discarded document end')

        def template():
            with region('page-content'):
                p('Accounts')

        result = hypergen(
            template,
            settings={
                'base_template': base_template,
                'render_mode': 'partial-update',
                'returns': FULL,
            },
        )

        assert result.html == ''
        assert [update.region_name for update in result.region_updates] == [
            'sidebar',
            'page-content',
            'messages',
        ]
        assert [update.html for update in result.region_updates] == [
            '<div data-hypergen-region="sidebar" style="display: contents">'
            '<span>Navigation</span>'
            '</div>',
            '<div data-hypergen-region="page-content" style="display: contents">'
            '<p>Accounts</p>'
            '</div>',
            '<div data-hypergen-region="messages" style="display: contents"><p>Saved</p></div>',
        ]

    def test_explicit_inner_morph_swap(self):
        def template():
            with region('messages', swap='inner-morph'):
                p('Saved')

        result = hypergen(
            template,
            settings={'render_mode': 'partial-update', 'returns': FULL},
        )

        assert result.region_updates == (
            RegionUpdate(
                region_name='messages',
                html=(
                    '<div data-hypergen-region="messages" style="display: contents">'
                    '<p>Saved</p>'
                    '</div>'
                ),
                swap='inner-morph',
            ),
        )

    def test_region_name_is_escaped_only_in_html(self):
        region_name = 'alerts "urgent" & more'

        def template():
            with region(region_name):
                p('Saved')

        result = hypergen(
            template,
            settings={'render_mode': 'partial-update', 'returns': FULL},
        )

        assert result.region_updates == (
            RegionUpdate(
                region_name=region_name,
                html=(
                    '<div data-hypergen-region="alerts &quot;urgent&quot; &amp; more" '
                    'style="display: contents"><p>Saved</p></div>'
                ),
            ),
        )
