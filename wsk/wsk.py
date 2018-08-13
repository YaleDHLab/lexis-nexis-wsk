from pymongo import MongoClient
from bs4 import BeautifulSoup, element
from datetime import datetime, timedelta
from random import random
import base64
import calendar
import copy
import json
import requests
import time
import sys
import math

class WSK:
  def __init__(self, environment='', project_id=''):
    self.environment = environment
    self.project_id = project_id
    self.auth_token = None
    self.verbose = True
    self.session_id = calendar.timegm(time.gmtime())


  def set_db(self, dbname='wsk', uri='mongodb://localhost:27017'):
    '''
    Create a MongoDB connection
    @param {str} dbname: the name of the db to use in Mongo
    @param {str} uri: a mongodb uri that specifies the db location
    '''
    self.db = MongoClient(uri)[dbname]


  def get_url(self, service, protocol='http'):
    '''
    Get the url for a query with the appropriate protocol and environment
    @param {str} service: the service endpoint to which the query will be sent
    @returns {str}: the fully-qualified url to which the request will be made
    '''
    return protocol + '://' + self.environment + '/wsapi/v1/services/' + service


  def get_headers(self, request):
    '''
    Get the headers for a query with the right content length attribute
    @param {str} request: an XML request object to be POST'ed to the WSK server
    @returns {obj}: the headers to be used in a WSK request
    '''
    return {
      'Host': self.environment,
      'Content-Type': 'text/xml; charset=UTF-8',
      'Content-Length': str(len(request)),
      'SOAPAction': ''
    }


  def save_results(self, results):
    '''
    Save all search results to the database
    @param: {arr} results: a list of search result objects
    '''
    if not self.db:
      raise Exception('Please call set_db() before saving records')
      return
    if not results:
      return
    prepared = []
    for i in results:
      i = copy.deepcopy(i)
      i['session_id'] = self.session_id
      i['project_id'] = self.project_id
      prepared.append(i)
    self.db.results.insert_many(prepared)


  ##
  # Authenticate
  ##

  def authenticate(self, username, password):
    '''
    Set the WSK's auth_token attribute by authenticating with the WSK servers
    @param {str} username: the user's WSK username
    @param {str} password: the user's WSK password
    '''
    request = '''
      <SOAP-ENV:Envelope
          xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
          SOAP-ENV:encodingStyle= "http://schemas.xmlsoap.org/soap/encoding/">
        <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <Authenticate xmlns="http://authenticate.authentication.services.v1.wsapi.lexisnexis.com">
            <authId>{0}</authId>
            <password>{1}</password>
          </Authenticate>
        </soap:Body>
      </SOAP-ENV:Envelope>
      '''.format(username, password)
    url = self.get_url('Authentication', protocol='https')
    headers = headers=self.get_headers(request)
    response = requests.post(url=url, headers=headers, data=request)
    try:
      soup = BeautifulSoup(response.text, 'lxml')
      self.auth_token = soup.find('binarysecuritytoken').string
      return self.auth_token
    except AttributeError:
      print(' * Authentication failure. Please verify your credentials and environment')
      sys.exit()


  ##
  # Browse Sources
  ##

  def get_all_sources(self):
    '''
    Get a list of the sources available to the current account. To do so, find
    all source types, then descend down the tree of folders to find all
    sources / leaf nodes. NB: Different folders have different depths one must
    descend to find sources / leaf nodes.
    '''
    # populate list of sources available to account
    sources = []
    # find the top order folder
    root_folders = self.browse_sources()
    # use the first source grouping folder to recurse through the folder hierarchy
    sub_folders = self.browse_sources(root_folders[0]['folder_id'])
    # descend into all sub folders and add any newly discovered sub folders to this list
    while sub_folders:
      sub_folder = sub_folders.pop(0)
      print(' * fetching sources in', sub_folder)
      # some results will contain parent folders, others contain source / leaf nodes
      result = self.browse_sources(sub_folder['folder_id'])
      if 'source_id' not in result[0]:
        sub_folders += result
      else:
        sources += result
    return sources


  def browse_sources(self, folder_id=''):
    '''
    Query for the sources to which the account has access. LexisNexis organizes
    sources into "folders". Each folder contains subfolders, which contain source
    information. To find all sources to which your account has access, one can choose
    a folder_id, find all subfolders, then find all sources within each of those
    subfolders and use the resulting set of sources.
    @param {str} folder_id: The high order folder to search for sources. If a
      folder_id is not provided, the query result will contain a list of available
      folder names and folder ids.
    @returns {obj} If the user did not provide a folder_id, obj will be a list
      of objects, where each object has name and folder_id attributes that describe
      a top-level folder.

      If the user provided a folder_id and that folder_id has children folders, obj
      will contain a list of objects, where each object has name and folder_id attributes
      that describe a subfolder within the queried folder_id.

      If the user provided a folder_id and that folder_id contains a list of sources,
      obj will contain a list of objects where each object contains source_id,
      type, name, and other metadata attributes.
    '''
    # assemble the folder argument to be passed to the soap request
    folder_arg = '<folderId>{0}</folderId>'.format(folder_id) if folder_id else ''
    # assemble the browse source query
    request = '''
    <SOAP-ENV:Envelope
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
        SOAP-ENV:encodingStyle= "http://schemas.xmlsoap.org/soap/encoding/">
      <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <BrowseSources xmlns="http://browsesources.source.services.v1.wsapi.lexisnexis.com">
          <locale>en-US</locale>
          <binarySecurityToken>{0}</binarySecurityToken>
          {1}
        </BrowseSources>
      </soap:Body>
    </SOAP-ENV:Envelope>
    '''.format(self.auth_token, folder_arg)
    url = self.get_url('Source')
    headers = self.get_headers(request)
    response = requests.post(url=url, headers=headers, data=request)
    soup = BeautifulSoup(response.text, 'lxml')
    results = []

    # parse out the sources identified for this query
    # nb: sources have differnet namespace prefixes
    sources = []
    for i in soup.find('sourcelist').findChildren():
      if 'source' in i.name:
        if 'sourceid' not in i.name and 'premiumsource' not in i.name:
          sources.append(i)

    # case where query result contains sources
    if sources:
      for i in sources:
        results.append({
          'name': find_tag_by_name(i, 'name').get_text(),
          'source_id': int(find_tag_by_name(i, 'sourceid').get_text()),
          'type': find_tag_by_name(i, 'type').get_text(),
          'premium_source': find_tag_by_name(i, 'premiumsource').get_text(),
          'has_index': bool(find_tag_by_name(i, 'hasindex').get_text()),
          'has_toc': bool(find_tag_by_name(i, 'hastoc').get_text()),
          'versionable': bool(find_tag_by_name(i, 'versionable').get_text()),
          'is_page_browsable': bool(find_tag_by_name(i, 'ispagebrowsable').get_text()),
        })

    # case where query result contains folders
    else:
      for i in soup.find_all('folder'):
        results.append({
          'name': i.find('name').get_text(),
          'folder_id': i.find('folderid').get_text()
        })

    return results


  ##
  # Search Sources
  ##

  def search_sources(self, query):
    '''
    @param: {str} query: a query for sources
    @returns: {arr}: a list of source metadata objects that match the query
    '''
    request = '''
      <SOAP-ENV:Envelope
          xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
          SOAP-ENV:encodingStyle= "http://schemas.xmlsoap.org/soap/encoding/">
        <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <SearchSources xmlns="http://searchsources.source.services.v1.wsapi.lexisnexis.com">
            <locale>en-US</locale>
            <binarySecurityToken>{0}</binarySecurityToken>
            <partialSourceName>{1}</partialSourceName>
          </SearchSources>
        </soap:Body>
      </SOAP-ENV:Envelope>
      '''.format(self.auth_token, query)

    url = self.get_url('Source')
    headers = self.get_headers(request)
    response = requests.post(url=url, headers=headers, data=request)
    soup = BeautifulSoup(response.text, 'xml')
    sources = []
    for i in soup.find_all('source'):
      combinable_list = []
      for j in i.find_all('combinability'):
        combinable_list.append(j.text)
      sources.append({
        'name': i.find('name').text,
        'source_id': int(i.find('sourceId').text),
        'type': i.find('type').text,
        'premium_source': bool(i.find('premiumSource').text),
        'has_index': bool(i.find('hasIndex').text),
        'versionable': bool(i.find('versionable').text),
        'is_page_browsable': bool(i.find('isPageBrowsable').text),
        'combinability': combinable_list
      })
    return sources


  ##
  # Get Source Details
  ##

  def get_source_details(self, source_id):
    '''
    @param: {int} source_id: a source id for which details are requested
    @returns: {arr}: a list of objects describing titles in the source id
    '''
    request = '''
      <SOAP-ENV:Envelope
          xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
          SOAP-ENV:encodingStyle= "http://schemas.xmlsoap.org/soap/encoding/">
        <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <GetSourceDetails xmlns="http://getsourcedetails.source.services.v1.wsapi.lexisnexis.com">
            <binarySecurityToken>{0}</binarySecurityToken>
            <sourceId>{1}</sourceId>
            <includeSourceElement>true</includeSourceElement>
          </GetSourceDetails>
        </soap:Body>
      </SOAP-ENV:Envelope>
      '''.format(self.auth_token, source_id)

    url = self.get_url('Source')
    headers = self.get_headers(request)
    response = requests.post(url=url, headers=headers, data=request)
    soup = BeautifulSoup(response.text, 'lxml')
    sources = []
    for i in soup.find('sourceguidelist').find_all('sourceguide'):
      sources.append(self.parse_source_details(i))
    return sources


  def parse_source_details(self, soup):
    '''
    @param: {BeautifulSoup} soup: contains the sourceguide tag from a
      get_source_details() query
    @returns: {obj}: an object that details the titles in the current source
    '''
    source = base64.b64decode(soup.string)
    source_soup = BeautifulSoup(source, 'lxml')
    exclusions = source_soup.find('div', {'EXCLUSIONS'}).find_all('p')[3]
    return dict({
      'source_name': source_soup.find('div', {'class': 'PUBLICATION-NAME'}).text,
      'file_name': source_soup.find('div', {'class': 'FILE-NAME'}).text,
      'content_summary': source_soup.find('div', {'class': 'CONTENT-SUMMARY'}).text,
      'full_text': split_on_br(source_soup.find('div', {'FULL-TEXT'})),
      'selected_text': split_on_br(source_soup.find('div', {'SELECTED-TEXT'})),
      'also_contains': split_on_br(source_soup.find('div', {'ALSO-CONTAINS'})),
      'exclusions': split_on_br(exclusions),
    })


  def search(self, *args, **kwargs):
    '''
    Submit a search to the WSK API. Creates a new Search() instance
    to manage search state and fetch all documents entailed by the search.
    '''
    save_results = kwargs.get('save_results', True)
    yield_results = kwargs.get('yield_results', False)
    results = []

    query = Search(
      session=self,
      query=kwargs.get('query', None),
      source_id=kwargs.get('source_id', None),
      start_date=kwargs.get('start_date', '2017-12-01'),
      end_date=kwargs.get('start_date', '2017-12-01'),
      get_text=kwargs.get('get_text', True),
      per_page=kwargs.get('per_page', 10),
      save_results=save_results,
      yield_results=yield_results,
    )

    for result in query.run():
      if yield_results:
        yield result

