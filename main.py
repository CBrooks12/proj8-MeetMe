import flask
from flask import render_template
from flask import request
from flask import url_for
from flask import jsonify # For AJAX transactions
import uuid
import sys
import json
import logging
import operator
# Date handling 
import arrow # Replacement for datetime, based on moment.js
import datetime # But we still need time
from dateutil import tz  # For interpreting local times


# Mongo database
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId


# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services 
from apiclient import discovery

###
# Globals
###
import CONFIG
app = flask.Flask(__name__)

try: 
    dbclient = MongoClient(CONFIG.MONGO_URL)
    db = dbclient.busytimes
    collection = db.dated

except:
    print("Failure opening database.  Is Mongo running? Correct password?")
    sys.exit(1)

import uuid
app.secret_key = str(uuid.uuid4())


SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = CONFIG.GOOGLE_LICENSE_KEY  ## You'll need this
APPLICATION_NAME = 'MeetMe class project'

#############################
#
#  Pages (routed from URLs)
#
#############################

@app.route("/")
@app.route("/index")
def index():
  app.logger.debug("Entering index")
  flask.session['key']=None
  if 'begin_date' not in flask.session:
    init_session_values()
  return render_template('index.html')

@app.route("/choose")
def choose():
    ## We'll need authorization to list calendars 
    ## I wanted to put what follows into a function, but had
    ## to pull it back here because the redirect has to be a
    ## 'return' 
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
      app.logger.debug("Redirecting to authorization")
      return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.session['calendars'] = list_calendars(gcal_service)
    if flask.session.get('key') == None:
        return render_template('index.html')
    else:
        return render_template('planner.html')


@app.route("/planner")
def planner():
    app.logger.debug("Entering index")
    if 'begin_date' not in flask.session:
        init_session_values()
    ##The long road
    print("here we go")
    if request.args.get('key'):
        key = request.args.get('key')
        flask.session['key'] = key
        print("KEY ="+key)
        for record in collection.find({"_id":ObjectId(key)}):
            print(record)
            tempRec = record
        tempRec = tempRec['types']
        try:
            flask.session['begin_date'] = tempRec['startTime']
            flask.session['end_date'] = tempRec['endTime']
        except:
            print("flask session was not created")
    else:
        print("no key")
    #FINALLY RENDER PAGE
    return set_range_planner()
    #return render_template('planner.html')

####
#
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
#  get a fresh serivce object from our credentials, which are
#  serializable. 
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead. 
#
####

def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value. 
    """
    if 'credentials' not in flask.session:
      return None

    credentials = client.OAuth2Credentials.from_json(
        flask.session['credentials'])

    if (credentials.invalid or
        credentials.access_token_expired):
      return None
    return credentials


def get_gcal_service(credentials):
  """
  We need a Google calendar 'service' object to obtain
  list of calendars, busy times, etc.  This requires
  authorization. If authorization is already in effect,
  we'll just return with the authorization. Otherwise,
  control flow will be interrupted by authorization, and we'll
  end up redirected back to /choose *without a service object*.
  Then the second call will succeed without additional authorization.
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
  flow =  client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope= SCOPES,
      redirect_uri=flask.url_for('oauth2callback', _external=True))
  ## Note we are *not* redirecting above.  We are noting *where*
  ## we will redirect to, which is this function. 
  
  ## The *second* time we enter here, it's a callback 
  ## with 'code' set in the URL parameter.  If we don't
  ## see that, it must be the first time through, so we
  ## need to do step 1. 
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    ## This will redirect back here, but the second time through
    ## we'll have the 'code' parameter set
  else:
    ## It's the second time through ... we can tell because
    ## we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    ## Now I can build the service and execute the query,
    ## but for the moment I'll just log it and go back to
    ## the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('choose'))

#####
#
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use. 
#
#####

