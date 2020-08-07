import json
import os
import pprint
import re

import jq
import requests
from jsonschema import Draft7Validator

BASE = 'https://api.github.com'
ISSUE_COMMENTS = BASE + '/repos/{repo}/issues/{issue_number}/comments'
DELETE_ISSUE_COMMENTS = BASE + '/repos/{repo}/issues/comments/{comment_id}'

COMMENT_HEADER = '**JSON Schema validation failed for `{path}`**'
COMMENT = '''
---
**Validator:** `{validator}`
**Validator value:**
```
{validator_value}
```
**Message:**
```
{message}
```
**Instance:**
```
{instance}
```'''


def request(verb, url, data=None):
    headers = {'Authorization': 'Bearer {}'.format(os.getenv('INPUT_TOKEN'))}
    verb_map = {
        'get': requests.get,
        'post': requests.post,
        'delete': requests.delete
    }

    response = verb_map.get(verb)(url, json=data, headers=headers)

    if response.status_code >= 200 and response.status_code < 300:
        try:
            return response.json()
        except Exception:
            return response.content
    else:
        raise Exception('Status code {}: {}'.format(response.status_code, url))


def json_from_file(file_path):
    with open(file_path) as f:
        return json.load(f)


def validate_file(json_schema, path_pattern, file_path):
    pattern = re.compile(path_pattern)
    if pattern.match(file_path):
        print('validating {}'.format(file_path))
        schema = json_from_file(json_schema)
        instance = json_from_file(file_path)

        validator = Draft7Validator(schema)
        return sorted(validator.iter_errors(instance), key=str)
    else:
        print('{} doesn\'t match pattern {}'.format(file_path, path_pattern))
        return []


def delete_comment(repo, id):
    delete_comment_url = DELETE_ISSUE_COMMENTS.format(repo=repo, comment_id=id)
    request('delete', delete_comment_url)


def delete_comments(repo, pull_number):
    print('clearing comments')
    bot = 'github-actions[bot]'
    comment_url = ISSUE_COMMENTS.format(repo=repo, issue_number=pull_number)

    comments = request('get', comment_url)
    jq_user = jq.compile('.user.login')
    jq_comment = jq.compile('.id')

    for comment in comments:
        user = jq_user.input(comment).first()
        if user == bot:
            comment_id = jq_comment.input(comment).first()
            delete_comment(repo, comment_id)


def create_comment(repo, pull_number, validation_errors):
    print('sending comment')
    formatted_errors = []
    for file in validation_errors:
        path = file['path']
        errors = file['errors']

        header = COMMENT_HEADER.format(path=path)
        formatted_errors.append(header)

        for error in errors:
            message = error.message
            validator = error.validator
            validator_value = error.validator_value
            instance = error.instance

            formatted = COMMENT.format(
                message=pprint.pformat(message, width=72),
                validator=validator,
                validator_value=json.dumps(validator_value),
                instance=json.dumps(instance)
            )
            formatted_errors.append(formatted)

    joined_errors = '\r\n\r\n'.join(formatted_errors)

    comment_url = ISSUE_COMMENTS.format(repo=repo, issue_number=pull_number)
    body = {'body': joined_errors}
    request('post', comment_url, body)
