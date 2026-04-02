/* Milestone data:
 * - release dates for all releases that submitted error reports
 * - beta dates for the development release
 */
var milestones = [
    /* Precise */
    {date: "April 26, 2012", milestone: "12.04"},
    {date: "August 23, 2012", milestone: "12.04.1"},
    {date: "February 14, 2013", milestone: "12.04.2"},
    {date: "August 22, 2013", milestone: "12.04.3"},
    {date: "February 6, 2014", milestone: "12.04.4"},
    {date: "August 7, 2014", milestone: "12.04.5"},
    /* Quantal */
    {date: "October 18, 2012", milestone: "12.10"},
    /* Raring */
    {date: "April 25, 2013", milestone: "13.04"},
    /* Saucy */
    {date: "October 17, 2013", milestone: "13.10"},
    /* Trusty */
    {date: "April 17, 2014", milestone: "14.04"},
    {date: "July 24, 2014", milestone: "14.04.1"},
    {date: "February 19, 2015", milestone: "14.04.2"},
    {date: "August 6, 2015", milestone: "14.04.3"},
    {date: "February 18, 2016", milestone: "14.04.4"},
    {date: "August 4, 2016", milestone: "14.04.5"},
    /* Utopic */
    {date: "October 23, 2014", milestone: "14.10"},
    /* Vivid */
    {date: "April 23, 2015", milestone: "15.04"},
    /* Wily */
    {date: "October 22, 2015", milestone: "15.10"},
    /* Xenial */
    {date: "April 21, 2016", milestone: "16.04"},
    {date: "July 21, 2016", milestone: "16.04.1"},
    {date: "Feburary 16, 2017", milestone: "16.04.2"},
    {date: "August 3, 2017", milestone: "16.04.3"},
    {date: "March 1, 2018", milestone: "16.04.4"},
    {date: "August 2, 2018", milestone: "16.04.5"},
    /* Yakkety */
    {date: "October 13, 2016", milestone: "16.10"},
    /* Zesty */
    {date: "April 13, 2017", milestone: "17.04"},
    /* Artful */
    {date: "October 19, 2017", milestone: "17.10"},
    /* Bionic */
    {date: "April 26, 2018", milestone: "18.04"},
    {date: "July 26, 2018", milestone: "18.04.1"},
    {date: "February 14, 2018", milestone: "18.04.2"},
    {date: "August 1, 2019", milestone: "18.04.3"},
    {date: "Febuary 6, 2020", milestone: "18.04.4"},
    /* Cosmic */
    {date: "October 18, 2018", milestone: "18.10"},
    /* Disco */
    {date: "April 18, 2019", milestone: "19.04"},
    /* Eoan */
    {date: "October 17, 2019", milestone: "19.10"},
    /* Focal */
    {date: "April 23, 2020", milestone: "20.04"},
    {date: "July 23, 2020", milestone: "20.04.1"},
    {date: "February 4, 2021", milestone: "20.04.2"},
    {date: "August 19, 2021", milestone: "20.04.3"},
    {date: "February 10, 2022", milestone: "20.04.4"},
    /* Groovy */
    {date: "October 22, 2020", milestone: "20.10"},
    /* Hirsute */
    {date: "April 22, 2021", milestone: "21.04"},
    /* Impish */
    {date: "October 14, 2021", milestone: "21.10"},
    /* Jammy */
    {date: "April 21, 2022", milestone: "22.04"},
    {date: "August 4, 2022", milestone: "22.04.1"},
    {date: "February 9, 2023", milestone: "22.04.2"},
    {date: "August 10, 2023", milestone: "22.04.3"},
    /* Kinetic */
    {date: "October 20, 2022", milestone: "22.10"},
    /* Lunar */
    {date: "April 20, 2023", milestone: "23.04"},
    /* Mantic */
    {date: "October 12, 2023", milestone: "23.10"},
    /* Noble */
    {date: "April 25, 2024", milestone: "24.04"},
    /* Oracular */
    {date: "October 10, 2024", milestone: "24.10"},
    /* Plucky */
    {date: "April 17, 2025", milestone: "25.04"},
    /* Questing */
    {date: "October 9, 2025", milestone: "25.10"},
    /* Resolute */
    {date: "March 26, 2026", milestone: "26.04 Beta"},
    {date: "April 23, 2026", milestone: "26.04"}
];

/* Set up milestone dates to be processed into ticks and milestone names for
 * quick lookup */
var ticks = [];
var milestone_map = {};
for (var m in milestones) {
    var d = new Date(milestones[m].date);
    ticks.push(d);
    milestone_map[d.valueOf()] = milestones[m].milestone;
}

function y_axis_tick_format(d) {
    return d3.format(".2f")(d);
}

/* Changing z-order easily, to move the x-axis milestone names above the grey
 * y-axis stripes:
 * https://groups.google.com/forum/#!msg/d3-js/eUEJWSSWDRY/EMmufH2KP8MJ */
d3.selection.prototype.moveToFront = function() { 
	return this.each(function() { 
		this.parentNode.appendChild(this); 
	}); 
};

