FROM python:latest

WORKDIR /usr/agent

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ .

CMD ["python", "main.py"]