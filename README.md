Jira comments downloader
========================

A script to donwload all comments from all jira issues matching a JQL query. Data is written to STDOUT as new-line separated JSON objects (ndjson)


Requirements
------------

Following python3 libraries must be installed:

- jira - https://jira.readthedocs.io/
- jira2markdown - https://github.com/catcombo/jira2markdown

Setup
-----

```bash
python3 -m virtualenv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r REQUIREMENTS.txt

mkdir private
cp conf-example.ini private/conf.ini

# Configure your Jira endpoint, personal access token and JQL query
vi private/conf.ini
```

Execution
---------

```bash
source venv/bin/activate
python3 download_comments.py -c private/conf.ini -s source >> comments.ndjson
```


License
-------
MIT: see https://opensource.org/license/mit

Copyright 2024 Paolo Prigione

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

