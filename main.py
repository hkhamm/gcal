import flask
from flask import render_template
from flask import request
from flask import url_for
import json
import logging
import uuid

# Date handling
import arrow  # Replacement for datetime, based on moment.js
import datetime  # But we still need time
from dateutil import tz  # For interpreting local times

# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2  # used in oauth2 flow

# Google API for services
from apiclient import discovery

import CONFIG

# Globals
app = flask.Flask(__name__)
app.secret_key = str(uuid.uuid4())
app.debug = CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = CONFIG.GOOGLE_LICENSE_KEY  # You'll need this
APPLICATION_NAME = 'auth0-server'
START_TIME = 9
END_TIME = 17


# Pages (routed from URLs)

@app.route("/")
@app.route("/index")
def index():
    app.logger.debug("Entering index")
    if 'begin_date' not in flask.session:
        init_session_values()
    return render_template('index.html')


@app.route("/choose")
def choose():
    """
    Renders the index.html page after a choose request.
    """
    # We'll need authorization to list calendars
    # I wanted to put what follows into a function, but had
    # to pull it back here because the redirect has to be a
    # 'return'
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()

    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.session['calendars'] = list_calendars(gcal_service)

    return render_template('index.html')


@app.route("/get-times")
def get_times():
    """
    Renders the index.html page after a get-times request.
    """
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()

    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.session['busy_times'] = list_times(gcal_service)
    # flask.session['busy_times'], flask.session['free_times'] = list_times(
    #     gcal_service)

    return render_template('index.html')


#  Google calendar authorization:
#      Returns us to the main /choose screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST:
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /choose, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh service object from our credentials, which are
#  serializable.
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead.

def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value.
    :return: a Google OAuth2 credentials object
    """
    if 'credentials' not in flask.session:
        return None

    credentials = client.OAuth2Credentials.from_json(
        flask.session['credentials'])

    if credentials.invalid or credentials.access_token_expired:
        return None

    return credentials


def get_gcal_service(credentials):
    """
    We need a Google calendar 'service' object to obtain
    list of calendars, times, etc.  This requires
    authorization. If authorization is already in effect,
    we'll just return with the authorization. Otherwise,
    control flow will be interrupted by authorization, and we'll
    end up redirected back to /choose *without a service object*.
    Then the second call will succeed without additional authorization.
    :param credentials: a Google OAuth2 credentials object
    """
    app.logger.debug("Entering get_gcal_service")
    http_auth = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http_auth)
    app.logger.debug("Returning service")

    return service


@app.route('/oauth2callback')
def oauth2callback():
    """
    The 'flow' has this one place to call back to.  We'll enter here
    more than once as steps in the flow are completed, and need to keep
    track of how far we've gotten. The first time we'll do the first
    step, the second time we'll skip the first step and do the second,
    and so on.
    """
    app.logger.debug("Entering oauth2callback")
    flow = client.flow_from_clientsecrets(
        CLIENT_SECRET_FILE,
        scope=SCOPES,
        redirect_uri=flask.url_for('oauth2callback', _external=True))
    # Note we are *not* redirecting above.  We are noting *where*
    # we will redirect to, which is this function.

    # The *second* time we enter here, it's a callback
    # with 'code' set in the URL parameter.  If we don't
    # see that, it must be the first time through, so we
    # need to do step 1.
    app.logger.debug("Got flow")
    if 'code' not in flask.request.args:
        app.logger.debug("Code not in flask.request.args")
        auth_uri = flow.step1_get_authorize_url()
        return flask.redirect(auth_uri)
        # This will redirect back here, but the second time through
        # we'll have the 'code' parameter set
    else:
        # It's the second time through ... we can tell because
        # we got the 'code' argument in the URL.
        app.logger.debug("Code was in flask.request.args")
        auth_code = flask.request.args.get('code')
        credentials = flow.step2_exchange(auth_code)
        flask.session['credentials'] = credentials.to_json()
        # Now I can build the service and execute the query,
        # but for the moment I'll just log it and go back to
        # the main screen
        app.logger.debug("Got credentials")

        return flask.redirect(flask.url_for('choose'))


#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use.

@app.route('/set-range', methods=['POST'])
def set_range():
    """
    User chose a date range with the bootstrap daterange widget.
    :return: redirects to the choose page
    """
    app.logger.debug("Entering setrange")
    # flask.flash("Setrange gave us '{}'".format(request.form.get('daterange')))

    daterange = request.form.get('daterange')
    flask.session['daterange'] = daterange

    daterange_parts = daterange.split()
    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])

    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
        daterange_parts[0], daterange_parts[1],
        flask.session['begin_date'], flask.session['end_date']))

    return flask.redirect(flask.url_for("choose"))


@app.route('/set-checked-calendars', methods=['POST'])
def set_checked_calendars():
    """
    User chose one or more calendars from the list.
    :return: redirects to the get-times page
    """
    app.logger.debug("Entering get_times")
    calendars = request.form.getlist('calendar')

    flask.session['checked_calendars'] = calendars

    return flask.redirect(flask.url_for("get_times"))


@app.route('/clear-session', methods=['POST'])
def clear_session():
    flask.session.clear()
    return flask.redirect(flask.url_for('index'))


#  Initialize session variables

def init_session_values():
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main.
    """
    # Default date span = tomorrow to 1 week from now
    now = arrow.now('local')
    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)

    flask.session["begin_date"] = tomorrow.floor('day').isoformat()
    flask.session["end_date"] = nextweek.ceil('day').isoformat()
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))

    # Default time span each day, 9 to 5
    flask.session["begin_time"] = interpret_time("9am")
    flask.session["end_time"] = interpret_time("5pm")


