ARG PYTHON_VERSION=3.10.4-slim-buster

FROM python:"${PYTHON_VERSION}"

ARG WORKDIR="/version_script"
ARG USER="python"

RUN adduser ${USER} --shell /bin/bash && adduser ${USER} python \
    && mkdir -p ${WORKDIR}

COPY version.py ${WORKDIR}
COPY libs ${WORKDIR}/libs
COPY release_templates ${WORKDIR}/release_templates
COPY requirements.txt ${WORKDIR}

RUN chown ${USER}:python ${WORKDIR}/version.py \
    && pip install --no-cache -r ${WORKDIR}/requirements.txt

CMD ["/bin/bash", "-c", "cat"]

USER ${USER}