##
# Search
##

class Search:
  def __init__(self, *args, **kwargs):
    self.session = kwargs.get('session', None)
    self.query = kwargs.get('query', None)
    self.source_id = kwargs.get('source_id', None)
    self.save_results = kwargs.get('save_results', True)
    self.yield_results = kwargs.get('yield_results', False)
    self.get_text = kwargs.get('get_text', True)
    self.per_page = kwargs.get('per_page', 10)
    self.start_date = string_to_date(kwargs.get('start_date', '2017-12-01'))
    self.end_date = string_to_date(kwargs.get('end_date', '2017-12-02'))
    # state
    self.search_id = None
    self.results = []
    self.total_results = float('inf')
    self.result_start = 1
    self.result_end = self.per_page
    self.time_delta = 1
    self.query_start_date = self.start_date
    self.query_end_date = self.start_date + timedelta(days=self.time_delta)
    self.more_days_to_query = True
    self.more_pages_to_query = True


  def reset_result_indices(self):
    '''
    Set class attributes to fetch the first page of results
    '''
    self.result_start = 1
    self.result_end = self.per_page
    self.total_results = float('inf')


  def advance_result_indices(self):
    '''
    Slide the result indices one page forward
    '''
    self.result_start += self.per_page
    self.result_end += self.per_page


  def advance_date_range(self):
    '''
    Advance the start and end query dates by `self.time_delta`
    '''
    self.query_start_date += timedelta(days=self.time_delta)
    self.query_end_date += timedelta(days=self.time_delta)
    self.reset_result_indices()


  def log_current_search(self):
    '''
    Log the current search parameters
    '''
    start_date = date_to_string(self.query_start_date)
    end_date = date_to_string(self.query_end_date)
    print(' * querying for', self.query,
      '- source_id', self.source_id,
      '- result_start', self.result_start,
      '- result_end', self.result_end,
      '- start_date', start_date,
      '- end_date', end_date)


  def run(self):
    '''
    Run a full query for the user, fetching all doc metadata and content
    @returns: {obj} an object with metadata describing search results data
    '''
    while self.more_days_to_query:
      # initialize pagination params for the new page
      self.reset_result_indices()
      # fetch all results for this day then all days
      while self.more_days_to_query or self.more_pages_to_query:
        # run a search first, then use get_documents_by_range to get docs
        if self.result_start == 1:
          results = self.search()
        else:
          results = self.get_documents_by_range()
        # handle the new results
        if results:
          if self.yield_results: yield results
          if self.save_results: self.session.save_results(results)
        # case where there are no results for query
        if self.total_results == 0:
          self.more_pages_to_query = False
          # case where there are more dates to cover
          if self.query_end_date < self.end_date:
            self.advance_date_range()
          # case where we've processed all days
          else:
            self.more_days_to_query = False
        # continue paginating over results for the current date range
        if self.result_end < self.total_results:
          self.advance_result_indices()
        # pagination is done, check whether to slide the date window forward
        else:
          self.more_pages_to_query = False
          if self.query_end_date < self.end_date:
           self.advance_date_range()
           # check whether to extend the time advancing slide
           if self.total_results < (self.per_page/2):
            self.time_delta += 1
          else:
            self.more_days_to_query = False


  def search(self):
    '''
    Method that actually submits search requests. Called from self.search(),
    which controls the logic that constructs the individual searches
    '''
    self.log_current_search()

    request = '''
      <SOAP-ENV:Envelope
          xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
          SOAP-ENV:encodingStyle= "http://schemas.xmlsoap.org/soap/encoding/">
        <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <Search xmlns="http://search.search.services.v1.wsapi.lexisnexis.com">
            <binarySecurityToken>{0}</binarySecurityToken>
            <sourceInformation>
              <sourceIdList xmlns="http://common.search.services.v1.wsapi.lexisnexis.com">
                <sourceId xmlns="http://common.services.v1.wsapi.lexisnexis.com">{1}</sourceId>
              </sourceIdList>
            </sourceInformation>
            <query>{2}</query>
            <projectId>{3}</projectId>
            <searchOptions>
              <sortOrder xmlns="http://common.search.services.v1.wsapi.lexisnexis.com">Date</sortOrder>
              <dateRestriction xmlns="http://common.search.services.v1.wsapi.lexisnexis.com">
                <startDate>{4}</startDate>
                <endDate>{5}</endDate>
              </dateRestriction>
            </searchOptions>
            <retrievalOptions>
              <documentView xmlns="http://result.common.services.v1.wsapi.lexisnexis.com">Cite</documentView>
              <documentMarkup xmlns="http://result.common.services.v1.wsapi.lexisnexis.com">Display</documentMarkup>
              <documentRange xmlns="http://result.common.services.v1.wsapi.lexisnexis.com">
                <begin>{6}</begin>
                <end>{7}</end>
              </documentRange>
            </retrievalOptions>
          </Search>
        </soap:Body>
      </SOAP-ENV:Envelope>
      '''.format(
        self.session.auth_token,
        self.source_id,
        self.query,
        self.session.project_id,
        date_to_string(self.query_start_date),
        date_to_string(self.query_end_date),
        self.result_start,
        self.result_end)
    url = self.session.get_url('Search')
    headers = self.session.get_headers(request)
    response = requests.post(url=url, headers=headers, data=request)
    # if the search errored, reduce the time delta and retry
    if response.status_code != 200:
      if self.time_delta > 1:
        self.time_delta = math.ceil(self.time_delta/2)
        self.query_end_date = self.query_start_date + timedelta(days=self.time_delta)
        return self.search()
      else:
        print(' ! Please submit a more specific search')
    soup = BeautifulSoup(response.text, 'lxml')
    self.search_id = self.get_search_id(soup)
    self.total_results = self.get_result_count(soup)
    if self.total_results == 0:
      return []
    else:
      return self.get_documents(soup)


  def get_search_id(self, soup):
    '''
    @param {BeautifulSoup} soup: contains a result from a search
    @returns {str} the search id for the current search
    '''
    try:
      tag = find_tag_by_name(soup, 'searchid')
      return tag.get_text()
    except AttributeError:
      return None


  def get_result_count(self, soup):
    '''
    @param {BeautifulSoup} soup: contains a result from a search
    @returns {int} the number of documents that match the current search
    '''
    try:
      tag = find_tag_by_name(soup, 'documentsfound')
      return int(tag.get_text())
    except AttributeError:
      return 0


  def get_documents_by_range(self):
    '''
    Get documents between self.start and self.end
    '''
    self.log_current_search()

    request = '''
      <SOAP-ENV:Envelope
          xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
          SOAP-ENV:encodingStyle= "http://schemas.xmlsoap.org/soap/encoding/">
        <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <GetDocumentsByRange xmlns="http://getdocumentsbyrange.retrieve.services.v1.wsapi.lexisnexis.com">
            <binarySecurityToken>{0}</binarySecurityToken>
            <searchId>{1}</searchId>
            <retrievalOptions>
              <documentView xmlns="http://result.common.services.v1.wsapi.lexisnexis.com">FullTextWithTerms</documentView>
              <documentMarkup xmlns="http://result.common.services.v1.wsapi.lexisnexis.com">Display</documentMarkup>
              <documentRange xmlns="http://result.common.services.v1.wsapi.lexisnexis.com">
                <begin>{2}</begin>
                <end>{3}</end>
              </documentRange>
            </retrievalOptions>
          </GetDocumentsByRange>
        </soap:Body>
      </SOAP-ENV:Envelope>
      '''.format(
        self.session.auth_token,
        self.search_id,
        self.result_start,
        self.result_end,
      )
    url = self.session.get_url('Retrieval')
    headers = self.session.get_headers(request)
    response = requests.post(url=url, headers=headers, data=request)
    soup = BeautifulSoup(response.text, 'lxml')
    return self.get_documents(soup)


  def get_documents(self, soup):
    '''
    @param: {BeautifulSoup}: the result of a search() query
    @returns: {arr}: a list of objects, each describing a match's metadata
    '''
    # create a store of processed documents
    docs = []
    # find list of document containers
    doc_containers = []
    for i in soup.findChildren():
      if 'documentcontainer' in i.name:
        if 'documentcontainerlist' not in i.name:
          doc_containers.append(i)
    for idx, i in enumerate(doc_containers):
      try:
        doc = Document(session=self.session,
          doc_soup=i,
          get_text=self.get_text)
        docs.append(doc.metadata)
      except Exception as exc:
        print(' ! could not process doc', idx, exc)
    return docs


