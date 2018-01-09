# WSK

This module provides convenience wrappers around the Lexis Nexis Web Services Kit API. To use it, you'll need to make sure your university or organization has purchased access to the Lexis Nexis Web Services Kit API.

## Installation

To install this module and its dependencies, you can run:

```
pip install wsk
```

## Initializing

To use the module, you can import the module and begin a session like so:

```
from wsk import WSK

session = WSK(environment='www.lexisnexis.com', project_id='cucumber@yale.edu')
```

The `environment` argument specifies the server group to which queries will be addressed. The WSK supports three server groups (certification, preproduction, and production), each with their own urls. `www.lexisnexis.com` is the production server group.

Project ids are optional; we use them to identify the patron who made a request. If you save search results in MongoDB (see below), the `project_id` gets stored in each saved record.

### Authenticate

Before running any queries, you must authenticate with Lexis Nexis' WSK servers:

```
auth_token = session.authenticate(username='tonytiger', password='grrrrreat')
```

This returns an authentication token that can be used to make requests. The token is saved internally for future requests. Note that Lexis Nexis retires tokens after a period of time (~24 hours currently).

### Search

The primary purpose of this API wrapper is to make it easier to run searches against the Lexis Nexis WSK servers, which were constructed such that any query that would return more than 3000 results returns a 500 response. To get around those limits, the `search()` method breaks queries into smaller units and fetches results for each. To run a search, one can do:

```
result = session.search(query='mangoes', source_id=161887,
    start_date='2017-12-01', end_date='2017-12-02',
    return_results=True, save_results=False)
```

All metadata values provided by the WSK servers are preserved in the returned data:

```
[
  {
    "doc_id": "02A6A252C52394AB97B14672E56C2F2FCCDD7BAE57A673BD668A9FCD789E029E295CF05DF658309C98518204E57CEA3E98718EE36B01E278E92861C544DB206E222C9E931557C251FE6650D6127090E25DCE4621DF709B6AC25C7241C18D248BE04ACF603628131770B7F958603D9CFB",
    "headline": "Summer goes swimmingly",
    "attachment_id": "",
    "pub": " The Courier Mail (Australia)",
    "pub_date": "December",
    "length": "968  words"
  },
  {
    "doc_id": "02A6A252C52394AB97B14672E56C2F2FCCDD7BAE57A673BD668A9FCD789E029E295CF05DF658309C98518204E57CEA3E98718EE36B01E278E92861C544DB206E222C9E931557C251FE6650D6127090E25DCE4621DF709B6AC25C7241C18D248BAEC7AB8C2DC198F6978CC606D5CC96E5",
    "headline": "Investment Climate Somalia",
    "attachment_id": "LNCDBE032A334E6199CDC3D9022282D83E5256AC5DCBF73F89",
    "pub": "",
    "pub_date": "December",
    "length": "1836  words"
  }, ...
]
```

### Search Sources

The WSK endpoints require one to identify a `source_id` for each query. Searching the WSK sources is a way of retrieving `source_id` values. 

```
source_results = session.search_sources(query='times')
```

All metadata values provided by the WSK servers are preserved in the returned data:

```
[
  {
    "name": "Abbotsford Times (British Columbia)*",
    "source_id": 296030,
    "type": "Standard",
    "premium_source": true,
    "has_index": true,
    ...
  },
  {
    "name": "Accommodation Times (Ht Media)",
    "source_id": 377727,
    "type": "Standard",
    "premium_source": true,
    "has_index": true,
    ...
  },
  ...
]
```

### Find Publications in Source

To find the publication titles within a source, one can run:

```
source_details = session.get_source_details(source_id=161887)
```

All metadata values provided by the WSK servers are preserved in the returned data:

```
[
  {
    "source_name": "English Language News (Most recent 90 Days)",
    "file_name": "FILE-NAME: 90DAYS",
    "content_summary": "CONTENT-SUMMARY: Access to certain freelance articles and other features within this publication...",
    "full_text": [
      "COMPLETE FILE: ",
      "50 Plus Lifestyles*",
      "580 Split",
      "AAACN Viewpoint",
      "AANA Journal", ...
    ]
  }
]
```

## Store Results in MongoDB

A single query may return millions of documents, so instead of retrieving the results in RAM one can store query results on disk using a MongoDB. To do so, one can create a database connection as follows:

```
# specify the mongo db connection details
session.set_db(dbname='wsk', uri='mongodb://localhost:27017')
```

Then, when running search queries, save them in the db like so:

```
result = session.search(query='mangoes', source_id=161887,
    start_date='2017-12-01', end_date='2017-12-02',
    return_results=False, save_results=True)
```