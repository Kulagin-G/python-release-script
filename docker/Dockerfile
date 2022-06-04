ARG PYTHON_VERSION=3.10.4-slim-buster

FROM python:"${PYTHON_VERSION}"

RUN adduser python --shell /bin/bash && adduser python python  \
    && pip install --no-cache loguru==0.6.0 python-gitlab==3.5.0 requests==2.27.1 semver==2.13.0 packaging==21.3 Jinja2==3.1.1

ENV GITLAB_URL "https://gitlab.com/"

COPY version.py .
RUN chown python:python /version.py

CMD ["/bin/bash", "-c", "cat"]

USER python