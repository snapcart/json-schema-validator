FROM python:3.7-slim-stretch

RUN pip install jsonschema requests jq

COPY . /

RUN chmod +x /entrypoint.sh
ENTRYPOINT [ "/entrypoint.sh" ]
