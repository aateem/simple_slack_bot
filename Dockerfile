FROM python:3.8 as builder
RUN pip install --upgrade setuptools wheel
COPY ./whistleblower /build/whistleblower
WORKDIR /build/whistleblower
RUN python setup.py sdist bdist_wheel

FROM python:3.8
WORKDIR /app/whistleblower_bot
COPY --from=builder /build/whistleblower/dist/whistleblower_bot-0.0.1-py3-none-any.whl .
RUN pip install whistleblower_bot-0.0.1-py3-none-any.whl
RUN pip install gunicorn
