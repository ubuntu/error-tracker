var current_from_value;
var current_to_value;

function most_common_problems_table(loggedin_user) {
YUI().use('node', 'io-queue', 'io-form', 'datatable', 'datatable-sort',
    'datasource-io', 'datasource-jsonschema', 'datatable-datasource',
    'datatable-message', 'datatype', 'event-key', 'event-valuechange',
    'querystring', 'event-outside', 'gallery-datasource-manage-stale',
function(Y) {
    query_string = Y.QueryString.parse (window.location.search.slice(1));
    var selected_release;
    /* The largest instance count in the data. */
    var current_max = 1;
    /* Asynchronously fetched Launchpad data for the table */
    var reports_state_fixed_master = null;
    var occurs_in_latest_version = null;

    var scale = d3.scale.linear()
        .range(["10", "110"]);

    function createBug (e, signature) {
        var newNode = Y.Node.create('<div>Creating</div>');
        function complete (id, o, args) {
            if (o.responseText) {
                var json = JSON.parse(o.responseText);
                if (json.report != null) {
                    newNode.set('innerHTML', '<div><a href="' + json.url + '">'
                                + json.report + '</a></div>');
                    return;
                }
            }
            newNode.set('innerHTML', '<div>Error</div>');
        }
        var token = Y.one('input[name=csrfmiddlewaretoken]').get('value');
        // encode any special characters in the signature
        var sig_enc = encodeURIComponent(signature);
        var cfg = {
            method: 'POST',
            data: '{"signature": "' + sig_enc + '" }',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token
            },
            on: {
                complete: complete
            }
        }
        var request = Y.io("/api/1.0/create-bug-report/?format=json&", cfg);
        e.target.replace(newNode);
    }

    function getPackagesState (packages, release, e) {
        function complete (id, o, args) {
            if (o.responseText) {
                var json = JSON.parse(o.responseText);
                if (json.packages != null) {
                    occurs_in_latest_version = json.packages;
                    table.datasource.onDataReturnInitializeTable(e);
                }
            }
        }
        var data;
        if (release) {
            data = {packages: packages, release: release};
        } else {
            data = {packages: packages};
        }
        var cfg = {
            method: 'POST',
            data: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json'
            },
            on: {
                complete: complete
            }
        }
        var request = Y.io.queue("/api/1.0/package-version-is-most-recent/?format=json", cfg);
    }
    function getPackagesPockets (packages_data, e) {
        function complete (id, o, args) {
            if (o.responseText) {
                var json = JSON.parse(o.responseText);
                if (json.packages_data != null) {
                    package_pocket = json.packages_data;
                    table.datasource.onDataReturnInitializeTable(e);
                }
            }
        }
        var data;
        data = {packages_data: packages_data};
        var cfg = {
            method: 'POST',
            data: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json'
            },
            on: {
                complete: complete
            }
        }
        var request = Y.io.queue("/api/1.0/release-package-version-pockets/?format=json", cfg);
    }
    function getReportsState (reports, release, e) {
        function complete (id, o, args) {
            if (o.responseText) {
                var json = JSON.parse(o.responseText);
                if (json.reports != null) {
                    reports_state_fixed_master = json.reports;
                    table.datasource.onDataReturnInitializeTable(e);
                }
            }
        }
        var data;
        if (release) {
            data = {reports: reports, release: release};
        } else {
            data = {reports: reports};
        }
        var cfg = {
            method: 'POST',
            data: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json'
            },
            on: {
                complete: complete
            }
        }
        var request = Y.io.queue("/api/1.0/reports-state/?format=json", cfg);
    }

    function genericFormatter(o) {
        /* We won't have a valid reports_state_fixed array on the first pass */
        if (!reports_state_fixed_master || !occurs_in_latest_version) {
            o.className = '';
            return o.value;
        }
        /* We won't have any package pocket information on the first pass */
        if (!package_pocket) {
            return o.value;
        }
        var latest = occurs_in_latest_version[o.data['package'] + ' ' + o.data.last_seen];
        if (reports_state_fixed_master[o.data.report] === null) {
            if (o.column._id == "report") {
                o.className += 'private';
            }
            return o.value;
        }
        if (reports_state_fixed_master[o.data.report][0]) {
            /* If the problem has appeared in the most recent published version
             */
            if (latest) {
                /* If the problem is marked as complete in the linked bug */
                o.className += 'regression';
                return o.value;

            } else {
                o.className += 'fixed';
                return o.value;
            }

        } else if (!latest) {
            o.className += 'disappeared';
            return o.value;
        }

    }

    var chartFormatter = function(o) {
        // TODO move this into the CSS by using release classes
        // Meanwhile, if you add or change colors here, also update the colors
        // in api/resources.py and static/js/retracers.js.
        var color = '#aea7a0';
        if (selected_release == 'Ubuntu 12.04') {
            color = '#29b458';
        } else if (selected_release == 'Ubuntu 12.10') {
            color = '#05b8ea';
        } else if (selected_release == 'Ubuntu 13.04') {
            color = '#4f2f8e';
        } else if (selected_release == 'Ubuntu 13.10') {
            color = '#d20700';
        } else if (selected_release == 'Ubuntu 14.04') {
            color = '#ff8b00';
        } else if (selected_release == 'Ubuntu 14.10') {
            color = '#d9c200';
        } else if (selected_release == 'Ubuntu 15.04') {
            color = '#00e600';
        } else if (selected_release == 'Ubuntu 15.10') {
            color = '#05ead3';
        } else if (selected_release == 'Ubuntu 16.04') {
            color = '#7e2f8e';
        } else if (selected_release == 'Ubuntu 16.10') {
            color = '#ff0900';
        } else if (selected_release == 'Ubuntu 17.04') {
            color = '#ffae00';
        } else if (selected_release == 'Ubuntu 17.10') {
            color = '#ffe81a';
        } else if (selected_release == 'Ubuntu 18.04') {
            color = '#228b22';
        } else if (selected_release == 'Ubuntu 18.10') {
            color = '#0066ff';
        } else if (selected_release == 'Ubuntu 19.04') {
            color = '#b353c6';
        } else if (selected_release == 'Ubuntu 19.10') {
            color = '#d20700';
        } else if (selected_release == 'Ubuntu 20.04') {
            color = '#dd4814';
        } else if (selected_release == 'Ubuntu 20.10') {
            color = '#d9c200';
        } else if (selected_release == 'Ubuntu 21.04') {
            color = '#00e600';
        } else if (selected_release == 'Ubuntu 21.10') {
            color = '#05ead3';
        } else if (selected_release == 'Ubuntu 22.04') {
            color = '#7e2f8e';
        } else if (selected_release == 'Ubuntu 22.10') {
            color = '#ff0900';
        } else if (selected_release == 'Ubuntu 23.04') {
            color = '#ffae00';
        } else if (selected_release == 'Ubuntu 23.10') {
            color = '#ffe81a';
        } else if (selected_release == 'Ubuntu 24.04') {
            color = '#00e600';
        } else if (selected_release == 'Ubuntu 24.10') {
            color = '#05b8ea';
        } else if (selected_release == 'Ubuntu 25.04') {
            color = '#7e2f8e';
        } else if (selected_release == 'Ubuntu 25.10') {
            color = '#ff0900';
        } else if (selected_release == 'Ubuntu 26.04') {
            color = '#ffae00';
        }
        o.value = "<div class=\"chart-wrap\"><span class=\"chart-text\">" + o.value + "</span><div class=\"chart\" style=\"width: " + scale(o.value / current_max) + "px; background-color: " + color + "\">&nbsp;</div></div>";
        return o.value;
    }

    var bugFormatter = function(o) {
        var failed = o.data['function'].indexOf('failed:') == 0;
        var unknown = o.data['package'] == 'unknown package';
        if (o.value || !user_is_authenticated || failed) {
            bug_id = o.value;
            /* show master bug if bug is a duplicate */
            state = reports_state_fixed_master[bug_id];
            if (state && state[1]) {
                bug_id = state[1];
            }
            o.value = "<a href=\"https://launchpad.net/bugs/" + bug_id + "\">" + bug_id + "</a>";
            return genericFormatter(o);
        /* don't show the create bug link for an unknown package */
        } else if (!unknown && allow_bug_filing) {
            var guid = Y.guid();
            Y.on('click', createBug, '#' + guid, null, o.data['function']);
            o.value = "<a href=\"javascript:void(0)\" id=\"" + guid + "\">Create</a>";
            return genericFormatter(o);
        /* this stops the last cell from not being grey (regression) if allow_bug_filing is false */
        } else {
            o.value = '';
            return genericFormatter(o);
        }
    }
    var functionFormatter = function(o) {
        var formatted = formatSignature(o.value);
        var web_link = o.data['web_link'];
        o.value = '<div class="outer"><div class="inner">' +
                  '<a href="' + web_link + '">' + formatted +
                  '</a></div></div>';
        return genericFormatter(o);
    }
    /* would be better if we didn't need two PocketFormatter functions,
       but I couldn't sort out which column we were working on with o */
    var firstPocketFormatter = function(o) {
        if (!package_pocket || !o.data['first_seen_release']) {
            return genericFormatter(o);
        }
        if (o.data['first_seen_release']) {
            /* some releases contain Kylin */
            var release = o.data['first_seen_release'].slice(-5);
            if (package_pocket) {
                var pocket = package_pocket[o.data['package'] + ' ' + o.data['first_seen'] + ' ' + o.data['first_seen_release']];
            }
        }
        release = release.replace("Ubuntu ", "");
        pocket = pocket.substr(0,1);
        /* Package version on mouse-over? */
        version = o.data['first_seen']
        if (pocket != '') {
            o.value = "<span title='" + version + "'>" + release + " (" + pocket + ")</span>";
        } else {
            o.value = "<span title='" + version + "'>" + release + "</span>";
        }
        return genericFormatter(o);
    }
    var lastPocketFormatter = function(o) {
        if (!package_pocket || !o.data['last_seen_release']) {
            return genericFormatter(o);
        }
        if (o.data['last_seen_release']) {
            /* some releases contain Kylin */
            var release = o.data['last_seen_release'].slice(-5);
            if (package_pocket) {
                var pocket = package_pocket[o.data['package'] + ' ' + o.data['last_seen'] + ' ' + o.data['last_seen_release']];
            }
        }
        release = release.replace("Ubuntu ", "");
        pocket = pocket.substr(0,1);
        /* Package version on mouse-over? */
        version = o.data['last_seen']
        if (pocket != '') {
            o.value = "<span title='" + version + "'>" + release + " (" + pocket + ")</span>";
        } else {
            o.value = "<span title='" + version + "'>" + release + "</span>";
        }
        return genericFormatter(o);
    }
    var cols = [
        {key: "rank", label: "Rank", sortable:true },
        {key: "count", label: "Occurrences", sortable:true, formatter:chartFormatter, allowHTML: true},
        {key: "package", label: "Binary Package", sortable:true, formatter:genericFormatter, allowHTML: true},
        {key: "first_seen_release", label: "First seen", formatter:firstPocketFormatter, allowHTML: true},
        {key: "last_seen_release", label: "Last seen", formatter:lastPocketFormatter, allowHTML: true},
        {key: "function", label: "Function", formatter:functionFormatter, allowHTML: true},
        {key: "report", label: "Bug report", sortable:true, formatter:bugFormatter, allowHTML: true}
    ];

    var datasource = new Y.DataSource.IO({
        source: "/api/1.0/most-common-problems/?format=json",
        /* FIXME Clearing the current pending request before starting a new one
         * does not work:
         * http://yuilibrary.com/projects/yui3/ticket/2529999 */
        //asyncMode: "cancelStaleRequests"
        plugins : [
          {fn: Y.Plugin.DataSourceManageStale, cfg: {
            ignoreStaleResponses : true,
            cancelStaleRequests : false
          }}
        ]
    });
    datasource.plug(Y.Plugin.DataSourceJSONSchema, {
        schema: {
            resultListLocator: "objects",
            resultFields: [
                {key: 'rank'},
                {key: 'count'},
                {key: 'first_seen'},
                {key: 'last_seen'},
                {key: 'first_seen_release'},
                {key: 'last_seen_release'},
                {key: 'function'},
                {key: 'package'},
                {key: 'report'},
                {key: 'web_link'}
            ]
        }
    });
    table = new Y.DataTable({
        columnset: cols,
          sortBy: { rank: 1 }
    });

    table.plug(Y.Plugin.DataTableDataSource, {
        datasource: datasource
    })

    function loadRequest (period) {
        table.datasource.load({
            request: '&limit=30' + period,
            callback: {
                /* Provide a better message on failure */
                success: function (e) {
                    // Cache for later.
                    var qs = Y.QueryString.parse (e.request.slice(2));
                    selected_release = qs.release;
                    /* We get the data sorted from the API. */
                    if (e.response.results.length > 0) {
                        current_max = e.response.results[0].count;
                    } else {
                        current_max = 1;
                    }

                    reports_state_fixed_master = null;
                    occurs_in_latest_version = null;
                    package_pocket = null;

                    Y.io.queue.stop();
                    /* TODO clear queue and abort current transaction */

                    /* Look up the bug states. */
                    var reports = Array();
                    e.response.results.map(function(elm) {
                        elm.report && reports.push(elm.report);
                    });
                    getReportsState (reports, selected_release, e);

                    /* Look up the package states. */
                    var packages = Array();
                    e.response.results.map( function(elm) {
                        if (elm.last_seen && elm['package']) {
                            packages.push({'package': elm['package'], last_seen: elm.last_seen });
                        }
                    });
                    getPackagesState (packages, selected_release, e);

                    /* Look up the pocket from where the package originates. */
                    var packages_data = Array();
                    e.response.results.map( function(elm) {
                        if (elm.first_seen && elm['package'] && elm['first_seen_release']) {
                            packages_data.push({'package': elm['package'], seen: elm.first_seen,
                                           release: elm['first_seen_release'] });
                        }
                        if (elm.last_seen && elm['package'] && elm['last_seen_release']) {
                            packages_data.push({'package': elm['package'], seen: elm.last_seen,
                                           release: elm['last_seen_release'] });
                        }
                    });
                    getPackagesPockets (packages_data, e);

                    /* We use a queue as running both async tasks
                     * simultaneously seems to break on reading from the socket
                     * on the server side. */
                    Y.io.queue.start();

                    /* Initialize without the color information */
                    table.datasource.onDataReturnInitializeTable(e);
                },
                failure: function (e) {
                    if (e.data.status == 404) {
                        table.showMessage("That user does not exist.");
                    } else {
                        msg = "An error occurred while trying to load the " + 
                              "most common problems."
                        table.showMessage(msg);
                    }
                }
            }
        });
    }

    function interval_changed () {
        var req = '';
        if (Y.one('#release_interval').getStyle('visibility') != 'hidden') {
            Y.one('#release_interval').get("options").each(function () {
                release = this.get('value');
                if (this.get('selected') && release != 'all') {
                    req += '&release=' + release;
                }
            });
        }
        if (Y.one('#rootfs_build').getStyle('display') != 'none') {
            Y.one('#rootfs_build_versions').get("options").each(function () {
                rootfs_build_version = this.get('value');
                if (this.get('selected')) {
                    req += '&rootfs_build_version=' + rootfs_build_version;
                }
            });
        }
        if (Y.one('#channel').getStyle('display') != 'none') {
            Y.one('#channel_versions').get("options").each(function () {
                channel_name = this.get('value');
                if (this.get('selected')) {
                    req += '&channel_name=' + channel_name;
                }
            });
            Y.one('#device_name_versions').get("options").each(function () {
                device_name = this.get('value');
                if (this.get('selected')) {
                    req += '&device_name=' + device_name;
                }
            });
        }
        if (Y.one('#device_image').getStyle('display') != 'none') {
            Y.one('#device_image_versions').get("options").each(function () {
                device_image_version = this.get('value');
                if (this.get('selected')) {
                    req += '&device_image_version=' + device_image_version;
                }
            });
        }
        var specific_package = Y.one('#package').get('value');
        if (specific_package != '') {
            req += '&package=' + specific_package;
        }
        var snap = Y.one('#snap').get('value');
        if (snap == 'True') {
            req += '&snap=True';
        }
        var packageset = Y.one('#packageset').get('value');
        if (packageset != '') {
            req += '&packageset=' + packageset;
        }
        if (Y.one('#subscriber_name').getStyle('visibility') != 'hidden') {
            var user = Y.one('#user').get('value');
            if (user.search(/^https:\/\/launchpad.net\//) != -1) {
                user = user.slice(22);
                req += '&user=' + user;
            } else {
                req += '&user=' + user;
            }
        }
        range_selected = false;
        Y.one('#problem_interval').get("options").each(function () {
            if (this.get('selected')) {
                var period = this.get('value').split(' ');
                period = period[period.length-1];
                if (period == 'range') {
                    Y.one('#date_selection').setStyle('visibility', 'visible');
                    Y.one('#date_selection').setStyle('display', 'inline');
                    range_selected = true;
                    return;
                } else {
                    Y.one('#date_selection').setStyle('visibility', 'hidden');
                    Y.one('#date_selection').setStyle('display', 'none');
                }
                req += '&period=' + period;
            }
        });
        var from_date = Y.one('#from_date').get('value');
        var to_date = Y.one('#to_date').get('value');

        /* Check to see if we have a date range selection. */
        if (from_date && to_date && from_date <= to_date) {
            current_from_value = from_date;
            current_to_value = to_date;
            req += '&from=' + from_date + '&to=' + to_date;
        } else if (range_selected) {
            return;
        }
        if (Y.one('#package_versions').getStyle('visibility') != 'hidden') {
            var package_version = Y.one('#package_versions').get('value');
            if (package_version != 'all' && package_version != 'all installed versions') {
                // encode the package version because it may contain + or ~ or :
                req += '&version=' + encodeURIComponent(package_version);
                Y.one('#package_versions').set('value', package_version);
            }
        }
        Y.one('#package_architecture').get("options").each(function () {
            pkg_arch = this.get('value');
            if (this.get('selected') && pkg_arch != 'every') {
                req += '&pkg_arch=' + pkg_arch;
            }
        });
        if (req) {
            table.showMessage("loadingMessage");
            history.replaceState('', '', req.replace("&", "?"));
            loadRequest(req);
        }
    }

    function display_release_types () {
        Y.one('#release_type').get("options").each(function () {
            if (this.get('selected')) {
                var release_type = this.get('value');
                if (release_type == 'release') {
                    Y.one('#release_interval').setStyle('visibility', 'visible');
                    Y.one('#release_interval').setStyle('display', 'inline');
                    Y.one('#rootfs_build').setStyle('visibility', 'hidden');
                    Y.one('#rootfs_build').setStyle('display', 'none');
                    Y.one('#channel').setStyle('visibility', 'hidden');
                    Y.one('#channel').setStyle('display', 'none');
                    Y.one('#device_name').setStyle('visibility', 'hidden');
                    Y.one('#device_name').setStyle('display', 'none');
                    Y.one('#device_image').setStyle('visibility', 'hidden');
                    Y.one('#device_image').setStyle('display', 'none');
                    interval_changed();
                    return;
                } else if (release_type == 'rootfs build') {
                    Y.one('#release_interval').setStyle('visibility', 'hidden');
                    Y.one('#release_interval').setStyle('display', 'none');
                    Y.one('#rootfs_build').setStyle('visibility', 'visible');
                    Y.one('#rootfs_build').setStyle('display', 'inline');
                    Y.one('#channel').setStyle('visibility', 'hidden');
                    Y.one('#channel').setStyle('display', 'none');
                    Y.one('#device_name').setStyle('visibility', 'hidden');
                    Y.one('#device_name').setStyle('display', 'none');
                    Y.one('#device_image').setStyle('visibility', 'hidden');
                    Y.one('#device_image').setStyle('display', 'none');
                    populate_image_versions('rootfs_build');
                    return;
                } else if (release_type == 'channel') {
                    Y.one('#release_interval').setStyle('visibility', 'hidden');
                    Y.one('#release_interval').setStyle('display', 'none');
                    Y.one('#rootfs_build').setStyle('visibility', 'hidden');
                    Y.one('#rootfs_build').setStyle('display', 'none');
                    Y.one('#channel').setStyle('visibility', 'visible');
                    Y.one('#channel').setStyle('display', 'inline');
                    Y.one('#device_name').setStyle('visibility', 'visible');
                    Y.one('#device_name').setStyle('display', 'inline');
                    Y.one('#device_image').setStyle('visibility', 'hidden');
                    Y.one('#device_image').setStyle('display', 'none');
                    populate_image_versions('channel');
                    populate_image_versions('device_name');
                    return;
                } else if (release_type == 'device image') {
                    Y.one('#release_interval').setStyle('visibility', 'hidden');
                    Y.one('#release_interval').setStyle('display', 'none');
                    Y.one('#rootfs_build').setStyle('visibility', 'hidden');
                    Y.one('#rootfs_build').setStyle('display', 'none');
                    Y.one('#channel').setStyle('visibility', 'hidden');
                    Y.one('#channel').setStyle('display', 'none');
                    Y.one('#device_name').setStyle('visibility', 'hidden');
                    Y.one('#device_name').setStyle('display', 'none');
                    Y.one('#device_image').setStyle('visibility', 'visible');
                    Y.one('#device_image').setStyle('display', 'inline');
                    populate_image_versions('device_image');
                    return;
                }
            }
        });
    }
    function display_pkg_user () {
        var subscriber = '';
        if (query_string.user !== undefined) {
            subscriber = query_string.user;
        } else if (loggedin_user != '' &&
                   query_string['package'] == undefined &&
                   query_string['release'] == undefined) {
            subscriber = loggedin_user;
        }
        Y.one('#package_selection').get("options").each(function () {
            if (this.get('selected')) {
                var pkg = this.get('value');
                if (pkg == 'the package') {
                    Y.one('#package_versions').setStyle('visibility', 'visible');
                    Y.one('#package_versions').setStyle('display', 'inline');
                    Y.one('#package_name').setStyle('visibility', 'visible');
                    Y.one('#package_name').setStyle('display', 'inline');
                    Y.one('#packageset_name').setStyle('visibility', 'hidden');
                    Y.one('#packageset_name').setStyle('display', 'none');
                    Y.one('#packageset').set('value', '');
                    Y.one('#snap').set('value', '');
                    Y.one('#user').set('value', '');
                    Y.one('#subscriber_name').setStyle('visibility', 'hidden');
                    Y.one('#subscriber_name').setStyle('display', 'none');
                    return;
                } else if (pkg == 'the package set') {
                    Y.one('#package_versions').setStyle('visibility', 'hidden');
                    Y.one('#package_versions').setStyle('display', 'none');
                    Y.one('#package_name').setStyle('visibility', 'hidden');
                    Y.one('#package_name').setStyle('display', 'none');
                    Y.one('#package').set('value', '');
                    Y.one('#packageset_name').setStyle('visibility', 'visible');
                    Y.one('#packageset_name').setStyle('display', 'inline');
                    Y.one('#snap').set('value', '');
                    Y.one('#user').set('value', '');
                    Y.one('#subscriber_name').setStyle('visibility', 'hidden');
                    Y.one('#subscriber_name').setStyle('display', 'none');
                    return;
                } else if (pkg == 'packages subscribed to by') {
                    Y.one('#package_versions').setStyle('visibility', 'hidden');
                    Y.one('#package_versions').setStyle('display', 'none');
                    Y.one('#subscriber_name').setStyle('visibility', 'visible');
                    Y.one('#subscriber_name').setStyle('display', 'inline');
                    Y.one('#package').set('value', '');
                    Y.one('#packageset').set('value', '');
                    Y.one('#snap').set('value', '');
                    // by default set the user to the logged in one
                    if (Y.one('#user').get('value') == '') {
                        Y.one('#user').set('value', subscriber);
                    }
                    Y.one('#package_name').setStyle('visibility', 'hidden');
                    Y.one('#package_name').setStyle('display', 'none');
                    Y.one('#packageset_name').setStyle('visibility', 'hidden');
                    Y.one('#packageset_name').setStyle('display', 'none');
                    return;
                // all debian packages is selected
                } else if (pkg == 'all debian packages') {
                    Y.one('#package_versions').setStyle('visibility', 'hidden');
                    Y.one('#package_versions').setStyle('display', 'none');
                    Y.one('#package').set('value', '');
                    Y.one('#packageset').set('value', '');
                    Y.one('#snap').set('value', '');
                    Y.one('#user').set('value', '');
                    Y.one('#package_name').setStyle('visibility', 'hidden');
                    Y.one('#package_name').setStyle('display', 'none');
                    Y.one('#packageset_name').setStyle('visibility', 'hidden');
                    Y.one('#packageset_name').setStyle('display', 'none');
                    Y.one('#subscriber_name').setStyle('visibility', 'hidden');
                    Y.one('#subscriber_name').setStyle('display', 'none');
                    interval_changed();
                    return;
                // other binary packages is selected
                } else {
                    Y.one('#package_versions').setStyle('visibility', 'hidden');
                    Y.one('#package_versions').setStyle('display', 'none');
                    Y.one('#package').set('value', '');
                    Y.one('#snap').set('value', 'True');
                    Y.one('#packageset').set('value', '');
                    Y.one('#user').set('value', '');
                    Y.one('#package_name').setStyle('visibility', 'hidden');
                    Y.one('#package_name').setStyle('display', 'none');
                    Y.one('#packageset_name').setStyle('visibility', 'hidden');
                    Y.one('#packageset_name').setStyle('display', 'none');
                    Y.one('#subscriber_name').setStyle('visibility', 'hidden');
                    Y.one('#subscriber_name').setStyle('display', 'none');
                    interval_changed();
                    return;
                }
            }
        });
    }

    Y.one('#release_type').on('change', display_release_types );
    Y.one('#release_interval').on('change', package_changed );
    Y.one('#rootfs_build_versions').on('change', interval_changed );
    Y.one('#channel_versions').on('change', interval_changed );
    Y.one('#device_name_versions').on('change', interval_changed );
    Y.one('#device_image_versions').on('change', interval_changed );
    Y.one('#problem_interval').on('change', interval_changed );
    Y.one('#package_selection').on('change', display_pkg_user );
    Y.one('#from_date').on('valuechange', interval_changed );
    Y.one('#to_date').on('valuechange', interval_changed );
    Y.one('#package_architecture').on('change', interval_changed );

    function load_package_versions (id, o, args) {
        var result = Y.JSON.parse(o.response);
        var versions = result.objects[0].versions;
        if (args.expected) {
            versions.push(args.expected);
            versions.sort();
        }
        var package_versions = Y.one('#package_versions');
        package_versions.empty(true);
        var text = '<option value="all">all installed versions</option>';
        for (ver in versions) {
            if (args.expected) {
                if (args.expected == versions[ver]) {
                    text += '<option selected value="' + versions[ver] + '">' + versions[ver] + '</option>';
                } else {
                    text += '<option value="' + versions[ver] + '">' + versions[ver] + '</option>';
                }
            } else {
                text += '<option value="' + versions[ver] + '">' + versions[ver] + '</option>';
            }
        }
        package_versions.setHTML(text);
        if (args.expected) {
            package_versions.set('value', args.expected);
        } else {
            package_versions.set('value', 'all');
        }
    }

    function load_image_versions (id, o, args) {
        if (o.status == 401) {
            return;
        }
        var result = Y.JSON.parse(o.response);
        var versions = result.objects[0].versions;
        var rootfs_build_versions = Y.one('#' + args.image_type + '_versions');
        rootfs_build_versions.empty(true);
        if (args.image_type == "device_name") {
            var text = '<option selected value="">all device</option>';
        } else {
            var text = '';
        }
        for (ver in versions) {
            if (args.selected) {
                if (args.selected == versions[ver]) {
                    text += '<option selected value="' + versions[ver] + '">' + versions[ver] + '</option>';
                } else {
                    text += '<option value="' + versions[ver] + '">' + versions[ver] + '</option>';
                }
            } else {
                text += '<option value="' + versions[ver] + '">' + versions[ver] + '</option>';
            }
        }
        text += '</select>';
        rootfs_build_versions.setHTML(text);
        if (args.selected) {
            rootfs_build_versions.set('value', args.selected);
        } else {
            /* select the all device option, which actually sends None to the api */
            if (args.image_type == "device_name") {
                rootfs_build_versions.set('value', '');
            /* select a channel that will have data */
            } else if (args.image_type == "channel") {
                rootfs_build_versions.set('value', 'ubuntu-touch/devel-proposed');
            }
            /* this selects the last item in the option list */
            rootfs_build_versions.set('value', 'none');
        }
        interval_changed();
    }

    function package_changed (update, expected_version) {
        p = Y.one('#package').get('value');
        uri = '/api/1.0/binary-package-versions/?format=json&binary_package=' + p;
        if (Y.one('#release_interval').getStyle('visibility') != 'hidden') {
            Y.one('#release_interval').get("options").each(function () {
                release = this.get('value');
                if (this.get('selected') && release != 'all') {
                    uri += '&release=' + release;
                }
            });
        }
        var cfg = {
            arguments: {expected: expected_version},
            on: {complete: load_package_versions}
        }
        if (p) {
            Y.io(uri, cfg);
        }
        if (update) {
            interval_changed();
        }
    }
    // remove update option
    function populate_image_versions (image_type, selected_version) {
        release_type = Y.one('#release_type').get('value');
        uri = '/api/1.0/system-image-versions/?format=json&image_type=' + image_type;
        var cfg = {
            arguments: {selected: selected_version, image_type: image_type},
            on: {complete: load_image_versions}
        }
        Y.io(uri, cfg);
    }

    Y.one('#package').on('key', package_changed, 'enter');
    Y.one('#packageset').on('key', interval_changed, 'enter');
    Y.one('#package_versions').on('change', interval_changed);
    Y.one('#user').on('key', interval_changed, 'enter');

    function set_defaults () {
        var update = false;
        var expected_version = '';

        if (query_string.release !== undefined) {
            Y.one('#release_interval').setStyle('visibility', 'visible');
            Y.one('#release_interval').setStyle('display', 'inline');
            Y.one('#rootfs_build').setStyle('visibility', 'hidden');
            Y.one('#rootfs_build').setStyle('display', 'none');
            Y.one('#channel').setStyle('visibility', 'hidden');
            Y.one('#channel').setStyle('display', 'none');
            Y.one('#device_name').setStyle('visibility', 'hidden');
            Y.one('#device_name').setStyle('display', 'none');
            Y.one('#device_image').setStyle('visibility', 'hidden');
            Y.one('#device_image').setStyle('display', 'none');
            Y.one('#release_interval').get("options").each(function () {
                if (this.get('value') == query_string.release) {
                    update = true;
                    this.set('selected', true);
                }
            });
            Y.one('#release_type').get("options").each(function () {
                if (this.get('value') == 'the release') {
                    update = true;
                    this.set('selected', true);
                }
            });
        }
        if (query_string.rootfs_build_version !== undefined) {
            Y.one('#release_type').get("options").each(function () {
                if (this.get('value') == 'rootfs build') {
                    update = true;
                    this.set('selected', true);
                }
            });
            Y.one('#release_interval').setStyle('visibility', 'hidden');
            Y.one('#release_interval').setStyle('display', 'none');
            Y.one('#rootfs_build').setStyle('visibility', 'visible');
            Y.one('#rootfs_build').setStyle('display', 'inline');
            Y.one('#channel').setStyle('visibility', 'hidden');
            Y.one('#channel').setStyle('display', 'none');
            Y.one('#device_name').setStyle('visibility', 'hidden');
            Y.one('#device_name').setStyle('display', 'none');
            Y.one('#device_image').setStyle('visibility', 'hidden');
            Y.one('#device_image').setStyle('display', 'none');
            populate_image_versions('rootfs_build', query_string.rootfs_build_version);
            Y.one('#rootfs_build_versions').get("options").each(function () {
                if (this.get('value') == query_string.rootfs_build_version) {
                    update = true;
                    this.set('selected', true);
                }
            });
        }
        if (query_string.channel_name !== undefined) {
            Y.one('#release_type').get("options").each(function () {
                if (this.get('value') == 'channel') {
                    update = true;
                    this.set('selected', true);
                }
            });
            Y.one('#release_interval').setStyle('visibility', 'hidden');
            Y.one('#release_interval').setStyle('display', 'none');
            Y.one('#rootfs_build').setStyle('visibility', 'hidden');
            Y.one('#rootfs_build').setStyle('display', 'none');
            Y.one('#channel').setStyle('visibility', 'visible');
            Y.one('#channel').setStyle('display', 'inline');
            Y.one('#device_name').setStyle('visibility', 'visible');
            Y.one('#device_name').setStyle('display', 'inline');
            Y.one('#device_image').setStyle('visibility', 'hidden');
            Y.one('#device_image').setStyle('display', 'none');
            populate_image_versions('channel', query_string.channel_name);
            Y.one('#channel_versions').get("options").each(function () {
                if (this.get('value') == query_string.channel_name) {
                    update = true;
                    this.set('selected', true);
                }
            });
            if (query_string.device_name !== undefined) {
                populate_image_versions('device_name', query_string.device_name);
                Y.one('#device_name_versions').get("options").each(function () {
                    if (this.get('value') == query_string.device_name) {
                        update = true;
                        this.set('selected', true);
                    }
                });
            }
        }
        if (query_string.device_image_version !== undefined) {
            Y.one('#release_type').get("options").each(function () {
                if (this.get('value') == 'device image') {
                    update = true;
                    this.set('selected', true);
                }
            });
            Y.one('#release_interval').setStyle('visibility', 'hidden');
            Y.one('#release_interval').setStyle('display', 'none');
            Y.one('#rootfs_build').setStyle('visibility', 'hidden');
            Y.one('#rootfs_build').setStyle('display', 'none');
            Y.one('#channel').setStyle('visibility', 'hidden');
            Y.one('#channel').setStyle('display', 'none');
            Y.one('#device_name').setStyle('visibility', 'hidden');
            Y.one('#device_name').setStyle('display', 'none');
            Y.one('#device_image').setStyle('visibility', 'visible');
            Y.one('#device_image').setStyle('display', 'inline');
            populate_image_versions('device_image', query_string.device_image_version);
            Y.one('#device_image_versions').get("options").each(function () {
                if (this.get('value') == query_string.device_image_version) {
                    update = true;
                    this.set('selected', true);
                }
            });
        }
        if (query_string.version !== undefined) {
            update = true;
            var package_versions = Y.one('#package_versions');
            expected_version = query_string.version;
            if (expected_version !== undefined) {
                expected_version = expected_version.toString();
            }
            text = '<option selected>' + expected_version + '</option>';
            package_versions.setHTML(text);
        }
        if (query_string['package'] !== undefined) {
            update = true;
            Y.one('#package_selection').get("options").each(function() {
                if (this.get('value') == 'the package') {
                    this.set('selected', true);
                }
            });
            Y.one('#package_name').setStyle('visibility', 'visible');
            Y.one('#package_name').setStyle('display', 'inline');
            Y.one('#package').set('value', query_string['package']);
            Y.one('#package_versions').setStyle('visibility', 'visible');
            Y.one('#package_versions').setStyle('display', 'inline');
            package_changed(false, expected_version);
        }
        if (query_string['packageset'] !== undefined) {
            update = true;
            Y.one('#package_selection').get("options").each(function() {
                if (this.get('value') == 'the package set') {
                    this.set('selected', true);
                }
            });
            Y.one('#packageset_name').setStyle('visibility', 'visible');
            Y.one('#packageset_name').setStyle('display', 'inline');
            Y.one('#packageset').set('value', query_string['packageset']);
        }
        if (query_string['snap'] !== undefined) {
            update = true;
            Y.one('#package_selection').get("options").each(function() {
                if (this.get('value') == 'other binary packages') {
                    this.set('selected', true);
                }
            });
            Y.one('#snap').set('value', 'True');
        }
        var subscriber;
        if (query_string.user !== undefined) {
            subscriber = query_string.user;
        }
        if (subscriber !== undefined) {
            update = true;
            Y.one('#package_selection').get("options").each(function() {
                if (this.get('value') == 'packages subscribed to by') {
                    this.set('selected', true);
                }
            });
            Y.one('#subscriber_name').setStyle('visibility', 'visible');
            Y.one('#subscriber_name').setStyle('display', 'inline');
            Y.one('#user').set('value', subscriber);
        }
        if (query_string.period !== undefined) {
            update = true;
            Y.one('#problem_interval').get("options").each(function() {
                var period = this.get('value').split(' ');
                period = period[period.length-1];
                if (period == query_string.period) {
                    this.set('selected', true);
                }
            });
        }
        if (query_string.pkg_arch !== undefined) {
            Y.one('#package_architecture').get("options").each(function () {
                if (this.get('value') == query_string.pkg_arch) {
                    update = true;
                    this.set('selected', true);
                }
            });
        }

        var from = query_string.from;
        if (from !== undefined) {
            from = from.toString();
        }
        var to = query_string.to;
        if (to !== undefined) {
            to = to.toString();
        }
        var day_from = false;

        if (to && from > to) {
            /* Malformatted query. Shut it down. */
            console.log('malformed request.');
            return update;
        }
        if (from !== undefined) {
            update = true;
            var valid_options = ['day', 'month', 'year'];
            day_from = (from.length == 10 && from.match(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/));
            var endswith_from = new RegExp(from + '$');
            if (day_from || valid_options.indexOf(from) != -1) {
                Y.one('#problem_interval').get("options").each(function () {
                    if (day_from) {
                        if (this.get('value') == 'the date range') {
                            this.set('selected', true);
                            Y.one('#date_selection').setStyle('visibility', 'visible');
                            Y.one('#from_date').set('value', day_from);
                            Y.one('#to_date').set('value', day_from);
                        }
                    } else {
                        if (endswith_from.test(this.get('value'))) {
                            this.set('selected', true);
                        }
                    }
                });
            }
            if (day_from && to !== undefined) {
                day_to = (to.length == 10 && to.match(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/));
                update = true;
                Y.one('#to_date').set('value', day_to);
            }
        }
        return update;
    }

    table.render("#problems").showMessage("loadingMessage");

    if (set_defaults()) {
        interval_changed();
    } else {
        /* We haven't received a request to load a custom view, so just load
         * the default */
        loadRequest('');
    }

});
}
