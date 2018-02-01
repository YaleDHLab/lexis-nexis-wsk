import os, json, sys
# allow relative import from a parent directory
# nb: this isn't required if you pip install wsk
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from wsk import WSK

# initialize a WSK session, specifying email as project identifier
session = WSK(environment='www.lexisnexis.com', project_id='cucumber@yale.edu')

# specify mongo db connection details
session.set_db(dbname='wsk', uri='mongodb://localhost:27017')

# authenticate with the web service
token = session.authenticate(username=os.environ['WSK_USERNAME'],
    password=os.environ['WSK_PASSWORD'])

# find all sources that contain times
sources = session.search_sources(query='times')

# get the included and excluded publication titles for a source id
source_details = session.get_source_details(source_id=161887)

# run a query for a keyword within a given source id
results = session.search(query='peppers', source_id=161887,
    start_date='2017-10-01', end_date='2017-10-24',
    save_results=True, return_results=True)

print(results)