external_legend_called = false;
function mean_time_between_failures_request(url, external_legend, constrain) {
    if (typeof(external_legend) == 'undefined') external_legend = false;
    if (typeof(constrain) == 'undefined') constrain = false;

    d3.json(url, function(data) {
        nv.addGraph(function() {

            /* Chart */
            var chart = nv.models.lineChart();
            chart.tooltipContent(function(key, x, y, e, graph) {
                x = chart.lines.x()(e.point, e.pointIndex);
                x = d3.time.format('%a, %b %e, \'%y')(x);
                return '<h3>' + y + '</h3>' + '<p>' + key + '</p><p>' + x + '</p>';
            });
            chart.clipEdge(true);
            chart.margin({top: 10, right: 5, bottom: 40, left: 30});
            chart.xAxis.showMaxMin(false);
            chart.xAxis.tickValues(ticks);
            chart.xAxis.tickFormat(d3.time.format('%b %e'));
            chart.yAxis.tickFormat(y_axis_tick_format);
            chart.forceY([0]); // including zero means starting at zero
            chart.x(function(d) { return new Date(d.x); })
                .y(function(d) { return d.y; })
                .xScale(d3.time.scale());

            /* Legend */
            if (external_legend) {
                chart.showLegend(false);
                if (!external_legend_called) {
                    /* Only draw the legend once and do not wire up its events,
                     * so we always show the legend items for all lines,
                     * regardless of which ones are showing, and so that we
                     * only have one control for manipulating which releases
                     * are shown: the "show error reports from" box. */
                    external_legend_called = true;
                    var legend = errors_legend();
                    var legend_container = d3.select('#legend svg')
                        .append('g')
                        /* Don't class this as 'nvd3' so the circles do not
                         * appear clickable. */
                        .attr('class', 'external-legend')
                        .datum(data.objects);
                    legend_container.call(legend);
                }
            } else {
                chart.showLegend(true);
            }

            /* Make sure release day is always visible */
            var releaseDay = ticks[ticks.length-1].valueOf();
            var oneDay = 86400000;
            for (obj in data.objects) {
                var vals = data.objects[obj].values;
                if (vals.length > 0 && vals[vals.length - 1].x < releaseDay) {
                    /* If the graph doesn't include the release day, expand the
                     * range to show it. Use three days past so that the label
                     * fits. */
                    chart.forceX([vals[0].x, releaseDay + oneDay * 3]);
                }
            }
            if (constrain) {
                /* Restrict the y-axis to 0.40, cropping out the massive spikes
                 * in 13.04 which made the rest of the data hard to read. */
                chart.yDomain([0, 0.4]);
            }

            /* Fill the chart with data and show it */
            var container = d3.select('#mean svg').datum(data.objects);
            container.transition().duration(500).call(chart);

            /* If we don't have any data */
            if (vals.length <= 0) {
                return chart;
            }

            /* Create light grey pinstripes along the y-axis */
            container.selectAll('.pinstripe').remove();
            var w = chart.lines.width();
            var num_ticks = container.select('.nv-y.nv-axis > g > g')
                            .selectAll('g')[0].length;
            var height = chart.yAxis.range()[0] / num_ticks;
            container.select('.nv-y.nv-axis > g > g').selectAll('g')
                .filter(function (d,i) {
                    return i % 2 == 0 && i != 0;
                })
                .append('rect')
                    .attr('class', 'pinstripe')
                    .attr('fill', 'lightgrey')
                    .attr('opacity', 0.5)
                    .attr('height', height)
                    .attr('width', w);

            function draw_milestones() {
                var xTicks = d3.select('.nv-x.nv-axis > g > g').selectAll('g');
                var chartTop = chart.yAxis.scale().range()[0];
                xTicks.each(function (d, i) {
                    var g = d3.select(this)
                        .append('g');

                    /* Milestone name */
                    g.append('text')
                        .text(milestone_map[d.valueOf()])
                        .attr('text-anchor', 'end')
                        .attr('transform',
                              'translate(-2,-' + chartTop + ')rotate(-90)');

                    /* Milestone year */
                    g.append('text')
                            .text(d3.time.format('%Y')(d))
                            .attr('text-anchor', 'middle')
                            .attr('transform', 'translate(0,29)');
                });
            }
            draw_milestones();

			container.select('g.nv-x').moveToFront();
            function resize () {
                chart.update();
                draw_milestones();
            }
            nv.utils.windowResize(resize);
            return chart;
        });
    });
}

function mean_time_between_failures_graph(means) {
    YUI().use('node', 'event-key', 'event-valuechange', 'event-outside', function(Y) {
        function mean_time_between_failures_changed() {
            var selected_release;
            var selected_package;
            var selected_version;
            Y.one('#release_interval').get("options").each(function () {
                release = this.get('value');
                if (this.get('selected') && release != 'all') {
                    selected_release = release;
                }
            });
            selected_package = Y.one('#package').get('value');
            selected_version = Y.one('#package_versions').get('value');

            var req = '';
            var constrain = true;
            if (selected_release) {
                if (selected_release != 'all') {
                    constrain = false;
                }
                req += '&release=' + selected_release;
            }
            if (selected_package) {
                req += '&package=' + selected_package;
            }
            if (selected_version && selected_version != 'all installed versions') {
                req += '&version=' + selected_version;
            }
            req = '/api/1.0/average-crashes/?limit=0' + req;
            mean_time_between_failures_request(req, true, constrain);
        }
        Y.one('#release_interval').on('change', mean_time_between_failures_changed);
        Y.one('#package').on('key', mean_time_between_failures_changed, 'enter');
        Y.one('#package_versions').on('change', mean_time_between_failures_changed);

        mean_time_between_failures_request('/api/1.0/average-crashes/?limit=0', true, true);
    });
}
