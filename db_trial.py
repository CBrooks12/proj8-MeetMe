"""
Just to test database functions,
outside of Flask.

We want to open our MongoDB database,
insert some memos, and read them back
"""
import arrow

# Mongo database
from pymongo import MongoClient
import CONFIG
try: 
    dbclient = MongoClient(CONFIG.MONGO_URL)
    db = dbclient.busytimes
    collection = db.dated

except:
    print("Failure opening database.  Is Mongo running? Correct password?")
    sys.exit(1)

#
# Insertions:  I commented these out after the first
# run successfuly inserted them
# 

record = { "type": "dated_memo",
           "startTime": '234',
           "endTime": '456',
           "dates": [{ "date":'123',
                       "data":[['123','123'],
                               ['123','1123']]
                     },
                     { "date":'123',
                       "data":[['123','123'],
                               ['123','1123']]
                     }
                     ]
          }
collection.insert(record)
record = { "type": "dated_memo",
           "startTime": '244444',
           "endTime": '456',
           "dates": [{ "date":'123',
                       "data":[['123','123'],
                               ['123','1123']]
                     },
                     { "date":'123',
                       "data":[['123','123'],
                               ['123','1123']]
                     }
                     ]
          }
collection.insert(record)
collection.remove({})
#
# Read database --- May be useful to see what is in there,
# even after you have a working 'insert' operation in the flask app,
# but they aren't very readable.  If you have more than a couple records,
# you'll want a loop for printing them in a nicer format. 
#

records = [ ] 
for record in collection.find( { "type": "dated_memo" }):
   records.append(
        { "startTime": record['startTime'],
           "endTime": record['endTime'],
           "dates": [{ "date":'123',
                       "data":[['123','123'],
                               ['123','1123']]
                     },
                     { "date":'123',
                       "data":[['123','123'],
                               ['123','1123']]
                     }
                     ]
          })
recordss = [ ] 
for record in collection.find( {}):
    print(record)
