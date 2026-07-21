function x_axis_tick_format(d) {
        var formatter = d3.time.format('%x');
            return formatter(new Date(d));
}
function y_axis_tick_format(d) {
        return d3.format(".2f")(d);
}
function mangle_data(response, result_types) {
    var retrace_data = [];
    var releases = ['Ubuntu 22.04',
                    'Ubuntu 24.04',
                    'Ubuntu 26.04',
                    'Ubuntu 26.10'
                   ];

    // If you add or change colors here, also update the colors
    // in api/resources.py and static/js/most_common_problems.js.

    // three colors (amd64, i386, armhf) for each release
    var colors = ['#29b458', '#96daab',
                  '#ff8b00', '#ffa132',
                  '#ffc580',
                  '#7e2f8e',
                  '#228b22',
                  '#0066ff',
                  '#d20700',
                  '#dd4814',
                  '#d9c200',
                  '#00e600',
                  '#05ead3',
                  '#7e2f8e',
                  '#ff0900',
                  '#ffae00',
                  '#ffe81a',
                  '#73e673',
                  '#8edbf4',
                  '#00faed',
                  '#9859a5'
                 ];
    for (var release in releases) {
        for (var result_type in result_types) {
            var data = [];
            for (var key in response.objects) {
                var day = response.objects[key].date;
                day = new Date(day.replace(/^(\d\d\d\d)(\d\d)(\d\d)$/, "$1/$2/$3"));
                var result = response.objects[key].value[releases[release]];
                if (result !== undefined) {
                    result = result[result_types[result_type]];
                    if (result !== undefined) {
                        data.push({ x: day, y: result});
                    }
                }
            }
            retrace_data.push({
                values: data,
                key: releases[release] + ' (' + result_types[result_type] + ')',
                color: colors.shift()
            });
        }
    }
    return retrace_data;
}
function retracers_graph () {
    YUI().use('node', 'io-base', 'json-parse', function (Y) {
        // FIXME: Tastypie suddenly doesn't like 0 as a parameter here.
        var uri = '/api/1.0/retracers-average-processing-time/?limit=365&format=json';
        function complete (id, o, args) {
            var response = Y.JSON.parse(o.response);
            var arches = ['amd64', 'i386', 'armhf', 'arm64'];
            var retrace_data = mangle_data(response, arches);
            nv.addGraph(function () {
                var chart = nv.models.lineWithFocusChart();
                chart.forceY([0]);
                chart.xAxis.tickFormat(x_axis_tick_format);
                chart.x2Axis.tickFormat(x_axis_tick_format);
                chart.yAxis.axisLabel('Average retracing time')
                chart.yAxis.tickFormat(y_axis_tick_format);
                chart.y2Axis.tickFormat(y_axis_tick_format);
                var container = d3.select('#retracers svg').datum(retrace_data);

                container.transition().duration(500).call(chart);
                nv.utils.windowResize(chart.update);
                return chart;
            });
        };
        Y.on('io:complete', complete, Y, {});
        Y.io(uri);
    });
}

function retracers_results_graph () {
    YUI().use('node', 'io-base', 'json-parse', function (Y) {
        // FIXME: Tastypie suddenly doesn't like 0 as a parameter here.
        var uri = '/api/1.0/retracers-results/?limit=365&format=json';
        function complete (id, o, args) {
            var response = Y.JSON.parse(o.response);
            var types = ['success', 'failed'];
            var retrace_data = mangle_data(response, types);
            nv.addGraph(function () {
                var chart = nv.models.lineWithFocusChart();
                chart.forceY([0]);
                chart.xAxis.tickFormat(x_axis_tick_format);
                chart.x2Axis.tickFormat(x_axis_tick_format);
                chart.yAxis.axisLabel('Retracing results')
                chart.yAxis.tickFormat(y_axis_tick_format);
                chart.y2Axis.tickFormat(y_axis_tick_format);
                var container = d3.select('#retracers svg').datum(retrace_data);

                container.transition().duration(500).call(chart);
                nv.utils.windowResize(chart.update);
                return chart;
            });
        };
        Y.on('io:complete', complete, Y, {});
        Y.io(uri);
    });
}

function instances_graph () {
    YUI().use('node', 'io-base', 'json-parse', function (Y) {
        var uri = '/api/1.0/instances-count/?limit=200&format=json';
        function complete (id, o, args) {
            var data = [];
            var response = Y.JSON.parse(o.response);
            for (var result in response.objects) {
                result = response.objects[result];
                var instance_data = [];
                for (var key in result.value) {
                    var x = result.value[key].date;
                    x = new Date(x.replace(/^(\d\d\d\d)(\d\d)(\d\d)$/, "$1/$2/$3"));
                    var y = result.value[key].value;
                    instance_data.push({x: x, y: y})
                }
                data.push({values: instance_data, key: result.release, color: result.color});

            }
            nv.addGraph(function () {
                var chart = nv.models.lineWithFocusChart();
                chart.xAxis.tickFormat(x_axis_tick_format);
                chart.x2Axis.tickFormat(x_axis_tick_format);
                chart.forceY([0]);
                chart.yAxis.axisLabel('Instances')
                var container = d3.select('#retracers svg').datum(data);

                container.transition().duration(500).call(chart);
                nv.utils.windowResize(chart.update);
                return chart;
            });
        };
        Y.on('io:complete', complete, Y, {});
        Y.io(uri);
    });
}

function retracers_queue_length_graph () {
    function hashColor(str) {
        var hash = 0;
        for (var i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        var hue = Math.abs(hash % 60) * 6;
        return 'hsl(' + hue + ', 65%, 55%)';
    }
    YUI().use('node', 'io-base', 'json-parse', function (Y) {
        var uri = '/api/1.0/retracer-queue-length/?hours=336&format=json';
        function complete (id, o, args) {
            var response = Y.JSON.parse(o.response);
            var data = [];
            for (var i in response.objects) {
                var queue = response.objects[i];
                var values = [];
                for (var j in queue.values) {
                    var ts = queue.values[j].timestamp;
                    var year = ts.substring(0, 4);
                    var month = ts.substring(4, 6);
                    var day = ts.substring(6, 8);
                    var hour = ts.substring(8, 10);
                    var minute = ts.substring(10, 12);
                    values.push({
                        x: new Date(year, month - 1, day, hour, minute),
                        y: queue.values[j].value
                    });
                }
                data.push({
                    values: values,
                    key: queue.queue,
                    color: hashColor(queue.queue)
                });
            }
            nv.addGraph(function () {
                var chart = nv.models.lineWithFocusChart();
                chart.xAxis.tickFormat(x_axis_tick_format);
                chart.x2Axis.tickFormat(x_axis_tick_format);
                chart.forceY([0]);
                chart.yAxis.axisLabel('Queue length')
                var container = d3.select('#retracers svg').datum(data);

                container.transition().duration(500).call(chart);
                nv.utils.windowResize(chart.update);
                return chart;
            });
        };
        Y.on('io:complete', complete, Y, {});
        Y.io(uri);
    });
}
