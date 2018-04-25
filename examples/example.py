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

# find all sources available to account
#all_sources = session.get_all_sources()

# find all sources that contain 'times' in their titles
#times_sources = session.search_sources(query='times')

# get the included and excluded publication titles for a source id
#source_details = session.get_source_details(source_id=8399)

# run a query for a keyword within a given source id
results = []
for result_packet in session.search(query='checkers', source_id=8399,
    start_date='2017-08-01', end_date='2017-08-02', yield_results=True,
    save_results=True):
  results += list(result_packet) if result_packet else []

print(' * found the following results', results)