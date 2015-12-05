# proj8-meetme
set appointment data as busy from a selection of a user's Google calendars 

## What is here

I've provided code for the authorization (oauth2) protocol for Google
calendars.  There is also a picker for a date range. 

## ADDITIONAL COMMENTS

Code runs on local and should run on ix. You will need your own verification secret key to access google.
Change the port number in the CONFIG file to match your credentials when you made your key.

##IMPORTANT NOTE

the test file is not completed and some of the code may have glitches. If everything is done properly, the code will run fine. The results of improper time and date input is varied and not tested for. I will try to get this updated as soon as possible.

## Steps to run

i:make sure google secret key is placed in the root of the file and edit config file to match your port

ii:make install

iii: activate the virtual environment

iv: run program

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1:choose date

2:verify

3:choose calendars and enter time in correct 24 hour format (only works in PST)

4:auto updates with list of free times after clicking on calendars

5:take generated key and place in URL

6:select times in correct 24 hour format for second user

7:select calendar

8:auto updates with valid free times of combined calendars

9:enter in meeting time

10:press to confirm

11:meeting time will be updated as busy

you can also delete the key on the initial page if the creator wishes to