@app.route('/setrange', methods=['POST'])
def setrange():
    """
    User chose a date range with the bootstrap daterange
    widget.
    """
    app.logger.debug("Entering setrange")  
    flask.flash("Setrange gave us '{}'".format(
      request.form.get('daterange')))
    daterange = request.form.get('daterange')
    flask.session['daterange'] = daterange
    daterange_parts = daterange.split()
    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])
    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
      daterange_parts[0], daterange_parts[1], 
      flask.session['begin_date'], flask.session['end_date']))
    return flask.redirect(flask.url_for("choose"))

def set_range_planner():
    """
    User chose a date range with the bootstrap daterange
    widget.
    """

    for record in collection.find({"_id":ObjectId(flask.session.get('key'))}):
        #flask.session['localDict'] = collection.findOne({"_id":ObjectId(key)})
        tempRecordHolder = record['types']
    print("tempRecordHolder")
    #daterange = request.form.get('daterange')
    #flask.session['daterange'] = daterange
    #daterange_parts = daterange.split()
    flask.session['begin_date'] = tempRecordHolder['startTime']
    flask.session['end_date'] =  tempRecordHolder['endTime']
    print("made it here")
    return flask.redirect(flask.url_for("choose"))


####
#
#   Initialize session variables 
#
####

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
    # Default time span each day, 8 to 5
    flask.session["begin_time"] = interpret_time("9am")
    flask.session["end_time"] = interpret_time("5pm")

def interpret_time( text ):
    """
    Read time in a human-compatible format and
    interpret as ISO format with local timezone.
    May throw exception if time can't be interpreted. In that
    case it will also flash a message explaining accepted formats.
    """
    app.logger.debug("Decoding time '{}'".format(text))
    time_formats = ["ha", "h:mma",  "h:mm a", "H:mm"]
    try: 
        as_arrow = arrow.get(text, time_formats).replace(tzinfo=tz.tzlocal())
        app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
              .format(text))
        raise
    return as_arrow.isoformat()

def interpret_date( text ):
    """
    Convert text of date to ISO format used internally,
    with the local time zone.
    """
    try:
      as_arrow = arrow.get(text, "MM/DD/YYYY").replace(
          tzinfo=tz.tzlocal())
    except:
        flask.flash("Date '{}' didn't fit expected format 12/31/2001")
        raise
    return as_arrow.isoformat()

def next_day(isotext):
    """
    ISO date + 1 day (used in query to Google calendar)
    """
    as_arrow = arrow.get(isotext)
    return as_arrow.replace(days=+1).isoformat()

####
#
#  Functions (NOT pages) that return some information
#
####
@app.route("/_getBusy")
def setupBusy():
    item_ids = json.loads(request.args.get('calData'))
    startTime = request.args.get('start')
    endTime = request.args.get('end')
    app.logger.debug(item_ids)
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
      app.logger.debug("Redirecting to authorization")
      return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.session['busyTimes'] = getBusy(gcal_service,item_ids,startTime,endTime)
    print(flask.session.get('busyTimes'))
    d = json.dumps(flask.session.get('busyTimes'))	
    return jsonify(result = d)

#api function to retrieve busy times from google.
#retrieves array of calendars and interval of free time
def getBusy(service,item_ids,startTime,endTime):
    #app.logger.debug(flask.session["begin_date"])
    begin = flask.session['begin_date']
    end = flask.session['end_date']
    if begin == end: 
        end = arrow.get(end).replace(days=+1).isoformat()
    calBusyTimes = []
    for calendars in item_ids:
        app.logger.debug(calendars)
        calBusy = {
        "timeMin" : begin,
        "timeMax" : end,
        "items":[
          {
           "id" :  calendars
          }
        ] #data.objId
        }
        freebusyResponse = service.freebusy().query(body = calBusy)
        busyRecords = freebusyResponse.execute()
        #app.logger.debug(busyRecords)
        calBusyTimes.append(busyRecords)
        app.logger.debug(calBusyTimes)
    calDictDates = cal_date_parse(calBusyTimes,startTime,endTime)
    if flask.session.get('key') != None:
        for record in collection.find({"_id":ObjectId(flask.session.get('key'))}):
            tempRecordHolder = record['types']
        calDictDates = combine_calendars(tempRecordHolder,calDictDates)
        try:
            collection.update_one(
            {"_id":ObjectId(flask.session.get("key"))},
            {
                "$set": { 
                "types": calDictDates
                }
            })
        except:
        #e = sys.exc_info()[0]
       #write_to_page( "<p>Error: %s</p>" % e )
            print("broke you")
            #print("broke you: {}".format(e))
        d = {"core":calDictDates, "key":flask.session.get("key")}
        print("checkhf")
        return d
    try:
        collection.insert({"types":calDictDates})
    except:
        #e = sys.exc_info()[0]
        #write_to_page( "<p>Error: %s</p>" % e )
        print(" broke yo")
    for record in collection.find({}):
        try:
            record['_id'] = str(record['_id'])
        except:
            del record['_id']
        key = record['_id']
    d = {"core":calDictDates, "key":key}
    return d #returns list of free times with start/end over a certain period