def interpret_time(text):
    """
    Read time in a human-compatible format and
    interpret as ISO format with local timezone.
    May throw exception if time can't be interpreted. In that
    case it will also flash a message explaining accepted formats.
    :param text: a human-compatible time
    :return: an arrow date time object
    """
    app.logger.debug("Decoding time '{}'".format(text))
    time_formats = ["ha", "h:mma", "h:mm a", "H:mm"]

    try:
        as_arrow = arrow.get(text, time_formats).replace(tzinfo=tz.tzlocal())
        app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
                    .format(text))
        raise

    return as_arrow.isoformat()


def interpret_date(text):
    """
    Convert text of date to ISO format used internally,
    with the local time zone.
    :param text: an ISO date
    :return: an arrow date time object
    """
    try:
        as_arrow = arrow.get(text, "MM/DD/YYYY").replace(
            tzinfo=tz.tzlocal())
    except:
        flask.flash("Date '{}' didn't fit expected format MM/DD/YYYY")
        raise

    return as_arrow.isoformat()


def next_day(iso_text):
    """
    ISO date + 1 day (used in query to Google calendar)
    :param iso_text: an ISO date
    :return: an arrow date time object
    """
    as_arrow = arrow.get(iso_text)

    return as_arrow.replace(days=+1).isoformat()


#  Functions (NOT pages) that return some information
def is_available(event):
    """
    Checks if the event has the transparency attribute.
    :param event: is the event to check.
    :return: True if it is transparent and False if not
    """
    try:
        transparency = event['transparency']
        available = True
    except:
        available = False

    return available


def get_start_end_datetime(event):
    """
    Gets the event's start and end as arrow objects.
    :param event: is the event to check.
    :return: a 2-tuple of the events start and end as an arrow objects.
    """
    is_all_day = False

    try:
        event_start = arrow.get(event['start']['dateTime'])
        event_end = arrow.get(event['end']['dateTime'])
    except:
        event_start = arrow.get(event['start']['date'])
        event_end = arrow.get(event['end']['date'])
        is_all_day = True

    return event_start, event_end, is_all_day