##
# Document
##

class Document(dict):
  def __init__(self, *args, **kwargs):
    self.session = kwargs.get('session', None)
    self.verbose = kwargs.get('verbose', False)
    self.get_text = kwargs.get('get_text', True)
    self.include_meta = kwargs.get('include_meta', False)
    self.doc_soup = kwargs.get('doc_soup', None)
    self.metadata = self.parse(self.doc_soup)


  def parse(self, soup):
    '''
    @param {BeautifulSoup} soup: contains a document from a search() query:

      <ns1:documentcontainer>
        <ns1:documentid>02A6A252C52</ns1:documentid>
        <ns1:document>PD94bWwgdmVyc2lvbj0i</ns1:document>
      </ns1:documentcontainer>

      Here the <documentid> contains the doc's id and <document> contains a
      base64 encoded representation of the doc's metadata
    @returns: {obj}: an object with metadata attributes from the decoded doc
    '''
    formatted = {}
    decoded = base64.b64decode(soup.find('ns1:document').get_text())
    doc_soup = BeautifulSoup(decoded, 'lxml')
    if self.include_meta:
      for i in doc_soup.find_all('meta'):
        try:
          formatted[ i['name'] ] = i['content']
        except Exception as exc:
          if self.verbose: print(' ! error formatting doc', i['name'], exc)
    formatted['doc_id'] = soup.find('ns1:documentid').get_text()
    formatted['headline'] = self.get_doc_headline(doc_soup)
    formatted['attachment_id'] = self.get_doc_attachment_id(doc_soup)
    formatted['pub'] = self.get_doc_pub(doc_soup)
    formatted['pub_date'] = self.get_doc_pub_date(doc_soup)
    formatted['length'] = self.get_doc_length(doc_soup)
    if self.get_text:
      formatted['full_text'] = self.get_full_text(formatted['doc_id'])
    return formatted


  ##
  # Document attribute accessors
  ##

  def get_doc_headline(self, soup):
    '''
    @param {BeautifulSoup} soup: the soup from a documentcontainer tag
    @returns {str} the headline from a document
    '''
    try:
      headline = soup.find('div', {'class': 'HEADLINE'}).string
      return headline if headline else ''
    except Exception as exc:
      if self.verbose: print(' ! error parsing headline', exc)
      return ''


  def get_doc_attachment_id(self, soup):
    '''
    @param {BeautifulSoup} soup: a documentcontainer tag
    @returns {str}: the attachmentId attribute of a document
    '''
    try:
      attachment_node = soup.find('span', {'class': 'attachmentId'})['id']
      return attachment_node if attachment_node else ''
    except Exception as exc:
      if self.verbose: print(' ! error parsing doc_attachment', exc)
      return ''


  def get_doc_pub(self, soup):
    '''
    @param {BeautifulSoup} soup: a documentcontainer tag
    @returns {str}: the publication attribute of a document
    '''
    try:
      pub = soup.find('div', {'class': 'PUB'}).string
      return pub if pub else ''
    except Exception as exc:
      if self.verbose: print(' ! error parsing doc_pub', exc)
      return ''


  def get_doc_pub_date(self, soup):
    '''
    @param {BeautifulSoup} soup: a documentcontainer tag
    @returns {str}: the pub date attribute from a document
    '''
    try:
      date = soup.find('div', {'class': 'PUB-DATE'}).find('span').string
      return date if date else ''
    except Exception as exc:
      if self.verbose: print(' ! error parsing doc_pub_date', exc)
      return ''


  def get_doc_length(self, soup):
    '''
    @param {BeautifulSoup} soup: a documentcontainer tag
    @returns {str}: the length attribute of a document
    '''
    try:
      length = soup.find('div', {'class': 'LENGTH'}).string
      return length if length else ''
    except Exception as exc:
      if self.verbose: print(' ! error parsing doc_length', exc)
      return ''


  def get_full_text(self, document_id):
    '''
    @param: {int}: a document's id number
    @returns: {str}: the full text content from the document
    '''
    request = '''
      <SOAP-ENV:Envelope
          xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
          SOAP-ENV:encodingStyle= "http://schemas.xmlsoap.org/soap/encoding/">
        <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <GetDocumentsByDocumentId xmlns="http://getdocumentsbydocumentid.retrieve.services.v1.wsapi.lexisnexis.com">
            <binarySecurityToken>{0}</binarySecurityToken>
            <documentIdList>
              <documentId>{1}</documentId>
            </documentIdList>
            <retrievalOptions>
              <documentView>FullTextWithTerms</documentView>
              <documentMarkup>Display</documentMarkup>
            </retrievalOptions>
          </GetDocumentsByDocumentId>
        </soap:Body>
      </SOAP-ENV:Envelope>
      '''.format(self.session.auth_token, document_id)

    url = self.session.get_url('Retrieval')
    headers = self.session.get_headers(request)
    response = requests.post(url=url, headers=headers, data=request)
    soup = BeautifulSoup(response.text, 'xml')
    return base64.b64decode(soup.document.text).decode('utf8')

