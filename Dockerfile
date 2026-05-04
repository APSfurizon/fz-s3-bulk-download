FROM python:3.12

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN apt update
RUN apt install moreutils -y
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app.py /code/app.py

CMD fastapi run app.py --port 80 --proxy-headers | ts | tee /code/data/log.txt
#CMD ["fastapi", "run", "app.py", "--port", "80", "--proxy-headers"]