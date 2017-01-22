FROM python:3.5.2-alpine

ADD . /app

WORKDIR /app

RUN pip install -r requirements.txt

EXPOSE 5000

ENTRYPOINT ["python", "main.py"]