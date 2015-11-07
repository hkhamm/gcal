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


$('button[id="cal-btn"]').click(function() {
  var calId = $(this).data('cal_id');
  console.log(calId);
});