def cal_date_parse(calBusyTimes,startTime,endTime):
    #setup initial variables
    startTimeHolder = startTime
    endTimeHolder = endTime
    print(endTimeHolder)
    print("we in cal_date")
    tempStartDate = arrow.get(flask.session["begin_date"])
    tempEndDate = arrow.get(flask.session["end_date"])
    print("what about here?")
    freeBusyList = []
    timeListWithDate = []
    finalDict = {"startTime":tempStartDate.isoformat(), "endTime":tempEndDate.isoformat(), "dates":None}
    print("made the finalDict")
    #loop through calendar list
    for calendars in calBusyTimes:
        calProperties = calendars['calendars'] #get the calendar properties
        try:
            tempList = calProperties[list(calProperties)[0]] #get the elements in the abstract key for calendar
            print("this worked")
        except:
            print("we broke the thing")
            tempList = calProperties['fakekey']
        for busyTimesPreSort in tempList['busy']:
            freeBusyList.append(busyTimesPreSort) #add the time to a localized list
    #freeBusyList.sort(key=operator.attrgetter("start"), reverse=False)
    try:
        freeBusyList = sorted(freeBusyList, key = byStart_key) #sort the localized list by earliest start times
        print("we sorted out bro")
    except:
        print("we didnt sort")
    #increments the start date by 1 day until start time is greater than the end time
    #this is keeping track of the free/busy times over the duration of the day
    while tempStartDate.timestamp <= tempEndDate.timestamp:
        startTime = startTimeHolder #holds the time of the start
        endTime = endTimeHolder   #holds the time of the endlocalDict
        start = tempStartDate  #stupid pointer for local loop
        #initialize the start time of the day array
        tempString = start.format('YYYY-MM-DD') + " " + str(startTime)
        startTime = arrow.get(tempString, 'YYYY-MM-DD HH:mm')
        startTime = startTime.replace(hours=+8)
        startTime = startTime.to('US/Pacific')
        #app.logger.debug(startTime)localDict
        start = startTime
        tempString = start.format('YYYY-MM-DD') + " " + str(endTime)
        endTime = arrow.get(tempString, 'YYYY-MM-DD HH:mm')
        endTime = endTime.replace(hours=+8)
        endTime = endTime.to('US/Pacific')
        end = start
        timeArr = []
        #loop through busy times of our localized list and generate an array of all the free/busy times
        #of the tempStartDate time day
        for busyTime in freeBusyList:
            busyTimeStart = arrow.get(busyTime["start"])
            busyTimeStart = busyTimeStart.to('US/Pacific') #convert time to correct time zone
            busyTimeEnd = arrow.get(busyTime["end"])
            busyTimeEnd = busyTimeEnd.to('US/Pacific')
            #if the busy time is on the same day as the day we are making the list for
           
            if busyTimeStart.format('YYYY-MM-DD') == tempStartDate.format('YYYY-MM-DD'):
                #if the busy times start time is before the temporary local pointer (lastest time of activity)

                #if busy time starts after the current freetime, cut off free time and move to next open time
                if busyTimeStart.timestamp>=start.timestamp and busyTimeStart.timestamp<=endTime.timestamp:
                    end = busyTimeStart
                    timeArr.append([start.isoformat(),end.isoformat()])
                    if busyTimeEnd.timestamp>endTime.timestamp:
                        start = endTime
                        break
                    else:
                        start = busyTimeEnd
                #else, create a free time before creating the busy time
                elif busyTimeEnd.timestamp >= start.timestamp and busyTimeEnd.timestamp <= endTime.timestamp:
                    start = busyTimeEnd
        if start.timestamp != endTime.timestamp:
            #timeArr.append([start.format('HH:mm'),endTime.format('HH:mm')])
            timeArr.append([start.isoformat(),endTime.isoformat()])
        #app.logger.debug(tempStartDate) #debug
        timeListWithDate.append({"date": tempStartDate.isoformat(), "data":timeArr})
        tempStartDate = tempStartDate.replace(days=+1)  #add day to localized time pointer (iterating to end date)
    finalDict["dates"] = timeListWithDate
    app.logger.debug(finalDict)
    return finalDict #returns list of free times with start/end over a certain period

