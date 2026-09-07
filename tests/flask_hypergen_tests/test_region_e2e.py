from playwright.sync_api import Error, expect
import pytest


def load_region_page(page, region_live_server, page_name='one'):
    page.goto(f'{region_live_server}/regions/{page_name}')


class TestApplyUpdates:
    def test_empty_single_and_multiple_roots(self, page, region_live_server):
        load_region_page(page, region_live_server)

        page.evaluate(
            """
            updates => hypergen.applyUpdates(updates)
            """,
            [
                {
                    'region': 'messages',
                    'swap': 'inner-morph',
                    'html': (
                        '<div data-hypergen-region="messages" style="display: contents"></div>'
                    ),
                },
                {
                    'region': 'navigation',
                    'swap': 'inner-morph',
                    'html': (
                        '<div data-hypergen-region="navigation" style="display: contents">'
                        '<nav>Single root</nav></div>'
                    ),
                },
                {
                    'region': 'page-content',
                    'swap': 'inner-morph',
                    'html': (
                        '<div data-hypergen-region="page-content" style="display: contents">'
                        '<p>First root</p><p>Second root</p></div>'
                    ),
                },
            ],
        )

        expect(page.locator('[data-hypergen-region="messages"]')).to_be_empty()
        expect(page.locator('[data-hypergen-region="navigation"]')).to_have_text('Single root')
        expect(page.locator('[data-hypergen-region="page-content"] > p')).to_have_count(2)

    def test_undeclared_region_is_unchanged(self, page, region_live_server):
        load_region_page(page, region_live_server)
        untouched = page.locator('[data-hypergen-region="untouched"]')
        before = untouched.inner_html()

        page.evaluate(
            """
            updates => hypergen.applyUpdates(updates)
            """,
            [
                {
                    'region': 'messages',
                    'swap': 'inner-morph',
                    'html': (
                        '<div data-hypergen-region="messages" style="display: contents">'
                        '<p>Changed</p></div>'
                    ),
                },
            ],
        )

        assert untouched.inner_html() == before

    def test_focus_is_restored_once_after_batch(self, page, region_live_server):
        load_region_page(page, region_live_server)
        field = page.locator('#focus-field')
        field.focus()
        field.fill('User-entered value')

        page.evaluate(
            """
            updates => hypergen.applyUpdates(updates)
            """,
            [
                {
                    'region': 'messages',
                    'swap': 'inner-morph',
                    'html': (
                        '<div data-hypergen-region="messages" style="display: contents"></div>'
                    ),
                },
                {
                    'region': 'page-content',
                    'swap': 'inner-morph',
                    'html': (
                        '<div data-hypergen-region="page-content" style="display: contents">'
                        '<input id="focus-field" value="Server value">'
                        '</div>'
                    ),
                },
            ],
        )

        expect(field).to_be_focused()
        expect(field).to_have_value('User-entered value')

    def test_exact_region_name_lookup_keeps_boundary_stable(self, page, region_live_server):
        load_region_page(page, region_live_server)
        page.evaluate(
            """
            () => {
                const boundary = document.createElement('div')
                boundary.setAttribute('data-hypergen-region', 'alerts "urgent" [primary]')
                boundary.textContent = 'Before'
                document.body.appendChild(boundary)
                window.exactRegionBoundary = boundary
            }
            """,
        )

        page.evaluate(
            """
            updates => hypergen.applyUpdates(updates)
            """,
            [
                {
                    'region': 'alerts "urgent" [primary]',
                    'swap': 'inner-morph',
                    'html': (
                        "<div data-hypergen-region='alerts &quot;urgent&quot; [primary]'>"
                        '<p>After</p></div>'
                    ),
                },
            ],
        )

        assert page.evaluate(
            """
            window.exactRegionBoundary === [...document.querySelectorAll('[data-hypergen-region]')]
                .find(element => element.getAttribute('data-hypergen-region') ===
                    'alerts "urgent" [primary]')
            """,
        )
        assert page.evaluate('window.exactRegionBoundary.textContent') == 'After'

    def test_restricted_context_boundary(self, page, region_live_server):
        load_region_page(page, region_live_server)
        page.evaluate(
            """
            () => document.body.insertAdjacentHTML(
                'beforeend',
                '<table><tbody><tr id="row-region" data-hypergen-region="row">' +
                '<td>Before</td></tr></tbody></table>',
            )
            """,
        )

        page.evaluate(
            """
            updates => hypergen.applyUpdates(updates)
            """,
            [
                {
                    'region': 'row',
                    'swap': 'inner-morph',
                    'html': (
                        '<tr data-hypergen-region="row">'
                        '<td id="updated-cell" data-state="new">After</td></tr>'
                    ),
                },
            ],
        )

        cell = page.locator('#row-region > #updated-cell')
        expect(cell).to_have_count(1)
        expect(cell).to_have_attribute('data-state', 'new')
        expect(cell).to_have_text('After')

    def test_main_target_joins_region_batch_focus_cycle(self, page, region_live_server):
        load_region_page(page, region_live_server)
        page.evaluate(
            """
            () => {
                document.body.insertAdjacentHTML(
                    'beforeend',
                    '<div id="main-target"><input id="main-draft" value="Initial"></div>',
                )
            }
            """,
        )
        draft = page.locator('#main-draft')
        draft.focus()
        draft.fill('User draft')
        page.evaluate(
            """
            () => {
                window.focusCalls = 0
                const originalFocus = HTMLElement.prototype.focus
                HTMLElement.prototype.focus = function(...args) {
                    window.focusCalls += 1
                    return originalFocus.apply(this, args)
                }
            }
            """,
        )

        page.evaluate(
            """
            () => hypergen.applyUpdates(
                [{
                    region: 'messages',
                    swap: 'inner-morph',
                    html: '<div data-hypergen-region="messages"><input autofocus></div>',
                }],
                {},
                {
                    target: 'main-target',
                    swap: 'inner-morph',
                    html: '<input id="main-draft" value="Server value">' +
                        '<p id="main-updated">Updated</p>',
                },
            )
            """,
        )

        expect(page.locator('#main-updated')).to_have_text('Updated')
        expect(draft).to_have_value('User draft')
        assert page.evaluate('window.focusCalls') == 1

    def test_autofocus_runs_once_per_batch(self, page, region_live_server):
        load_region_page(page, region_live_server)
        page.evaluate(
            """
            () => {
                window.focusCalls = 0
                const originalFocus = HTMLElement.prototype.focus
                HTMLElement.prototype.focus = function(...args) {
                    window.focusCalls += 1
                    return originalFocus.apply(this, args)
                }
            }
            """,
        )

        page.evaluate(
            """
            updates => hypergen.applyUpdates(updates)
            """,
            [
                {
                    'region': 'messages',
                    'swap': 'inner-morph',
                    'html': (
                        '<div data-hypergen-region="messages"><input autofocus>'
                        '<script>window.autofocusSeenDuringMorph = '
                        'document.querySelectorAll("[autofocus]").length</script></div>'
                    ),
                },
                {
                    'region': 'page-content',
                    'swap': 'inner-morph',
                    'html': '<div data-hypergen-region="page-content"><input autofocus></div>',
                },
            ],
        )

        assert page.evaluate('window.focusCalls') == 1
        assert page.evaluate('window.autofocusSeenDuringMorph') >= 1

    def test_batch_events_wrap_region_events(self, page, region_live_server):
        load_region_page(page, region_live_server)
        page.evaluate(
            """
            () => {
                window.updateEvents = []
                for (const name of [
                    'hypergen.applyUpdates.before',
                    'hypergen.applyUpdate.before',
                    'hypergen.applyUpdate.after',
                    'hypergen.applyUpdates.after',
                ]) {
                    document.addEventListener(name, () => window.updateEvents.push(name))
                }
            }
            """,
        )

        page.evaluate(
            """
            () => hypergen.applyUpdates([{
                region: 'messages',
                swap: 'inner-morph',
                html: '<div data-hypergen-region="messages"></div>',
            }])
            """,
        )

        assert page.evaluate('window.updateEvents') == [
            'hypergen.applyUpdates.before',
            'hypergen.applyUpdate.before',
            'hypergen.applyUpdate.after',
            'hypergen.applyUpdates.after',
        ]

    def test_callbacks_are_registered_before_updated_scripts_run(
        self,
        page,
        region_live_server,
    ):
        load_region_page(page, region_live_server)
        page.evaluate(
            """
            () => {
                window.regionEvents = []
                window.regionTest = {record: value => window.regionEvents.push(value)}
                hypergen.applyUpdates(
                    [{
                        region: 'page-content',
                        swap: 'inner-morph',
                        html: '<div data-hypergen-region="page-content">' +
                            '<button id="immediate-callback" ' +
                            'onclick="hypergen.event(event, &quot;' +
                            'immediate-callback__onclick&quot;)">' +
                            'Record</button>' +
                            '<script>document.getElementById("immediate-callback")' +
                            '.click()</script>' +
                            '</div>',
                    }],
                    {'immediate-callback__onclick': ['regionTest.record', 'during-morph']},
                )
            }
            """,
        )

        assert page.evaluate('window.regionEvents') == ['during-morph']


