FROM python:3-alpine

RUN apk update && apk upgrade
RUN apk add --no-cache curl py3-pip pkgconfig python3-dev openssl-dev libffi-dev musl-dev make gcc

WORKDIR /service
COPY ./service/requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY ./service /service

EXPOSE 5000/tcp

CMD ["python3", "-u", "./proxy-service.py"]