def fake_busy_meeting_create(date,start,end):
    date = arrow.get(date)
    print("check a:")
    print(date)
    tempString = date.format('YYYY-MM-DD') + " " + str(start)
    startTime = arrow.get(tempString, 'YYYY-MM-DD HH:mm')
    startTime = startTime.replace(hours=+8)
    startTime = startTime.to('US/Pacific')
    tempString = date.format('YYYY-MM-DD') + " " + str(end)
    endTime = arrow.get(tempString, 'YYYY-MM-DD HH:mm')
    endTime = endTime.replace(hours=+8)
    endTime = endTime.to('US/Pacific')
    print("check4")
    fakeDict = {
               "calendars": {
               "fakekey":{
               "busy": [
               {
                       "start": startTime.isoformat(),
                        "end": endTime.isoformat()
               }
                       ]
               }
               }
    }
    print("check5")
    return fakeDict

def combine_calendars(calInit,calNew):
    newDataList = []
    tempInit = calInit['dates']
    newDates = []
    for timesInit in tempInit:
        freeTimeInit = timesInit['data']
        initDate = timesInit['date']
        innerData = []
        for timeLocal in freeTimeInit:         
            tempNew = calNew['dates']
            for timesNew in tempNew:
                freeTimeNew = timesNew['data']
                newDate = timesNew['date']
                print(initDate)
                initDate = arrow.get(initDate)
                newDate = arrow.get(newDate)
                #print(newDate)
                print(initDate.format('YYYY-MM-DD')+ " == " + newDate.format('YYYY-MM-DD'))
                if initDate.format('YYYY-MM-DD') != newDate.format('YYYY-MM-DD'):
                    continue
                for timeForeign in freeTimeNew:
                    print(timeLocal)
                    print(timeLocal[0])
                    print(timeForeign)
                    print(timeForeign[0])
                    #timeForBeg = arrow.get('2015-12-03T09:00:00+00:00')
                    timeForBeg = arrow.get(timeForeign[0])
                    print("timeForBeg: " + str(timeForBeg))
                    timeForBeg = timeForBeg.timestamp
                    timeForEnd = arrow.get(timeForeign[1])
                    timeForEnd = timeForEnd.timestamp
                    timeLocBeg = arrow.get(timeLocal[0])
                    timeLocBeg = timeLocBeg.timestamp
                    timeLocEnd = arrow.get(timeLocal[1])
                    timeLocEnd = timeLocEnd.timestamp
                    print("wtf?")
                    if timeForBeg <= timeLocBeg and timeLocBeg <= timeForEnd:
                        tempNewStartFree = timeLocal[0]
                    elif timeLocBeg <= timeForBeg and timeForBeg <= timeLocEnd:
                        tempNewStartFree = timeForeign[0]
                    else:
                        continue
                    startTempQuack = arrow.get(tempNewStartFree)
                    startTempQuack = startTempQuack.timestamp
                    if startTempQuack <= timeLocEnd and timeLocEnd <= timeForEnd:
                         tempNewEndFree = timeLocal[1]
                    else:
                         tempNewEndFree = timeForeign[1]
                    endTempQuack = arrow.get(tempNewEndFree)
                    endTempQuack = endTempQuack.timestamp
                    if startTempQuack == endTempQuack:
                         print("quack")
                    else:
                         innerData.append([tempNewStartFree,tempNewEndFree])
        newDates.append({ "date": initDate.isoformat(), "data":innerData })
    finalDict = { "startTime":calInit['startTime'],"endTime":calInit['endTime'],"dates":newDates }
    print("got here")
    return finalDict