def get_busy_times(service):
    """
    Gets a list of busy times calculated from the user selected calendar's
    events.
    :param service: is the Google service from where the calendar is retrieved.
    :return: a list of busy times in ascending order.
    """
    app.logger.debug('Entering get_busy_times')
    begin_date = arrow.get(flask.session["begin_date"]).replace(hours=+9)
    end_date = arrow.get(flask.session['end_date']).replace(hours=+17)
    busy_dict = {}
    busy = []

    # TODO refactor because its too complicated

    for cal_id in flask.session['checked_calendars']:
        events = service.events().list(calendarId=cal_id).execute()
        for event in events['items']:
            available = is_available(event)
            event_start, event_end, is_all_day = get_start_end_datetime(event)
            day_start = event_start.replace(hour=START_TIME, minute=0)
            day_end = event_end.replace(hour=END_TIME, minute=0)

            # Catches events start after begin time or end before end time
            if ((event_start >= begin_date or event_end <= end_date) and
                    not available and not is_all_day and
                    event_start < day_end and event_end > day_start):
                if event_start < day_start:
                    event['start']['dateTime'] = day_start.isoformat()
                if event_end > day_end:
                    event['end']['dateTime'] = day_end.isoformat()

                busy_dict[event_start.isoformat()] = event

            # Catches all day events between beginning and ending times
            if (event_start >= begin_date and event_end <= end_date and
                    not available and is_all_day and
                    event_start < day_end and event_end > day_start):
                tmp = arrow.get(event['start']['date'])
                tmp = tmp.replace(hour=START_TIME, minute=0).isoformat()
                event['start']['dateTime'] = tmp
                tmp = arrow.get(event['end']['date'])
                tmp = tmp.replace(days=-1, hour=END_TIME, minute=0).isoformat()
                event['end']['dateTime'] = tmp

                busy_dict[event_start.isoformat()] = event

            # Catches events that start before beginning datetime and end
            # before or after the ending datetime
            if (event_start < begin_date < event_end and
                    not available):
                try:
                    start_tmp = arrow.get(event['start']['dateTime'])
                    end_tmp = arrow.get(event['end']['dateTime'])
                except:
                    start_tmp = arrow.get(event['start']['date'])
                    end_tmp = arrow.get(event['end']['date'])

                start_tmp = start_tmp.replace(hour=START_TIME,
                                              minute=0).isoformat()
                end_tmp = end_tmp.isoformat()
                event['start']['dateTime'] = start_tmp
                event['end']['dateTime'] = end_tmp

                busy_dict[event_start.isoformat()] = event

            # Catches all day events events that start before beginning datetime
            # and end before or after the ending datetime
            if (event_start < begin_date < event_end and
                    not available and is_all_day):
                try:
                    start_tmp = arrow.get(event['start']['dateTime'])
                    end_tmp = arrow.get(event['end']['dateTime'])
                except:
                    start_tmp = arrow.get(event['start']['date'])
                    end_tmp = arrow.get(event['end']['date'])

                start_tmp = start_tmp.replace(hour=START_TIME,
                                              minute=0,
                                              tzinfo=tz.tzlocal()).isoformat()
                end_tmp = end_tmp.replace(days=-1, hour=END_TIME,
                                          minute=0,
                                          tzinfo=tz.tzlocal()).isoformat()
                event['start']['dateTime'] = start_tmp
                event['end']['dateTime'] = end_tmp

                busy_dict[event_start.isoformat()] = event

    # check for all day events, remove other events that overlap with it
    remove_list = []
    for i in sorted(busy_dict):
        event = busy_dict[i]

        # if event is all day
        if 'date' in event['start']:
            this_day = arrow.get(event['start']['dateTime']).format('dddd')
            this_day_end = arrow.get(event['end']['dateTime'])

            for j in sorted(busy_dict):
                other_event = busy_dict[j]

                if event != other_event:
                    other_day = arrow.get(
                        other_event['start']['dateTime']).format('dddd')

                    if this_day == other_day:
                        remove_list.append(other_event)

                    other_day_end = arrow.get(other_event['end']['dateTime'])

                    if this_day_end == other_day_end:
                        remove_list.append(other_event)

        if event not in remove_list:
            busy.append(busy_dict[i])

    return busy