##
# Soup Helpers
##

def find_tag_by_name(soup, tag_name):
  '''
  Given a BeautifulSoup object and a tag name, return the first
  tag whose name contains `tag_name`
  @param {BeautifulSoup} soup: a BeautifulSoup object
  @param {str} tag_name: the name of the tag to find
  @returns {BeautifulSoup} the first child whose name contains `tag_name`
  '''
  for tag in soup.findChildren():
    if tag_name in tag.name:
      return tag
  return None


def split_on_br(soup):
  '''
  @param: {BeautifulSoup}: contains a list of elements separated by <br/> tags
  @returns: {arr}: a list of the elements in the soup
  '''
  elems = []
  for i in soup.contents:
    if getattr(i, 'name', None) != 'br':
      if type(i) is element.Tag:
        elems.append(i.string)
      else:
        elems.append(i)
  return elems

##
# Date Helpers
##

def string_to_date(string_date):
  '''
  @param: {str} string_date: a date in string format: '2017-12-01'
  @returns: {datetime}: the input date in datetime format
  '''
  year, month, day = [int(i) for i in string_date.split('-')]
  return datetime(year, month, day)


def date_to_string(datetime_date):
  '''
  @param: {datetime}: a datetime object
  @returns: {str}: the input datetime in string format: 'YYYY-MM-DD'
  '''
  return datetime_date.strftime('%Y-%m-%d')
