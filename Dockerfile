FROM python:3-alpine
MAINTAINER Graham Moore "graham.moore@sesam.io"

RUN apk update && apk upgrade
RUN apk add --no-cache curl python pkgconfig python-dev openssl-dev libffi-dev musl-dev make gcc
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python

COPY ./service /service
WORKDIR /service
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
EXPOSE 5000/tcp

CMD ["python3", "-u", "./proxy-service.py"]