def get_free_times(busy_times):
    """
    Gets a list of free times calculated from a list of busy times.
    :param busy_times: is the list of busy times
    :return: a list of free times in ascending order.
    """
    app.logger.debug('Entering get_free_times')
    free_times = []
    is_first = True
    stored_event = arrow.now()

    # TODO refactor using a table

    for event in busy_times:
        if is_first:
            stored_event = event

        event_start = arrow.get(event['start']['dateTime'])
        event_end = arrow.get(event['end']['dateTime'])
        start_time = int(event_start.format('HHmm'))
        end_time = int(event_end.format('HHmm'))
        event_day = int(arrow.get(
            event['start']['dateTime']).format('YYYYMMDD'))
        day_start = arrow.get(
            event['start']['dateTime']).replace(hour=START_TIME, minute=0)
        stored_event_day = int(arrow.get(
            stored_event['start']['dateTime']).format('YYYYMMDD'))
        stored_event_end = stored_event['end']['dateTime']

        if start_time == 900 and end_time == 1700:
            stored_event = event
        elif start_time == 900 and end_time < 1700:
            if not is_first:
                if stored_event_day < event_day:
                    prev_day_end = arrow.get(
                        stored_event['end']['dateTime']).replace(hour=END_TIME,
                                                                 minute=0)
                    free_times.append((stored_event_end,
                                       prev_day_end.isoformat()))
                    print('1 {} - {}'.format(stored_event_end,
                                             prev_day_end.isoformat()))
            else:
                is_first = False
            stored_event = event
        elif start_time > 900 and end_time < 1700:
            if not is_first:
                if stored_event_day < event_day:
                    prev_day_end = arrow.get(
                        stored_event['end']['dateTime']).replace(hour=END_TIME,
                                                                 minute=0)
                    free_times.append((stored_event_end,
                                       prev_day_end.isoformat()))
                    print('2 {} - {}'.format(stored_event_end,
                                             prev_day_end.isoformat()))
                if event_day != stored_event_day:
                    free_times.append((day_start.isoformat(),
                                       event_start.isoformat()))
                    print('3 {} - {}'.format(day_start.isoformat(),
                                             event_start.isoformat()))
                elif event_day == stored_event_day:
                    free_times.append((stored_event_end,
                                       event_start.isoformat()))
                    print('4 {} - {}'.format(stored_event_end,
                                             event_start.isoformat()))
            else:
                is_first = False
            stored_event = event
        elif start_time > 900 and end_time == 1700:
            if not is_first:
                if stored_event_day < event_day:
                    prev_day_end = arrow.get(
                        stored_event['end']['dateTime']).replace(hour=END_TIME,
                                                                 minute=0)
                    free_times.append((stored_event_end,
                                       prev_day_end.isoformat()))
                    print('5 {} - {}'.format(stored_event_end,
                                             prev_day_end.isoformat()))
                if event_day != stored_event_day:
                    free_times.append((day_start.isoformat(),
                                       event_start.isoformat()))
                    print('6 {} - {}'.format(day_start.isoformat(),
                                             event_start.isoformat()))
                elif event_day == stored_event_day:
                    free_times.append((stored_event_end,
                                       event_start.isoformat()))
                    print('7 {} - {}'.format(stored_event_end,
                                             event_start.isoformat()))
            else:
                is_first = False
            stored_event = event

    print()

    return free_times


def list_times(service):
    """
    Lists the times from the selected calendar in ascending order.
    :param service: a google 'service' object
    :return: a sorted list of times for the selected calendar(s)
    """
    app.logger.debug('Entering list_times')

    busy_times = get_busy_times(service)

    # free_times = get_free_times(busy_times)
    #
    # return busy_times, free_times
    return busy_times


def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict, so that
    it can be stored in the session object and converted to
    json for cookies. The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    :param service: a google 'service' object
    :return: a sorted list of calendars
    """
    app.logger.debug("Entering list_calendars")
    calendar_list = service.calendarList().list().execute()
    result = []

    for cal in calendar_list["items"]:
        kind = cal["kind"]
        cal_id = cal["id"]

        # if "description" in cal:
        #     desc = cal["description"]
        # else:
        #     desc = "(no description)"
        summary = cal["summary"]

        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]

        result.append(
            {"kind": kind,
             "id": cal_id,
             "summary": summary,
             "selected": selected,
             "primary": primary
             })

    return sorted(result, key=cal_sort_key)


def cal_sort_key(cal):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    :param cal: a calendars
    :return: the sorted calendar
    """
    if cal["selected"]:
        selected_key = " "
    else:
        selected_key = "X"
    if cal["primary"]:
        primary_key = " "
    else:
        primary_key = "X"

    return primary_key, selected_key, cal["summary"]


# Functions used within the templates

@app.template_filter('fmtdate')
def format_arrow_date(date):
    try:
        normal = arrow.get(date)
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"


@app.template_filter('fmttime')
def format_arrow_time(time):
    try:
        normal = arrow.get(time)
        return normal.format("HH:mm")
    except:
        return "(bad time)"


@app.template_filter('fmtdatetime')
def format_arrow_date_time(date_time):
    try:
        normal = arrow.get(date_time)
        return normal.format("HH:mm, dddd, MM/DD/YYYY")
    except:
        return "(bad date)"


if __name__ == "__main__":
    import uuid

    app.secret_key = str(uuid.uuid4())
    app.debug = CONFIG.DEBUG
    app.logger.setLevel(logging.DEBUG)
    if CONFIG.DEBUG:
        app.run(port=CONFIG.PORT)
    else:
        app.run(port=CONFIG.PORT, host="0.0.0.0")
