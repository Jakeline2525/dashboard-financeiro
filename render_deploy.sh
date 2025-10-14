#!/bin/bash

# Instala as dependências listadas no requirements.txt
pip install -r requirements.txt

# Roda a aplicação Streamlit
# Não precisamos mais dos comandos de locale aqui
streamlit run dashboard.py --server.port $PORT
