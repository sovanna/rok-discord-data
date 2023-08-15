FROM pypy:3

WORKDIR /usr/src/app/
RUN apt-get update \
  && apt-get install build-essential -y \
  && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN apt-get update \
  && apt-get install --no-install-recommends  locales -y \
  && apt-get install --no-install-recommends  vim-nox -y \
  && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
  && dpkg-reconfigure --frontend=noninteractive locales \
  && apt-get clean \
  && apt-get autoremove \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd -r sasr \
  && useradd -r -s /bin/false -g sasr sasr

USER sasr

CMD ["pypy3", "./main.py"]