@app.route("/_delKey")
def delKeyDict():
    key = request.args.get('key')
    try:
        collection.remove({"_id":ObjectId(key)})
        print("key deleted")
    except:
        print("key not deleted")
    d = {"key":key}
    d = json.dumps(d)	
    return jsonify(result = d)

@app.route("/_getMeeting")
def meeting_entry_init():
    date = request.args.get('date')
    startTime = request.args.get('start')
    endTime = request.args.get('end')
    print("check1")
    print(startTime)
    print(endTime)
    fakeDict = fake_busy_meeting_create(date,startTime,endTime)
    print("check2")
    tempStart = "00:00"
    tempEnd = "23:59"
    print(tempEnd)
    print(flask.session["end_date"])
    print(fakeDict)
    tempfakeDictArr = []
    tempfakeDictArr.append(fakeDict)
    tempMeetDict = cal_date_parse(tempfakeDictArr,tempStart,tempEnd)
    print("check3")
    if flask.session.get('key') != None:
        for record in collection.find({"_id":ObjectId(flask.session.get('key'))}):
            tempRecordHolder = record['types']
        finalDict = combine_calendars(tempRecordHolder,tempMeetDict)
    try:
        collection.update_one(
            {"_id":ObjectId(flask.session.get("key"))},
            {
                "$set": { 
                "types": finalDict
                }
            })
    except:
        print("broke shit")
    d = {"core":finalDict, "key":flask.session.get("key")}
    d = json.dumps(d)	
    return jsonify(result = d)

#sort function
def byStart_key(time):
    time = arrow.get(time["start"])
    app.logger.debug(time)
    return time.timestamp

def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict, so that
    it can be stored in the session object and converted to
    json for cookies. The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    """
    app.logger.debug("Entering list_calendars")  
    calendar_list = service.calendarList().list().execute()["items"]
    result = [ ]
    for cal in calendar_list:
        kind = cal["kind"]
        id = cal["id"]
        if "description" in cal: 
            desc = cal["description"]
        else:
            desc = "(no description)"
        summary = cal["summary"]
        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]
        
        result.append(
          { "kind": kind,
            "id": id,
            "summary": summary,
            "selected": selected,
            "primary": primary
            })
    return sorted(result, key=cal_sort_key)


def cal_sort_key( cal ):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    """
    if cal["selected"]:
       selected_key = " "
    else:
       selected_key = "X"
    if cal["primary"]:
       primary_key = " "
    else:
       primary_key = "X"
    return (primary_key, selected_key, cal["summary"])


#################
#
# Functions used within the templates
#
#################

@app.template_filter( 'fmtdate' )
def format_arrow_date( date ):
    try: 
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

@app.template_filter( 'fmttime' )
def format_arrow_time( time ):
    try:
        normal = arrow.get( time )
        return normal.format("HH:mm")
    except:
        return "(bad time)"
    
#############


if __name__ == "__main__":
  # App is created above so that it will
  # exist whether this is 'main' or not
  # (e.g., if we are running in a CGI script)

  app.secret_key = str(uuid.uuid4())  
  app.debug=CONFIG.DEBUG
  app.logger.setLevel(logging.DEBUG)
  # We run on localhost only if debugging,
  # otherwise accessible to world
  if CONFIG.DEBUG:
    # Reachable only from the same computer
    app.run(port=CONFIG.PORT)
  else:
    # Reachable from anywhere 
    app.run(port=CONFIG.PORT,host="0.0.0.0")
    