class TestApplyUpdatesValidation:
    def test_missing_main_target_prevents_region_mutation(self, page, region_live_server):
        load_region_page(page, region_live_server)
        messages = page.locator('[data-hypergen-region="messages"]')
        before = messages.inner_html()

        with pytest.raises(Error) as exc_info:
            page.evaluate(
                """
                () => hypergen.applyUpdates(
                    [{
                        region: 'messages',
                        swap: 'inner-morph',
                        html: '<div data-hypergen-region="messages"><p>Changed</p></div>',
                    }],
                    {},
                    {
                        target: 'missing-main',
                        swap: 'inner-morph',
                        html: '<p>Main update</p>',
                    },
                )
                """,
            )

        assert 'Hypergen main target "missing-main" must exist exactly once.' in str(exc_info.value)
        assert messages.inner_html() == before

    @pytest.mark.parametrize('reverse_order', [False, True])
    def test_nested_existing_targets_are_rejected(
        self,
        page,
        region_live_server,
        reverse_order,
    ):
        load_region_page(page, region_live_server)
        page.evaluate(
            """
            () => document.body.insertAdjacentHTML(
                'beforeend',
                '<div data-hypergen-region="outer"><p>Outer before</p>' +
                '<div data-hypergen-region="inner"><p>Inner before</p></div></div>',
            )
            """,
        )
        outer = page.locator('[data-hypergen-region="outer"]')
        before = outer.inner_html()
        updates = [
            {
                'region': 'outer',
                'swap': 'inner-morph',
                'html': '<div data-hypergen-region="outer"><p>Outer after</p></div>',
            },
            {
                'region': 'inner',
                'swap': 'inner-morph',
                'html': '<div data-hypergen-region="inner"><p>Inner after</p></div>',
            },
        ]
        if reverse_order:
            updates.reverse()

        with pytest.raises(Error) as exc_info:
            page.evaluate('updates => hypergen.applyUpdates(updates)', updates)

        assert 'Hypergen update targets "outer" and "inner" must not overlap.' in str(
            exc_info.value,
        )
        assert outer.inner_html() == before

    def test_missing_region_prevents_all_mutation(self, page, region_live_server):
        load_region_page(page, region_live_server)
        messages = page.locator('[data-hypergen-region="messages"]')
        before = messages.inner_html()

        with pytest.raises(
            Error,
            match=r'Hypergen region "missing" must exist exactly once\.',
        ):
            page.evaluate(
                """
                updates => hypergen.applyUpdates(updates)
                """,
                [
                    {
                        'region': 'messages',
                        'swap': 'inner-morph',
                        'html': (
                            '<div data-hypergen-region="messages"><p>Must not apply</p></div>'
                        ),
                    },
                    {
                        'region': 'missing',
                        'swap': 'inner-morph',
                        'html': '<div data-hypergen-region="missing"><p>Missing</p></div>',
                    },
                ],
            )

        assert messages.inner_html() == before

    @pytest.mark.parametrize(
        ('html', 'message'),
        [
            (
                '<div><p>Missing marker</p></div>',
                'Returned update for region "messages" must contain exactly one region boundary.',
            ),
            (
                '<div data-hypergen-region="other"><p>Wrong name</p></div>',
                'Returned region "other" does not match update "messages".',
            ),
            (
                '<section data-hypergen-region="messages"><p>Wrong tag</p></section>',
                'Returned region "messages" must use <div>, not <section>.',
            ),
            (
                '<div data-hypergen-region="messages"></div><p>Extra root</p>',
                'Returned update for region "messages" must contain exactly one region boundary.',
            ),
            (
                '<div><div data-hypergen-region="messages"></div></div>',
                'Returned update for region "messages" must contain exactly one region boundary.',
            ),
        ],
    )
    def test_returned_boundary_is_validated(self, page, region_live_server, html, message):
        load_region_page(page, region_live_server)

        with pytest.raises(Error) as exc_info:
            page.evaluate(
                """
                update => hypergen.applyUpdates([update])
                """,
                {'region': 'messages', 'swap': 'inner-morph', 'html': html},
            )

        assert message in str(exc_info.value)

    def test_malformed_later_update_prevents_earlier_mutation(self, page, region_live_server):
        load_region_page(page, region_live_server)
        messages = page.locator('[data-hypergen-region="messages"]')
        before = messages.inner_html()

        with pytest.raises(Error) as exc_info:
            page.evaluate(
                """
                updates => hypergen.applyUpdates(updates)
                """,
                [
                    {
                        'region': 'messages',
                        'swap': 'inner-morph',
                        'html': '<div data-hypergen-region="messages"><p>Changed</p></div>',
                    },
                    {
                        'region': 'page-content',
                        'swap': 'inner-morph',
                        'html': '<div><p>Missing marker</p></div>',
                    },
                ],
            )

        assert (
            'Returned update for region "page-content" must contain exactly one region boundary.'
            in str(exc_info.value)
        )
        assert messages.inner_html() == before

    def test_duplicate_existing_region_prevents_mutation(self, page, region_live_server):
        load_region_page(page, region_live_server)
        messages = page.locator('[data-hypergen-region="messages"]').first
        before = messages.inner_html()
        page.evaluate(
            """
            () => document.body.appendChild(
                document.querySelector('[data-hypergen-region="messages"]').cloneNode(true),
            )
            """,
        )

        with pytest.raises(Error) as exc_info:
            page.evaluate(
                """
                () => hypergen.applyUpdates([{
                    region: 'messages',
                    swap: 'inner-morph',
                    html: '<div data-hypergen-region="messages"><p>Changed</p></div>',
                }])
                """,
            )

        assert 'Hypergen region "messages" must exist exactly once.' in str(exc_info.value)
        assert messages.inner_html() == before

    @pytest.mark.parametrize(
        ('updates', 'message'),
        [
            (
                [
                    {
                        'region': 'messages',
                        'swap': 'outer-morph',
                        'html': '<div data-hypergen-region="messages"></div>',
                    },
                ],
                'Unsupported region swap: outer-morph',
            ),
            (
                [
                    {
                        'region': 'messages',
                        'swap': 'inner-morph',
                        'html': '<div data-hypergen-region="messages"></div>',
                    },
                    {
                        'region': 'messages',
                        'swap': 'inner-morph',
                        'html': '<div data-hypergen-region="messages"></div>',
                    },
                ],
                'Hypergen region "messages" may only be updated once per batch.',
            ),
        ],
    )
    def test_invalid_batch_update_is_rejected(
        self,
        page,
        region_live_server,
        updates,
        message,
    ):
        load_region_page(page, region_live_server)

        with pytest.raises(Error) as exc_info:
            page.evaluate('updates => hypergen.applyUpdates(updates)', updates)

        assert message in str(exc_info.value)


