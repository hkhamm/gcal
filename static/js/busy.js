/**
 * Bind together javascript libraries used in this application.
 * Compile these with 'browserify' to create a combined, 'minified' 
 * version.  (See Makefile)
 */
"use strict";
var moment = require('moment');
var daterangepicker = require('bootstrap-daterangepicker');


/* Export to global environment */ 
window.moment = moment;
window.daterangepicker = daterangepicker;


$(function() {
  $('input[name="daterange"]').daterangepicker({
    ranges: {
      'Today': [moment(), moment()],
      'Tomorrow': [moment().add(1, 'days'), moment().add(1, 'days')],
      'This week': [moment(), moment().endOf('week')],
      'Next week': [moment().add(7, 'days').startOf('week'),
                    moment().add (7, 'days').endOf('week')],
      'This month': [moment(), moment().endOf('month')],
      'Within two weeks': [moment(), moment().add(15, 'days')]
    }
  });
});
