#!/bin/bash

# Instala as dependências
pip install -r requirements.txt

# Instala e configura o locale pt_BR para as datas em português
apt-get update && apt-get install -y locales
locale-gen pt_BR.UTF-8
export LANG=pt_BR.UTF-8

# Roda a aplicação Streamlit
streamlit run dashboard.py --server.port $PORT