class TestRegionNavigation:
    def test_stale_response_does_not_overwrite_newer_navigation(self, page, region_live_server):
        load_region_page(page, region_live_server)

        current_page = page.evaluate(
            """
            async () => {
                const pending = {}
                window.fetch = url => new Promise(resolve => { pending[url] = resolve })
                const response = text => ({ok: true, status: 200, text: async () => text})
                const commands = pageName => JSON.stringify([[
                    'hypergen.applyUpdates',
                    [{
                        region: 'page-content',
                        swap: 'inner-morph',
                        html: '<div data-hypergen-region="page-content">' +
                            '<p id="current-page">Current page: ' + pageName + '</p></div>',
                    }],
                    {},
                    null,
                ]])
                const olderUrl = new URL('/regions/two', window.location.href).href
                const newerUrl = new URL('/regions/one', window.location.href).href
                const older = hypergen.navigate(null, olderUrl, 'none')
                const newer = hypergen.navigate(null, newerUrl, 'none')

                pending[newerUrl](response(commands('newer')))
                await newer
                pending[olderUrl](response(commands('stale')))
                await older
                return document.getElementById('current-page').textContent
            }
            """,
        )

        assert current_page == 'Current page: newer'

    def test_command_redirect_response_is_applied(self, page, region_live_server):
        load_region_page(page, region_live_server)

        redirected_to = page.evaluate(
            """
            async () => {
                window.fetch = async () => ({
                    ok: false,
                    status: 302,
                    text: async () => '[["hypergen.redirect", "/redirected"]]',
                })
                window.redirectedTo = null
                Object.defineProperty(hypergen, 'redirect', {
                    configurable: true,
                    value: url => { window.redirectedTo = url },
                })
                await hypergen.navigate(null, '/redirect-response', 'none')
                return window.redirectedTo
            }
            """,
        )

        assert redirected_to == '/redirected'

    def test_partial_get_updates_every_declared_region(self, page, region_live_server):
        requests = []
        page.on(
            'request',
            lambda request: requests.append(
                (request.method, request.url, request.headers.get('x-hypergen-partial')),
            ),
        )
        load_region_page(page, region_live_server)

        page.locator('#push-two').click()

        expect(page).to_have_url(f'{region_live_server}/regions/two')
        expect(page).to_have_title('Page two | Region tests')
        expect(page.locator('[data-hypergen-region="navigation"] nav')).to_have_attribute(
            'data-active-page',
            'two',
        )
        expect(page.locator('[data-hypergen-region="messages"]')).to_be_empty()
        expect(page.locator('#current-page')).to_have_text('Current page: two')
        assert ('GET', f'{region_live_server}/regions/two', '1') in requests

    def test_back_and_forward_restore_region_state(self, page, region_live_server):
        load_region_page(page, region_live_server)
        page.locator('#push-two').click()
        expect(page.locator('#current-page')).to_have_text('Current page: two')

        page.go_back()
        expect(page.locator('#current-page')).to_have_text('Current page: one')
        expect(page).to_have_title('Page one | Region tests')

        page.go_forward()
        expect(page.locator('#current-page')).to_have_text('Current page: two')
        expect(page).to_have_title('Page two | Region tests')

    def test_replace_and_no_history_modes(self, page, region_live_server):
        load_region_page(page, region_live_server)
        page.locator('#push-two').click()
        expect(page).to_have_url(f'{region_live_server}/regions/two')

        page.locator('#replace-three').click()
        expect(page).to_have_url(f'{region_live_server}/regions/three')
        page.go_back()
        expect(page).to_have_url(f'{region_live_server}/regions/one')

        page.locator('#no-history-three').click()
        expect(page).to_have_url(f'{region_live_server}/regions/one')
        expect(page.locator('#current-page')).to_have_text('Current page: three')

    def test_callbacks_work_in_updated_and_untouched_regions(self, page, region_live_server):
        load_region_page(page, region_live_server)
        page.evaluate(
            """
            window.regionEvents = []
            window.regionTest = {record: value => window.regionEvents.push(value)}
            """,
        )

        page.locator('#push-two').click()
        expect(page.locator('#current-page')).to_have_text('Current page: two')
        page.locator('#updated-callback').click()
        page.locator('#navigation-callback').click()
        page.locator('#untouched-callback').click()

        assert page.evaluate('window.regionEvents') == [
            'updated-two',
            'navigation-two',
            'untouched',
        ]
        assert (
            page.evaluate(
                "'removed-callback__onclick' in "
                'hypergen.clientState.hypergen.eventHandlerCallbacks',
            )
            is False
        )
